import cv2
import numpy as np
from typing import Tuple, Dict, Any


class ImagePreprocessor:
    # Magic bytes for JPEG, PNG, WEBP
    MAGIC_BYTES = {
        b"\xff\xd8\xff": "image/jpeg",
        b"\x89PNG\r\n\x1a\n": "image/png",
        b"RIFF": "image/webp",
    }

    @staticmethod
    def validate_magic_bytes(data: bytes) -> str:
        """Validates that the file payload starts with legitimate image magic bytes."""
        if len(data) < 12:
            raise ValueError("File is too small to be a valid image")

        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "image/webp"

        raise ValueError("Unsupported or malicious file type: Magic bytes do not match JPEG, PNG, or WebP")

    @staticmethod
    def decode_image(image_bytes: bytes) -> np.ndarray:
        """Safely decodes image bytes into an OpenCV BGR numpy array."""
        ImagePreprocessor.validate_magic_bytes(image_bytes)
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image: Corrupted or invalid image stream")
        return img

    @staticmethod
    def estimate_skew_angle(gray: np.ndarray) -> float:
        """
        Estimates the in-plane tilt/skew angle (in degrees) of the OMR sheet
        using probabilistic Hough line detection on dominant horizontal table/grid lines.
        """
        h, w = gray.shape[:2]
        roi = gray[int(h * 0.10):int(h * 0.90), int(w * 0.08):int(w * 0.92)]
        if roi.size == 0:
            return 0.0

        rh, rw = roi.shape[:2]
        if max(rh, rw) > 1100:
            scale = 1100.0 / float(max(rh, rw))
            roi = cv2.resize(roi, (int(rw * scale), int(rh * scale)), interpolation=cv2.INTER_AREA)
            rh, rw = roi.shape[:2]

        edges = cv2.Canny(roi, 50, 150, apertureSize=3)
        min_line_len = max(40, int(min(rh, rw) * 0.15))
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 900.0, threshold=55, minLineLength=min_line_len, maxLineGap=12
        )
        if lines is None:
            return 0.0

        angles = []
        for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
            dx = float(x2 - x1)
            dy = float(y2 - y1)
            if abs(dx) < 1e-3:
                continue
            angle = float(np.degrees(np.arctan2(dy, dx)))
            # Collect near-horizontal lines within [-35, +35] degrees
            if -35.0 <= angle <= 35.0:
                angles.append(angle)

        if not angles:
            return 0.0

        median_angle = float(np.median(angles))
        return round(median_angle, 2)

    @staticmethod
    def assess_quality(img: np.ndarray) -> Dict[str, Any]:
        """
        Assesses image resolution, blur/sharpness, brightness, contrast,
        shadows/uneven lighting, cropping/visibility, and tilt angle.
        """
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()

        # 1. Resolution Check (supports standard scans, mobile photos, and 682x1024 templates)
        min_dim = min(h, w)
        max_dim = max(h, w)
        resolution_ok = min_dim >= 400 and max_dim >= 600

        # 2. Aspect Ratio / Cropping Check
        # Upright A4 portrait has h/w ~ 1.414 (or 1.50 for 682x1024).
        # 90° rotated A4 landscape has h/w ~ 0.707 and no horizontal top banner.
        aspect_hw = float(h) / float(max(1, w))
        top_strip = gray[int(h * 0.02) : int(h * 0.16), int(w * 0.15) : int(w * 0.85)]
        has_horiz_top_banner = bool(top_strip.size > 0 and float(np.mean(top_strip)) < 165.0)
        if has_horiz_top_banner:
            is_cropped = aspect_hw < 1.15 or aspect_hw > 1.75
        else:
            is_portrait_ok = 1.15 <= aspect_hw <= 1.75
            is_landscape_ok = 0.56 <= aspect_hw <= 0.86
            is_cropped = not (is_portrait_ok or is_landscape_ok)

        # 3. Blur assessment using variance of the Laplacian
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        blur_score = float(laplacian.var())
        is_blurry = blur_score < 40.0

        # 4. Brightness, Contrast, and Glare assessment
        mean_brightness = float(np.mean(gray))
        std_brightness = float(np.std(gray))
        is_low_contrast = std_brightness < 16.0

        # Overexposed pixels (> 250) and underexposed pixels (< 15)
        overexposed_ratio = float(np.sum(gray > 250) / gray.size)
        underexposed_ratio = float(np.sum(gray < 15) / gray.size)

        has_glare = overexposed_ratio > 0.15
        is_too_dark = mean_brightness < 85.0

        # 5. Shadows and Uneven Lighting Check (3x3 spatial illumination grid)
        cell_bgs = []
        gh, gw = max(1, h // 3), max(1, w // 3)
        for r_idx in range(3):
            for c_idx in range(3):
                cell = gray[r_idx * gh : (r_idx + 1) * gh, c_idx * gw : (c_idx + 1) * gw]
                if cell.size > 0:
                    cell_bgs.append(float(np.percentile(cell, 88)))
        shadow_spread = float(max(cell_bgs) - min(cell_bgs)) if cell_bgs else 0.0
        min_cell_bg = float(min(cell_bgs)) if cell_bgs else 255.0
        has_shadows = shadow_spread > 35.0
        is_severe_shadow = shadow_spread > 165.0 and min_cell_bg < 40.0

        # 6. Tilt / Rotation Check
        tilt_angle_deg = ImagePreprocessor.estimate_skew_angle(gray)
        is_tilted = abs(tilt_angle_deg) >= 1.5
        is_landscape = w > int(h * 1.12)

        # Quality verdict
        is_acceptable = (
            resolution_ok
            and not is_blurry
            and not is_too_dark
            and not is_low_contrast
            and not is_severe_shadow
            and not is_cropped
        )

        # Clear human-readable validation message
        validation_message = "Image quality is suitable for evaluation."
        if is_cropped:
            validation_message = "Part of the answer sheet is missing. Upload the complete sheet."
        elif is_too_dark or not resolution_ok or is_low_contrast or is_severe_shadow:
            validation_message = "Image quality is insufficient for reliable evaluation."
        elif is_blurry:
            validation_message = "The image is blurry. Please take another photo."
        elif is_tilted or is_landscape:
            validation_message = "The OMR sheet is tilted. Aligning the image..."

        diagnostics = {
            "width": w,
            "height": h,
            "resolution_ok": resolution_ok,
            "is_cropped": is_cropped,
            "blur_score": round(blur_score, 2),
            "is_blurry": is_blurry,
            "mean_brightness": round(mean_brightness, 2),
            "std_brightness": round(std_brightness, 2),
            "is_low_contrast": is_low_contrast,
            "overexposed_ratio": round(overexposed_ratio, 4),
            "underexposed_ratio": round(underexposed_ratio, 4),
            "has_glare": has_glare,
            "has_shadows": has_shadows,
            "shadow_spread": round(shadow_spread, 2),
            "is_severe_shadow": is_severe_shadow,
            "is_too_dark": is_too_dark,
            "tilt_angle_deg": tilt_angle_deg,
            "is_tilted": is_tilted,
            "is_landscape": is_landscape,
            "is_acceptable": is_acceptable,
            "validation_message": validation_message,
            "quality_status": "GOOD" if (is_acceptable and not has_glare and not has_shadows) else ("WARNING" if is_acceptable else "FAIL"),
        }
        return diagnostics
