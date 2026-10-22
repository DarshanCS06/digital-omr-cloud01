"""
Robust Computer Vision OMR Detection Engine with Sensitive Small-Mark Recognition.
Implements the complete OpenCV image processing pipeline with:
- Dual-mode corner registration marker and document boundary detection
- Perspective correction and canonical alignment
- Inner-bubble ink measurement strictly excluding printed circular borders
- Multi-feature small-mark detection (Connected Component Analysis, Dark Pixel Ratio, Local Contrast)
- Support for small dots, partial pen strokes, faint pencil marks, partial fills, and solid fills
- Invariance to ambient room lighting, flash reflections, shadows, and paper grain
- Administrator-configurable sensitivity presets (HIGH, NORMAL, CONSERVATIVE)
- Calibrated response classification (Single, Blank, Multiple, Review)
- Visual diagnostic overlay generation with mark centroid localization for human inspection
"""
import cv2
import math
import logging
import numpy as np
from typing import Dict, List, Tuple, Optional, Any

from backend.app.config import settings
from backend.app.omr.preprocessor import ImagePreprocessor
from backend.app.omr.htr_engine import HTREngine
from backend.app.omr.layout import (
    OMRLayoutConfig,
    BubbleLocation,
    CANONICAL_WIDTH,
    CANONICAL_HEIGHT,
    SCALE_X,
    SCALE_Y,
)


