"""
Vidyakashi Study Circle — Authoritative Official OMR Sheet Generator (Image & PDF).
Uses the official Vidyakashi 4-Column (100Q) OMR Answer Sheet template and
OMRLayoutConfig(template_type="vidyakashi_official") coordinates to guarantee
100% geometric alignment with the OpenCV OMR detector.
"""
import io
import os
import cv2
import numpy as np
from typing import Optional, Dict, Any, Tuple
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from backend.app.omr.layout import (
    OMRLayoutConfig,
    CANONICAL_WIDTH,
    CANONICAL_HEIGHT,
)

PAGE_W, PAGE_H = A4

_OFFICIAL_TEMPLATE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "assets", "vidyakashi_official_omr.jpg")
)


class VidyakashiOMRGenerator:
    """
    Generates blank and pre-filled official Vidyakashi Study Circle OMR sheets
    as both high-resolution canonical images (1654 x 2338) and print-ready A4 PDFs.
    """

    def __init__(self, question_count: int = 100):
        self.question_count = max(1, min(100, question_count))
        self.layout = OMRLayoutConfig(
            question_count=self.question_count,
            template_type="vidyakashi_official",
        )

    def generate_image(
        self,
        exam_title: str = "",
        exam_code: str = "",
        subject: str = "",
        class_grade: str = "",
        exam_date: str = "",
        sheet_id: Optional[str] = None,
        pre_filled_answers: Optional[Dict[int, str]] = None,
        student_name: str = "",
        student_roll: str = "",
        mark_style: str = "solid",
    ) -> np.ndarray:
        """
        Renders the official Vidyakashi OMR sheet at canonical resolution (1654 x 2338).
        If pre_filled_answers or student/exam details are provided, draws them accurately
        onto the sheet.
        """
        if os.path.exists(_OFFICIAL_TEMPLATE_PATH):
            raw = cv2.imread(_OFFICIAL_TEMPLATE_PATH, cv2.IMREAD_COLOR)
            if raw is not None:
                sheet = cv2.resize(
                    raw,
                    (CANONICAL_WIDTH, CANONICAL_HEIGHT),
                    interpolation=cv2.INTER_LINEAR,
                )
            else:
                sheet = np.ones((CANONICAL_HEIGHT, CANONICAL_WIDTH, 3), dtype=np.uint8) * 255
        else:
            sheet = np.ones((CANONICAL_HEIGHT, CANONICAL_WIDTH, 3), dtype=np.uint8) * 255

        # Draw student & exam metadata only when pre_filled_answers or student_name is requested
        if pre_filled_answers or student_name or student_roll:
            ink_color = (95, 25, 15)  # Realistic dark blue/black ballpoint pen (BGR)

            if student_name:
                cv2.putText(
                    sheet,
                    student_name[:28],
                    (240, 478),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75,
                    ink_color,
                    2,
                    cv2.LINE_AA,
                )
            if class_grade:
                cv2.putText(
                    sheet,
                    f"{class_grade} ({subject})" if subject else class_grade,
                    (240, 545),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.70,
                    ink_color,
                    2,
                    cv2.LINE_AA,
                )
            if exam_date:
                cv2.putText(
                    sheet,
                    exam_date,
                    (240, 610),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.68,
                    ink_color,
                    2,
                    cv2.LINE_AA,
                )
            if exam_title:
                cv2.putText(
                    sheet,
                    f"{exam_title[:24]} ({exam_code})" if exam_code else exam_title[:28],
                    (1090, 478),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    ink_color,
                    2,
                    cv2.LINE_AA,
                )
            if student_roll:
                # 9 Roll No. boxes start around x=1091, width ~56.5 px each, y ~ 596..636
                digits = str(student_roll).strip()[:9]
                for idx, ch in enumerate(digits):
                    bx = int(round(1108 + idx * 56.5))
                    by = 620
                    cv2.putText(
                        sheet,
                        ch,
                        (bx, by),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.75,
                        ink_color,
                        2,
                        cv2.LINE_AA,
                    )

        # Shade / mark answers at the exact calibrated bubble coordinates
        if pre_filled_answers:
            for q_num, opt_val in pre_filled_answers.items():
                q_int = int(q_num)
                if q_int not in self.layout.bubbles:
                    continue
                opt_str = str(opt_val).upper().strip()
                if opt_str not in self.layout.bubbles[q_int]:
                    continue

                b = self.layout.bubbles[q_int][opt_str]
                cx, cy, r = b.cx, b.cy, b.radius

                if mark_style == "dot":
                    cv2.circle(sheet, (cx, cy), 4, (20, 20, 25), -1, cv2.LINE_AA)
                elif mark_style == "tick":
                    cv2.line(sheet, (cx - 6, cy), (cx - 1, cy + 5), (20, 20, 25), 3, cv2.LINE_AA)
                    cv2.line(sheet, (cx - 1, cy + 5), (cx + 7, cy - 6), (20, 20, 25), 3, cv2.LINE_AA)
                elif mark_style == "partial":
                    cv2.circle(sheet, (cx, cy), max(5, int(r * 0.55)), (25, 20, 20), -1, cv2.LINE_AA)
                else:
                    # Solid ballpoint pen bubble fill
                    cv2.circle(sheet, (cx, cy), max(8, r - 2), (20, 20, 25), -1, cv2.LINE_AA)

        return sheet

    def generate_image_bytes(
        self,
        ext: str = ".jpg",
        **kwargs: Any,
    ) -> bytes:
        """Generates encoded JPEG or PNG bytes of the official Vidyakashi OMR sheet."""
        sheet = self.generate_image(**kwargs)
        if ext.lower() == ".png":
            ok, buf = cv2.imencode(".png", sheet)
        else:
            ok, buf = cv2.imencode(".jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            raise RuntimeError("Failed to encode Vidyakashi OMR image")
        return buf.tobytes()

    def generate_pdf(
        self,
        exam_title: str = "Chapter Test",
        exam_code: str = "VKS-2026",
        subject: str = "Science",
        class_grade: str = "10th",
        exam_date: str = "2026-10-21",
        sheet_id: Optional[str] = None,
        pre_filled_answers: Optional[Dict[int, str]] = None,
        student_name: str = "",
        student_roll: str = "",
        mark_style: str = "solid",
    ) -> Tuple[bytes, Dict[int, Dict[str, Any]]]:
        """
        Generates a print-ready A4 PDF embedding the official Vidyakashi OMR sheet
        and returns `(pdf_bytes, bubble_coords_dict)`.
        """
        img_bytes = self.generate_image_bytes(
            ext=".jpg",
            exam_title=exam_title,
            exam_code=exam_code,
            subject=subject,
            class_grade=class_grade,
            exam_date=exam_date,
            sheet_id=sheet_id,
            pre_filled_answers=pre_filled_answers,
            student_name=student_name,
            student_roll=student_roll,
            mark_style=mark_style,
        )

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        c.setTitle(f"Vidyakashi OMR Answer Sheet - {exam_code}")

        img_reader = ImageReader(io.BytesIO(img_bytes))
        c.drawImage(
            img_reader,
            0,
            0,
            width=PAGE_W,
            height=PAGE_H,
            preserveAspectRatio=False,
        )

        c.showPage()
        c.save()
        buffer.seek(0)

        bubble_coords: Dict[int, Dict[str, Any]] = {}
        for q, opts in self.layout.bubbles.items():
            bubble_coords[q] = {
                opt: {
                    "cx_px": b.cx,
                    "cy_px": b.cy,
                    "radius_px": b.radius,
                    "cx_pt": round(b.cx_pt, 2),
                    "cy_pt": round(b.cy_pt, 2),
                }
                for opt, b in opts.items()
            }

        return buffer.getvalue(), bubble_coords