class OMRDetector:
    def __init__(
        self,
        layout: Optional[OMRLayoutConfig] = None,
        sensitivity: Optional[str] = None,
    ):
        self.layout = layout or OMRLayoutConfig(question_count=100)
        self.expected_question_count = self.layout.question_count
        self._last_alignment_info: Dict[str, Any] = {}
        self._last_oriented_img: Optional[np.ndarray] = None
        self.sensitivity = (sensitivity or getattr(settings, "OMR_SENSITIVITY", "NORMAL")).upper()
        if self.sensitivity not in ("HIGH", "NORMAL", "CONSERVATIVE", "LOW"):
            self.sensitivity = "NORMAL"

        # Calibrated legacy thresholds for backward compatibility
        self.blank_threshold = 0.20
        self.fill_threshold = 0.38
        self.multiple_threshold = 0.30
        self.contrast_margin = 0.18

    def set_sensitivity(self, sensitivity: str) -> None:
        """Sets the detection sensitivity level ('HIGH', 'NORMAL', 'CONSERVATIVE')."""
        sens = sensitivity.upper()
        if sens in ("HIGH", "NORMAL", "CONSERVATIVE", "LOW"):
            self.sensitivity = "CONSERVATIVE" if sens == "LOW" else sens

    def order_quad_points(self, pts: np.ndarray) -> np.ndarray:
        """Orders 4 points as: top-left, top-right, bottom-right, bottom-left."""
        pts = np.asarray(pts, dtype="float32")
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]  # Top-left has smallest sum (x + y)
        rect[2] = pts[np.argmax(s)]  # Bottom-right has largest sum (x + y)

        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]  # Top-right has smallest diff (y - x)
        rect[3] = pts[np.argmax(diff)]  # Bottom-left has largest diff (y - x)
        return rect

    def find_registration_markers(self, img: np.ndarray) -> Optional[np.ndarray]:
        """
        Detects the 4 corner registration markers on the sheet.
        Supports both square and rectangular blocks across varying lighting conditions.
        """
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()

        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 5
        )

        contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        page_area = float(h * w)
        candidates = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < (page_area * 0.00008) or area > (page_area * 0.035):
                continue

            x, y, cw, ch = cv2.boundingRect(cnt)
            if cw == 0 or ch == 0:
                continue

            aspect = float(cw) / float(ch)
            solidity = area / float(cw * ch)

            if 0.35 <= aspect <= 2.8 and solidity >= 0.58:
                roi_gray = gray[y : y + ch, x : x + cw]
                if roi_gray.size == 0 or float(np.mean(roi_gray)) > 125.0:
                    continue
                M = cv2.moments(cnt)
                if M["m00"] > 0:
                    cx = float(M["m10"] / M["m00"])
                    cy = float(M["m01"] / M["m00"])
                    # Corner markers reside near the 4 outer corners (allowing for tilt/rotation)
                    if (cx < w * 0.24 or cx > w * 0.76) and (cy < h * 0.18 or cy > h * 0.82):
                        candidates.append((cx, cy, area))

        if len(candidates) < 4:
            return None

        mid_x, mid_y = w / 2.0, h / 2.0
        tl_cands = [c for c in candidates if c[0] < mid_x and c[1] < mid_y]
        tr_cands = [c for c in candidates if c[0] >= mid_x and c[1] < mid_y]
        br_cands = [c for c in candidates if c[0] >= mid_x and c[1] >= mid_y]
        bl_cands = [c for c in candidates if c[0] < mid_x and c[1] >= mid_y]

        if not (tl_cands and tr_cands and br_cands and bl_cands):
            return None

        tl = min(tl_cands, key=lambda p: (p[0]**2 + p[1]**2))
        tr = min(tr_cands, key=lambda p: ((w - p[0])**2 + p[1]**2))
        br = min(br_cands, key=lambda p: ((w - p[0])**2 + (h - p[1])**2))
        bl = min(bl_cands, key=lambda p: (p[0]**2 + (h - p[1])**2))

        areas = [tl[2], tr[2], br[2], bl[2]]
        if max(areas) / max(1.0, min(areas)) > 3.5:
            return None

        return np.array([(tl[0], tl[1]), (tr[0], tr[1]), (br[0], br[1]), (bl[0], bl[1])], dtype="float32")

    def detect_sheet_boundary(self, img: np.ndarray) -> Optional[np.ndarray]:
        """
        Detects the outer boundary of the A4 page on contrasting backgrounds.
        Used as a robust fallback/reinforcement when corner markers are cropped or obscured.
        """
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        edges = cv2.Canny(blurred, 30, 120)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(edges, kernel, iterations=2)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        img_area = float(h * w)

        for cnt in contours[:5]:
            area = cv2.contourArea(cnt)
            if area < (img_area * 0.35):
                continue

            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                pts = approx.reshape(4, 2).astype("float32")
                ordered = self.order_quad_points(pts)
                min_y = float(np.min(ordered[:, 1]))
                max_y = float(np.max(ordered[:, 1]))
                # Must span nearly the full document height (rejects internal form boxes)
                if min_y < (h * 0.08) and max_y > (h * 0.92):
                    return ordered

        return None

    def auto_calibrate_vidyakashi_grid(self, canon_img: np.ndarray) -> bool:
        """
        Automatically calibrates the exact X-columns, Y-rows, and bubble radius
        directly from the detected bubble circles on a canonical (1654 x 2338) Vidyakashi sheet.
        Supports both 4-column (100Q) and 2-column (25Q) Vidyakashi variants.
        """
        gray = cv2.cvtColor(canon_img, cv2.COLOR_BGR2GRAY) if len(canon_img.shape) == 3 else canon_img
        if len(canon_img.shape) == 3:
            b, g, r = cv2.split(canon_img)
            redness = np.clip(
                r.astype(np.float32) - 0.5 * (g.astype(np.float32) + b.astype(np.float32)),
                0,
                255,
            ).astype(np.uint8)
        else:
            redness = np.zeros_like(gray)

        y_min, y_max = 1015, 2080
        roi_gray = gray[y_min:y_max, :]
        roi_red = redness[y_min:y_max, :]

        _, th_dark = cv2.threshold(roi_gray, 140, 255, cv2.THRESH_BINARY_INV)
        _, th_red = cv2.threshold(roi_red, 20, 255, cv2.THRESH_BINARY)
        combined = cv2.bitwise_or(th_dark, th_red)

        contours, _ = cv2.findContours(combined, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        raw_circles = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if 20 <= cw <= 56 and 20 <= ch <= 56:
                aspect = cw / float(ch)
                if 0.80 <= aspect <= 1.25:
                    area = cv2.contourArea(cnt)
                    if area >= 120:
                        cx = x + cw / 2.0
                        cy = y + y_min + ch / 2.0
                        rad = (cw + ch) / 4.0
                        raw_circles.append((cx, cy, rad))

        dedup = []
        for cx, cy, rad in sorted(raw_circles, key=lambda c: c[2], reverse=True):
            if not any(abs(cx - dx) < 12 and abs(cy - dy) < 12 for dx, dy, _ in dedup):
                dedup.append((cx, cy, rad))

        if len(dedup) < 40:
            return False

        xs = sorted([c[0] for c in dedup])
        x_groups = []
        if xs:
            curr = [xs[0]]
            for x in xs[1:]:
                if x - curr[-1] > 20:
                    x_groups.append(curr)
                    curr = [x]
                else:
                    curr.append(x)
            x_groups.append(curr)
        valid_x_cols = [int(round(np.median(grp))) for grp in x_groups if len(grp) >= 6]

        ys = sorted([c[1] for c in dedup])
        y_groups = []
        if ys:
            curr = [ys[0]]
            for y in ys[1:]:
                if y - curr[-1] > 16:
                    y_groups.append(curr)
                    curr = [y]
                else:
                    curr.append(y)
            y_groups.append(curr)
        valid_y_rows = [int(round(np.median(grp))) for grp in y_groups if len(grp) >= 3]
        median_rad = int(round(np.median([c[2] for c in dedup]))) if dedup else 15

        options = ["A", "B", "C", "D"][: self.layout.options_per_question]

        if len(valid_x_cols) == 16 and len(valid_y_rows) >= 25:
            row_y = valid_y_rows[-25:]
            self.layout = OMRLayoutConfig(
                question_count=self.layout.question_count,
                options_per_question=self.layout.options_per_question,
                template_type="vidyakashi_official",
            )
            self.layout.bubble_radius = median_rad
            self.layout.bubbles = {}
            total_q = min(self.layout.question_count, 100)
            for q in range(1, total_q + 1):
                b_idx = (q - 1) // 25
                r_idx = (q - 1) % 25
                cy_px = row_y[r_idx]
                self.layout.bubbles[q] = {}
                for opt_i, opt in enumerate(options):
                    cx_px = valid_x_cols[b_idx * 4 + opt_i]
                    self.layout.bubbles[q][opt] = BubbleLocation(
                        question=q,
                        option=opt,
                        cx=cx_px,
                        cy=cy_px,
                        radius=median_rad,
                        cx_pt=cx_px / SCALE_X,
                        cy_pt=cy_px / SCALE_Y,
                        radius_pt=median_rad / SCALE_X,
                    )
            return True

        if len(valid_x_cols) == 8 and len(valid_y_rows) >= 13:
            row_y = valid_y_rows[-13:]
            self.layout = OMRLayoutConfig(
                question_count=self.layout.question_count,
                options_per_question=self.layout.options_per_question,
                template_type="vidyakashi_25",
            )
            self.layout.bubble_radius = median_rad
            self.layout.bubbles = {}
            total_q = min(self.layout.question_count, 25)
            for q in range(1, total_q + 1):
                b_idx = 0 if q <= 13 else 1
                r_idx = (q - 1) if q <= 13 else (q - 14)
                cy_px = row_y[r_idx]
                self.layout.bubbles[q] = {}
                for opt_i, opt in enumerate(options):
                    cx_px = valid_x_cols[b_idx * 4 + opt_i]
                    self.layout.bubbles[q][opt] = BubbleLocation(
                        question=q,
                        option=opt,
                        cx=cx_px,
                        cy=cy_px,
                        radius=median_rad,
                        cx_pt=cx_px / SCALE_X,
                        cy_pt=cy_px / SCALE_Y,
                        radius_pt=median_rad / SCALE_X,
                    )
            return True

        return False

    def orient_and_deskew_image(self, img: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Automatically corrects:
        - 90° / 270° landscape orientation
        - 180° upside-down orientation
        - Minor in-plane rotation / tilt (1° to 28°)
        Returns (oriented_img, alignment_metadata).
        """
        oriented = img.copy()
        h, w = oriented.shape[:2]
        rotation_deg = 0
        tilt_angle_deg = 0.0
        was_tilted = False

        # 1. Landscape orientation check (90° or 270° rotated sheet)
        if w > h * 1.12:
            rot_cw = cv2.rotate(oriented, cv2.ROTATE_90_CLOCKWISE)
            rot_ccw = cv2.rotate(oriented, cv2.ROTATE_90_COUNTERCLOCKWISE)

            def _header_advantage(cand: np.ndarray) -> float:
                g = cv2.cvtColor(cand, cv2.COLOR_BGR2GRAY) if len(cand.shape) == 3 else cand
                ch, cw = g.shape[:2]
                top_band = g[int(ch * 0.02):int(ch * 0.22), int(cw * 0.12):int(cw * 0.88)]
                bot_band = g[int(ch * 0.78):int(ch * 0.96), int(cw * 0.12):int(cw * 0.88)]
                top_m = float(np.mean(top_band)) if top_band.size > 0 else 255.0
                bot_m = float(np.mean(bot_band)) if bot_band.size > 0 else 255.0
                return bot_m - top_m

            if _header_advantage(rot_cw) >= _header_advantage(rot_ccw):
                oriented = rot_cw
                rotation_deg = 90
            else:
                oriented = rot_ccw
                rotation_deg = 270
            was_tilted = True

        # 2. Upside-down (180°) check on portrait image
        gray_p = cv2.cvtColor(oriented, cv2.COLOR_BGR2GRAY) if len(oriented.shape) == 3 else oriented
        ph, pw = gray_p.shape[:2]
        top_banner = gray_p[int(ph * 0.02):int(ph * 0.14), int(pw * 0.15):int(pw * 0.85)]
        bot_banner = gray_p[int(ph * 0.86):int(ph * 0.98), int(pw * 0.15):int(pw * 0.85)]
        top_mean = float(np.mean(top_banner)) if top_banner.size > 0 else 255.0
        bot_mean = float(np.mean(bot_banner)) if bot_banner.size > 0 else 255.0

        # Also check upper vs lower header density for standard sheets
        top_header = gray_p[int(ph * 0.04):int(ph * 0.20), int(pw * 0.10):int(pw * 0.45)]
        bot_header = gray_p[int(ph * 0.80):int(ph * 0.96), int(pw * 0.55):int(pw * 0.90)]
        th_mean = float(np.mean(top_header)) if top_header.size > 0 else 255.0
        bh_mean = float(np.mean(bot_header)) if bot_header.size > 0 else 255.0

        if (bot_mean < 160.0 and top_mean > 185.0) or (th_mean > 250.5 and bh_mean < 242.0):
            oriented = cv2.rotate(oriented, cv2.ROTATE_180)
            rotation_deg = (rotation_deg + 180) % 360
            was_tilted = True
            gray_p = cv2.cvtColor(oriented, cv2.COLOR_BGR2GRAY) if len(oriented.shape) == 3 else oriented
            ph, pw = gray_p.shape[:2]

        # 3. Estimate in-plane skew angle and deskew if tilted
        skew_deg = ImagePreprocessor.estimate_skew_angle(gray_p)
        if 1.0 <= abs(skew_deg) <= 28.0:
            tilt_angle_deg = round(float(skew_deg), 2)
            was_tilted = True
            banner_check = gray_p[int(ph * 0.02):int(ph * 0.14), int(pw * 0.15):int(pw * 0.85)]
            is_vidyakashi_banner = bool(banner_check.size > 0 and float(np.mean(banner_check)) < 155.0)
            # If Vidyakashi sheet or 4 corner markers aren't directly handling the warp, deskew via affine rotation
            if is_vidyakashi_banner or self.find_registration_markers(oriented) is None:
                border_val = (255, 255, 255) if len(oriented.shape) == 3 else 255

                def _rotate_by(src_img: np.ndarray, angle_deg: float) -> np.ndarray:
                    sh_i, sw_i = src_img.shape[:2]
                    mat = cv2.getRotationMatrix2D((sw_i / 2.0, sh_i / 2.0), angle_deg, 1.0)
                    return cv2.warpAffine(
                        src_img,
                        mat,
                        (sw_i, sh_i),
                        flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=border_val,
                    )

                cand_pos = _rotate_by(oriented, skew_deg)
                cand_neg = _rotate_by(oriented, -skew_deg)
                g_pos = cv2.cvtColor(cand_pos, cv2.COLOR_BGR2GRAY) if len(cand_pos.shape) == 3 else cand_pos
                g_neg = cv2.cvtColor(cand_neg, cv2.COLOR_BGR2GRAY) if len(cand_neg.shape) == 3 else cand_neg
                res_pos = abs(ImagePreprocessor.estimate_skew_angle(g_pos))
                res_neg = abs(ImagePreprocessor.estimate_skew_angle(g_neg))
                oriented = cand_pos if res_pos <= res_neg else cand_neg

        return oriented, {
            "was_tilted": was_tilted,
            "tilt_angle_deg": tilt_angle_deg,
            "rotation_deg": rotation_deg,
        }

    def rectify_image(self, img: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        Rectifies the input image to the canonical A4 coordinate space (1654 x 2338).
        Supports:
        - Automatic 90°/180°/270° orientation and in-plane tilt deskewing
        - Official Vidyakashi 4-Column 100Q OMR Sheet (vidyakashi_official) with auto-grid calibration
        - Vidyakashi 2-Column 25Q OMR Sheet (vidyakashi_25) with auto-grid calibration
        - Standard A4 OMR Sheet with 4 corner markers (standard)
        """
        oriented_img, align_meta = self.orient_and_deskew_image(img)
        self._last_oriented_img = oriented_img
        self._last_alignment_info = align_meta

        gray_sample = cv2.cvtColor(oriented_img, cv2.COLOR_BGR2GRAY) if len(oriented_img.shape) == 3 else oriented_img
        sh, sw = gray_sample.shape[:2]
        banner_crop = gray_sample[int(sh * 0.02):int(sh * 0.14), int(sw * 0.15):int(sw * 0.85)]
        has_dark_banner = bool(banner_crop.size > 0 and float(np.mean(banner_crop)) < 155.0)

        # 1. If Vidyakashi header banner is detected, try direct canonical resize + circle grid self-calibration first
        if has_dark_banner:
            resized = cv2.resize(oriented_img, (CANONICAL_WIDTH, CANONICAL_HEIGHT), interpolation=cv2.INTER_LINEAR)
            if self.auto_calibrate_vidyakashi_grid(resized):
                return resized, True

        # 2. Try 4-corner black registration marker detection
        marker_pts = self.find_registration_markers(oriented_img)
        if marker_pts is not None:
            if has_dark_banner and self.layout.template_type not in ("vidyakashi_25", "vidyakashi_50") and self.layout.question_count <= 50:
                self.layout = OMRLayoutConfig(
                    question_count=self.layout.question_count,
                    options_per_question=self.layout.options_per_question,
                    template_type="vidyakashi_25",
                )
            target_tl = self.layout.markers["top_left"]
            target_tr = self.layout.markers["top_right"]
            target_br = self.layout.markers["bottom_right"]
            target_bl = self.layout.markers["bottom_left"]
            target_marker_pts = np.array([target_tl, target_tr, target_br, target_bl], dtype="float32")

            ordered_src = self.order_quad_points(marker_pts)
            top_dx = float(ordered_src[1][0] - ordered_src[0][0])
            top_dy = float(ordered_src[1][1] - ordered_src[0][1])
            if top_dx > 10.0:
                marker_angle = math.degrees(math.atan2(top_dy, top_dx))
                if abs(marker_angle) >= 1.2:
                    self._last_alignment_info["was_tilted"] = True
                    self._last_alignment_info["tilt_angle_deg"] = round(marker_angle, 2)

            matrix = cv2.getPerspectiveTransform(ordered_src, target_marker_pts)
            rectified = cv2.warpPerspective(
                oriented_img, matrix, (CANONICAL_WIDTH, CANONICAL_HEIGHT), flags=cv2.INTER_LINEAR
            )
            if has_dark_banner:
                self.auto_calibrate_vidyakashi_grid(rectified)
            return rectified, True

        # 3. If dark Vidyakashi header banner is present without 4 black corner blocks -> Official 4-Column Vidyakashi Sheet
        if has_dark_banner:
            if self.layout.template_type not in ("vidyakashi_official", "vidyakashi_100"):
                self.layout = OMRLayoutConfig(
                    question_count=self.layout.question_count,
                    options_per_question=self.layout.options_per_question,
                    template_type="vidyakashi_official",
                )
            boundary_pts = self.detect_sheet_boundary(oriented_img)
            if boundary_pts is not None:
                page_target = np.array([
                    [0, 0],
                    [CANONICAL_WIDTH, 0],
                    [CANONICAL_WIDTH, CANONICAL_HEIGHT],
                    [0, CANONICAL_HEIGHT],
                ], dtype="float32")
                matrix = cv2.getPerspectiveTransform(boundary_pts, page_target)
                rectified = cv2.warpPerspective(
                    oriented_img, matrix, (CANONICAL_WIDTH, CANONICAL_HEIGHT), flags=cv2.INTER_LINEAR
                )
                self.auto_calibrate_vidyakashi_grid(rectified)
                return rectified, True

            resized = cv2.resize(oriented_img, (CANONICAL_WIDTH, CANONICAL_HEIGHT), interpolation=cv2.INTER_LINEAR)
            return resized, True

        # 3. Try sheet boundary detection for standard sheets
        boundary_pts = self.detect_sheet_boundary(oriented_img)
        if boundary_pts is not None:
            page_target = np.array([
                [0, 0],
                [CANONICAL_WIDTH, 0],
                [CANONICAL_WIDTH, CANONICAL_HEIGHT],
                [0, CANONICAL_HEIGHT],
            ], dtype="float32")
            matrix = cv2.getPerspectiveTransform(boundary_pts, page_target)
            rectified = cv2.warpPerspective(
                oriented_img, matrix, (CANONICAL_WIDTH, CANONICAL_HEIGHT), flags=cv2.INTER_LINEAR
            )
            return rectified, True

        # 4. Fallback: Direct resize
        resized = cv2.resize(oriented_img, (CANONICAL_WIDTH, CANONICAL_HEIGHT), interpolation=cv2.INTER_AREA)
        return resized, False

    def validate_sheet_alignment_and_template(
        self,
        rectified_img: np.ndarray,
        markers_detected: bool,
    ) -> Dict[str, Any]:
        """
        Verifies:
        1. Whether the uploaded sheet layout matches the selected examination's OMR template.
        2. Whether all required answer bubble regions remain visible and uncropped after alignment.
        """
        gray = cv2.cvtColor(rectified_img, cv2.COLOR_BGR2GRAY) if len(rectified_img.shape) == 3 else rectified_img
        h, w = gray.shape[:2]

        template_matches = True
        regions_visible = True
        validation_error: Optional[str] = None

        # 1. Check if layout has enough question bubbles for the selected examination
        detected_q_capacity = len(self.layout.bubbles)
        if detected_q_capacity < self.expected_question_count:
            template_matches = False
            validation_error = "The sheet layout does not match the selected examination."
        elif not markers_detected:
            banner_crop = gray[int(h * 0.02):int(h * 0.14), int(w * 0.15):int(w * 0.85)]
            has_vidyakashi_banner = bool(banner_crop.size > 0 and float(np.mean(banner_crop)) < 155.0)
            if has_vidyakashi_banner:
                regions_visible = False
                validation_error = "Part of the answer sheet is missing. Upload the complete sheet."
            else:
                # Verify whether circular OMR bubbles exist at expected locations
                visible_bubble_rows = 0
                for q_num, opt_map in self.layout.bubbles.items():
                    xs = [b.cx for b in opt_map.values()]
                    ys = [b.cy for b in opt_map.values()]
                    r = next(iter(opt_map.values())).radius
                    x1, x2 = max(0, min(xs) - r - 4), min(w, max(xs) + r + 4)
                    y1, y2 = max(0, min(ys) - r - 4), min(h, max(ys) + r + 4)
                    patch = gray[y1:y2, x1:x2]
                    if patch.size > 0 and float(np.std(patch)) >= 8.0:
                        visible_bubble_rows += 1
                if visible_bubble_rows < max(5, int(len(self.layout.bubbles) * 0.5)):
                    template_matches = False
                    validation_error = "The sheet layout does not match the selected examination."

        # 2. Check if all required answer regions (1..expected_question_count) are visible and uncropped
        if template_matches:
            missing_questions_list: List[int] = []
            for q_num in range(1, min(self.expected_question_count, len(self.layout.bubbles)) + 1):
                opt_map = self.layout.bubbles.get(q_num, {})
                if not opt_map:
                    missing_questions_list.append(q_num)
                    continue
                xs = [b.cx for b in opt_map.values()]
                ys = [b.cy for b in opt_map.values()]
                r = next(iter(opt_map.values())).radius
                if min(xs) - r < 2 or max(xs) + r >= w - 2 or min(ys) - r < 2 or max(ys) + r >= h - 2:
                    missing_questions_list.append(q_num)
                    continue
                x1, x2 = max(0, min(xs) - r - 3), min(w, max(xs) + r + 3)
                y1, y2 = max(0, min(ys) - r - 3), min(h, max(ys) + r + 3)
                patch = gray[y1:y2, x1:x2]
                # Even a blank OMR row has printed circle outlines (ptp > 20, std > 4.2)
                if patch.size == 0 or (float(np.max(patch)) - float(np.min(patch))) < 20.0 or float(np.std(patch)) < 4.2:
                    missing_questions_list.append(q_num)

            missing_questions = len(missing_questions_list)
            if missing_questions > max(2, int(self.expected_question_count * 0.10)):
                # Distinguish between template mismatch (e.g. Q1..25 present, Q26..100 unprinted) vs cropped sheet
                q1_to_25_missing = sum(1 for q in missing_questions_list if q <= 25)
                q26_plus_missing = sum(1 for q in missing_questions_list if q > 25)
                if self.expected_question_count > 25 and q1_to_25_missing <= 2 and q26_plus_missing >= int((self.expected_question_count - 25) * 0.6):
                    template_matches = False
                    validation_error = "The sheet layout does not match the selected examination."
                else:
                    regions_visible = False
                    validation_error = "Part of the answer sheet is missing. Upload the complete sheet."

        was_tilted = bool(self._last_alignment_info.get("was_tilted", False))
        tilt_deg = float(self._last_alignment_info.get("tilt_angle_deg", 0.0))
        rot_deg = int(self._last_alignment_info.get("rotation_deg", 0))

        alignment_message = (
            validation_error
            if validation_error
            else (
                "The OMR sheet is tilted. Aligning the image..."
                if was_tilted
                else "OMR sheet boundaries and template verified."
            )
        )

        return {
            "template_matches": template_matches,
            "regions_visible": regions_visible,
            "was_tilted": was_tilted,
            "tilt_angle_deg": tilt_deg,
            "rotation_deg": rot_deg,
            "validation_error": validation_error,
            "alignment_message": alignment_message,
        }

    def evaluate_bubble_features(
        self,
        gray_img: np.ndarray,
        cx: int,
        cy: int,
        radius: int,
    ) -> Dict[str, Any]:
        """
        Extracts multi-feature ink measurements inside the inner bubble region.
        Samples inner 60-65% radius to guarantee exclusion of printed circular outlines.
        Measures:
        - Local background intensity (lighting and shadow invariant)
        - Mean inner ink contrast
        - Dark ink pixel ratio
        - Connected Component Analysis (CCA) for small dots and pen strokes
        - Largest connected component area and mark centroid coordinates
        """
        h_img, w_img = gray_img.shape[:2]
        inner_scale = 0.60 if radius <= 16 else 0.65
        inner_r = max(3, int(radius * inner_scale))

        # 1. Local background estimation (92nd percentile in surrounding 1.4x box)
        box_half = max(inner_r + 4, int(radius * 1.4))
        bx1 = max(0, cx - box_half)
        bx2 = min(w_img, cx + box_half)
        by1 = max(0, cy - box_half)
        by2 = min(h_img, cy + box_half)

        roi_box = gray_img[by1:by2, bx1:bx2]
        bg_intensity = float(np.percentile(roi_box, 92)) if roi_box.size > 0 else 255.0
        if bg_intensity <= 15.0:
            bg_intensity = 255.0

        # 2. Extract inner circular ROI
        x1 = max(0, cx - inner_r)
        x2 = min(w_img, cx + inner_r + 1)
        y1 = max(0, cy - inner_r)
        y2 = min(h_img, cy + inner_r + 1)

        roi_inner = gray_img[y1:y2, x1:x2]
        if roi_inner.size == 0:
            return {
                "mean_contrast": 0.0,
                "dark_pixel_ratio": 0.0,
                "max_cc_area": 0,
                "total_ink_px": 0,
                "centroid": None,
                "inner_radius": inner_r,
                "total_inner_pixels": 0,
            }

        mask = np.zeros(roi_inner.shape, dtype=np.uint8)
        cv2.circle(mask, (cx - x1, cy - y1), inner_r, 255, -1)
        inner_pixels = roi_inner[mask > 0]
        total_inner = len(inner_pixels)
        if total_inner == 0:
            return {
                "mean_contrast": 0.0,
                "dark_pixel_ratio": 0.0,
                "max_cc_area": 0,
                "total_ink_px": 0,
                "centroid": None,
                "inner_radius": inner_r,
                "total_inner_pixels": 0,
            }

        mean_inner = float(np.mean(inner_pixels))
        mean_contrast = max(0.0, float((bg_intensity - mean_inner) / bg_intensity))

        # 3. Ink pixel thresholding
        ink_thresh = 0.15 if self.sensitivity == "HIGH" else 0.18 if self.sensitivity == "NORMAL" else 0.22
        rel_diff = np.maximum(0.0, (bg_intensity - roi_inner.astype(np.float32)) / bg_intensity)
        ink_mask = np.zeros_like(roi_inner, dtype=np.uint8)
        ink_mask[(mask > 0) & (rel_diff >= ink_thresh)] = 255

        total_ink_px = int(np.sum(ink_mask > 0))
        dark_pixel_ratio = float(total_ink_px / float(total_inner))

        # 4. Connected Component Analysis for small dots / strokes
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(ink_mask, connectivity=8)
        max_cc_area = 0
        mark_centroid = None
        if num_labels > 1:
            areas = stats[1:, cv2.CC_STAT_AREA]
            max_idx = int(np.argmax(areas)) + 1
            max_cc_area = int(stats[max_idx, cv2.CC_STAT_AREA])
            mark_centroid = (float(centroids[max_idx][0] + x1), float(centroids[max_idx][1] + y1))

        return {
            "mean_contrast": round(float(np.clip(mean_contrast, 0.0, 1.0)), 4),
            "dark_pixel_ratio": round(float(dark_pixel_ratio), 4),
            "max_cc_area": max_cc_area,
            "total_ink_px": total_ink_px,
            "centroid": mark_centroid,
            "inner_radius": inner_r,
            "total_inner_pixels": total_inner,
        }

    def measure_bubble_ink_density(
        self, gray_img: np.ndarray, cx: int, cy: int, radius: int
    ) -> float:
        """
        Legacy contrast measurement.
        Returns the mean contrast inside the inner bubble region.
        """
        feats = self.evaluate_bubble_features(gray_img, cx, cy, radius)
        return feats["mean_contrast"]

    def detect_roll_number(self, gray_img: np.ndarray) -> Tuple[Optional[str], float]:
        """Detects roll number if the template includes roll bubbles; otherwise returns None."""
        if not self.layout.roll_bubbles:
            return None, 0.0

        by_col: Dict[int, List[Any]] = {}
        for rb in self.layout.roll_bubbles:
            by_col.setdefault(rb.column_index, []).append(rb)

        col_digits = []
        confidences = []

        for col_idx in range(self.layout.roll_digit_count):
            bubbles = by_col.get(col_idx, [])
            densities = [
                (b.digit, self.measure_bubble_ink_density(gray_img, b.cx, b.cy, b.radius))
                for b in bubbles
            ]
            densities.sort(key=lambda x: x[1], reverse=True)

            top_digit, top_density = densities[0]
            runner_up_digit, runner_up_density = densities[1] if len(densities) > 1 else (None, 0.0)

            if top_density >= self.fill_threshold and (top_density - runner_up_density) >= self.contrast_margin:
                col_digits.append(str(top_digit))
                confidences.append(min(1.0, (top_density - runner_up_density) / 0.3))
            else:
                col_digits.append("?")
                confidences.append(0.3)

        detected_roll = "".join(col_digits)
        avg_conf = float(np.mean(confidences)) if confidences else 0.0
        return detected_roll, round(avg_conf, 2)

    def detect_vidyakashi_candidate_info(
        self, raw_or_rectified_img: np.ndarray
    ) -> Tuple[Optional[str], Optional[str], float]:
        """
        Extracts Student Roll No. and Student Name from the candidate header box
        using cross-platform HTREngine with zero guessing and robust handwriting recognition.
        """
        try:
            tmpl_type = getattr(self.layout, "template_type", "vidyakashi_official")
            details = HTREngine.extract_candidate_details(
                canonical_img=raw_or_rectified_img,
                template_type=tmpl_type,
            )
            cand_roll = details.get("student_roll")
            cand_name = details.get("student_name")
            cand_conf = max(details.get("roll_confidence", 0.0), details.get("name_confidence", 0.0))
            return cand_roll, cand_name, cand_conf
        except Exception:
            return None, None, 0.0

    def detect_qr_code(self, img: np.ndarray) -> Optional[str]:
        """Attempts to read embedded QR code for sheet identifier verification."""
        try:
            detector = cv2.QRCodeDetector()
            val, pts, _ = detector.detectAndDecode(img)
            if val and val.strip():
                return val.strip()
        except Exception:
            pass
        return None

    def classify_question_bubbles(
        self,
        options_data: Dict[str, Dict[str, Any]],
        image_aligned: bool = True,
        is_blurred: bool = False,
    ) -> Tuple[str, float, Dict[str, bool]]:
        """
        Evaluates all option bubbles for a single question according to calibrated rules:
        - Exactly one bubble containing a detectable mark: classify that option as selected answer.
        - No detectable marks in any bubble: classify as BLANK.
        - Detectable marks in two or more bubbles: classify as MULTIPLE.
        - Image quality or alignment makes result unreliable: classify as REVIEW.
        Returns: (classification, confidence, mark_flags)
        """
        if not image_aligned or is_blurred:
            mark_flags = {opt: False for opt in options_data}
            return "REVIEW", 0.35, mark_flags

        # Thresholds based on sensitivity profile (scaled to bubble area)
        base_cc_thresh = 6 if self.sensitivity == "HIGH" else 8 if self.sensitivity == "NORMAL" else 18
        sample_total_px = max((d.get("total_inner_pixels", 700) for d in options_data.values()), default=700)
        area_scale = min(1.0, max(0.5, float(sample_total_px) / 700.0))
        min_cc_thresh = max(4, int(round(base_cc_thresh * area_scale)))
        min_dark_ratio = 0.010 if self.sensitivity == "HIGH" else 0.012 if self.sensitivity == "NORMAL" else 0.035

        all_contrasts = [d["mean_contrast"] for d in options_data.values()]
        all_dark_ratios = [d["dark_pixel_ratio"] for d in options_data.values()]
        min_contrast = min(all_contrasts)
        min_dark_ratio_q = min(all_dark_ratios)
        max_contrast = max(all_contrasts)

        has_dominant_fill = max_contrast >= 0.35 or max(all_dark_ratios) >= 0.30

        mark_flags: Dict[str, bool] = {}

        for opt, data in options_data.items():
            c = data["mean_contrast"]
            dr = data["dark_pixel_ratio"]
            cc = data["max_cc_area"]

            is_mark = False

            if c >= 0.35 or dr >= 0.30:
                is_mark = True
            elif cc < min_cc_thresh and c < 0.08 and dr < min_dark_ratio:
                # Blank bubble or isolated dust speckle
                is_mark = False
            elif has_dominant_fill:
                # With a dominant solid fill, unshaded letters/noise with contrast < 0.18 are not marked
                if c >= 0.28 or (c - min_contrast) >= 0.20:
                    is_mark = True
                else:
                    is_mark = False
            else:
                # No bubble is dominantly filled (evaluating dots, strokes, faint marks)
                if min_contrast < 0.04 and min_dark_ratio_q < 0.02:
                    # Clean empty bubbles
                    if cc >= min_cc_thresh and dr >= min_dark_ratio:
                        is_mark = True
                    elif c >= 0.12 or dr >= 0.04:
                        is_mark = True
                else:
                    # Bubbles with printed letters inside
                    if (c - min_contrast) >= 0.14 or (dr - min_dark_ratio_q) >= 0.12:
                        is_mark = True
                    elif c >= 0.25:
                        is_mark = True

            mark_flags[opt] = is_mark

        marked_opts = [opt for opt, flag in mark_flags.items() if flag]

        if len(marked_opts) == 0:
            if max_contrast >= 0.18:
                return "REVIEW", 0.45, mark_flags
            return "BLANK", 0.98, mark_flags

        elif len(marked_opts) == 1:
            selected = marked_opts[0]
            sel_c = options_data[selected]["mean_contrast"]
            other_c = [d["mean_contrast"] for o, d in options_data.items() if o != selected]
            runner_up = max(other_c) if other_c else 0.0
            confidence = round(min(1.0, max(0.70, 0.70 + (sel_c - runner_up))), 2)
            return selected, confidence, mark_flags

        else:
            sorted_marked = sorted(marked_opts, key=lambda o: options_data[o]["mean_contrast"], reverse=True)
            top_c = options_data[sorted_marked[0]]["mean_contrast"]
            sec_c = options_data[sorted_marked[1]]["mean_contrast"]

            # If one is heavily filled and second is an erasure (< 0.22) with large gap, flag REVIEW
            if top_c >= 0.65 and sec_c < 0.22 and (top_c - sec_c) >= 0.45:
                return "REVIEW", 0.50, mark_flags

            return "MULTIPLE", 0.92, mark_flags

    def generate_visual_diagnostic(
        self,
        rectified_img: np.ndarray,
        questions: Dict[int, Dict[str, Any]],
        markers_detected: bool,
        answer_key: Optional[Dict[str, str]] = None,
        detected_roll: Optional[str] = None,
        detected_name: Optional[str] = None,
    ) -> np.ndarray:
        """
        Creates an annotated visual OMR correction & diagnostic image showing:
        - Registered sheet boundary & corner markers
        - Expected position and measured inner region of every bubble
        - Exact detected mark locations
        - When answer_key is provided:
          * CORRECT answers: Green circle + Green checkmark tag (e.g. "Q01:A OK")
          * WRONG answers: Red circle with Red X cross on student's bubble + Blue ring on the Correct Answer bubble + Red tag ("Q10:C X(B)")
          * BLANK answers: Orange/Blue ring on the Correct Answer bubble
        """
        diag = rectified_img.copy()

        # 1. Draw Corner Marker Expectations (Cyan boxes)
        for name, (cx, cy) in self.layout.markers.items():
            half = self.layout.marker_size // 2
            cv2.rectangle(
                diag,
                (cx - half, cy - half),
                (cx + half, cy + half),
                (255, 255, 0),  # Cyan
                2
            )
            cv2.putText(
                diag,
                name.replace("_", " ").upper(),
                (cx - half, cy - half - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 0),
                1
            )

        correct_count = 0
        wrong_count = 0
        blank_count = 0
        multiple_count = 0

        # 2. Draw Every Question's Bubbles, Marks, and Correction vs Answer Key
        for q_num, opt_map in self.layout.bubbles.items():
            q_res = questions.get(q_num, {})
            classification = q_res.get("classification", "BLANK")
            densities = q_res.get("densities", {})
            opt_features = q_res.get("features", {})
            mark_flags = q_res.get("mark_flags", {})

            correct_opt = None
            if answer_key:
                raw_k = answer_key.get(str(q_num)) or answer_key.get(q_num)
                if raw_k:
                    correct_opt = str(raw_k).upper().strip()

            is_correct = False
            is_wrong = False
            if classification in ("A", "B", "C", "D"):
                if correct_opt in ("A", "B", "C", "D"):
                    if classification == correct_opt:
                        is_correct = True
                        correct_count += 1
                    else:
                        is_wrong = True
                        wrong_count += 1
                else:
                    is_correct = True
                    correct_count += 1
            elif classification == "BLANK":
                blank_count += 1
            else:
                multiple_count += 1
                if correct_opt in ("A", "B", "C", "D"):
                    wrong_count += 1

            for opt, bubble in opt_map.items():
                cx, cy, r = bubble.cx, bubble.cy, bubble.radius
                inner_r = max(3, int(r * 0.65))
                density = densities.get(opt, 0.0)
                b_feat = opt_features.get(opt, {})
                is_marked = mark_flags.get(opt, False)
                centroid = b_feat.get("centroid")

                # Bubble outline (thin circle)
                cv2.circle(diag, (cx, cy), r, (220, 180, 100), 1)
                cv2.circle(diag, (cx, cy), inner_r, (190, 190, 190), 1)

                if is_marked and centroid is not None:
                    mx, my = int(centroid[0]), int(centroid[1])
                    cv2.circle(diag, (mx, my), 3, (255, 255, 0), -1)

                # Color-code based on Answer Key correction
                if classification == opt:
                    if is_wrong:
                        # WRONG student answer: Red circle + Red X cross over bubble
                        cv2.circle(diag, (cx, cy), r + 3, (0, 0, 235), 3)
                        d = int(r * 0.65)
                        cv2.line(diag, (cx - d, cy - d), (cx + d, cy + d), (0, 0, 235), 3)
                        cv2.line(diag, (cx - d, cy + d), (cx + d, cy - d), (0, 0, 235), 3)
                    else:
                        # CORRECT student answer: Strong Green ring + center dot
                        cv2.circle(diag, (cx, cy), r + 3, (0, 190, 0), 3)
                        cv2.circle(diag, (cx, cy), 4, (0, 190, 0), -1)
                elif correct_opt == opt and (is_wrong or classification in ("BLANK", "MULTIPLE")):
                    # Show the actual correct option in Blue/Cyan ring when student got it wrong or left blank
                    cv2.circle(diag, (cx, cy), r + 3, (230, 110, 0), 3)
                elif classification == "MULTIPLE" and is_marked:
                    cv2.circle(diag, (cx, cy), r + 2, (0, 0, 255), 3)
                elif classification == "REVIEW" and (is_marked or density >= 0.15):
                    cv2.circle(diag, (cx, cy), r + 2, (0, 140, 255), 3)

            # Draw question correction label next to row
            first_b = next(iter(opt_map.values()))
            if is_wrong and correct_opt:
                tag_color = (0, 0, 230)  # Red for wrong
                q_tag = f"{classification} X (Key:{correct_opt})"
            elif is_correct:
                tag_color = (0, 155, 0)  # Green for correct
                q_tag = f"{classification} OK"
            elif classification == "BLANK" and correct_opt:
                tag_color = (180, 100, 0)
                q_tag = f"- (Key:{correct_opt})"
            else:
                tag_color = (0, 0, 220) if classification == "MULTIPLE" else (120, 120, 120)
                q_tag = f"{classification}"

            cv2.putText(
                diag,
                q_tag,
                (first_b.cx - 72, first_b.cy + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                tag_color,
                1
            )

        # 3. Top Banner Header Summary (OMR Correction Stamp)
        cv2.rectangle(diag, (0, 0), (CANONICAL_WIDTH, 48), (25, 30, 40), -1)
        total_q = len(self.layout.bubbles)
        cand_label = ""
        if detected_name or detected_roll:
            cand_label = f" | {detected_name or 'Student'} ({detected_roll or 'N/A'})"
        if answer_key:
            pct = round((correct_count / max(1, total_q)) * 100.0, 1)
            status_txt = f"OMR CORRECTION{cand_label} | SCORE: {correct_count}/{total_q} ({pct}%)"
            cv2.putText(diag, status_txt, (18, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (100, 255, 140), 2)
            summary_txt = f"Correct: {correct_count} | Wrong: {wrong_count} | Blank: {blank_count}"
            cv2.putText(diag, summary_txt, (CANONICAL_WIDTH - 520, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2)
        else:
            status_txt = f"OMR DIAGNOSTIC{cand_label} | Alignment: {'OK' if markers_detected else 'FALLBACK'}"
            cv2.putText(diag, status_txt, (18, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
            summary_txt = f"Detected: {correct_count} | Blank: {blank_count} | Multiple: {multiple_count}"
            cv2.putText(diag, summary_txt, (CANONICAL_WIDTH - 520, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (100, 230, 255), 1)

        return diag

    def process_omr_sheet(
        self,
        img: np.ndarray,
        answer_key: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes the complete, calibrated OMR detection and correction pipeline on the image:
        1. Rectifies perspective and aligns with canonical geometry
        2. Detects blur / image quality
        3. Detects roll number (if applicable) and QR identifier
        4. Evaluates question bubbles with sensitive small-mark detection
        5. Classifies each question using calibrated decision rules
        6. Generates the visual OMR correction & diagnostic overlay (marking Right vs Wrong against answer_key)
        """
        rectified, markers_detected = self.rectify_image(img)
        alignment_info = self.validate_sheet_alignment_and_template(rectified, markers_detected)
        gray = cv2.cvtColor(rectified, cv2.COLOR_BGR2GRAY) if len(rectified.shape) == 3 else rectified.copy()

        # Check image blur (Laplacian variance)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        is_blurred = lap_var < 35.0

        # 1. Student Identification (Roll No. & Student Name via HTREngine)
        bubble_roll, bubble_conf = self.detect_roll_number(gray)
        tmpl_type = getattr(self.layout, "template_type", "vidyakashi_official")
        htr_details = HTREngine.extract_candidate_details(
            canonical_img=rectified,
            template_type=tmpl_type,
            bubble_roll=bubble_roll,
        )
        detected_roll = htr_details.get("student_roll") or bubble_roll
        roll_conf = htr_details.get("roll_confidence", bubble_conf)
        detected_name = htr_details.get("student_name")
        name_conf = htr_details.get("name_confidence", 0.0)
        name_crop_url = htr_details.get("name_crop_url")
        details_need_review = htr_details.get("needs_review", False)
        qr_identifier = self.detect_qr_code(rectified)

        # 2. Evaluate Question Bubbles
        question_results: Dict[int, Dict[str, Any]] = {}
        uncertain_count = 0

        for q_num, opt_map in self.layout.bubbles.items():
            options_data: Dict[str, Dict[str, Any]] = {}
            densities: Dict[str, float] = {}

            for opt, bubble in opt_map.items():
                b_feats = self.evaluate_bubble_features(gray, bubble.cx, bubble.cy, bubble.radius)
                options_data[opt] = b_feats
                densities[opt] = b_feats["mean_contrast"]

            classification, confidence, mark_flags = self.classify_question_bubbles(
                options_data=options_data,
                image_aligned=markers_detected,
                is_blurred=is_blurred,
            )

            if classification == "REVIEW":
                uncertain_count += 1

            question_results[q_num] = {
                "classification": classification,
                "confidence": confidence,
                "densities": densities,
                "features": options_data,
                "mark_flags": mark_flags,
            }

        # 3. Generate Visual Diagnostic / Correction Image
        diagnostic_img = self.generate_visual_diagnostic(
            rectified_img=rectified,
            questions=question_results,
            markers_detected=markers_detected,
            answer_key=answer_key,
            detected_roll=detected_roll,
            detected_name=detected_name,
        )

        return {
            "markers_detected": markers_detected,
            "alignment_info": alignment_info,
            "detected_roll_number": detected_roll,
            "detected_student_name": detected_name,
            "roll_confidence": roll_conf,
            "name_confidence": name_conf,
            "name_crop_url": name_crop_url,
            "details_need_review": details_need_review,
            "sheet_identifier": qr_identifier,
            "questions": question_results,
            "uncertain_questions_count": uncertain_count,
            "rectified_image": rectified,
            "diagnostic_image": diagnostic_img,
            "sensitivity": self.sensitivity,
            "is_blurred": is_blurred,
            "image_quality_score": round(lap_var, 1),
        }
