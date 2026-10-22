import io
import qrcode
from typing import Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from backend.app.omr.layout import (
    OMRLayoutConfig,
    CANONICAL_WIDTH,
    CANONICAL_HEIGHT,
    A4_POINTS_WIDTH,
    A4_POINTS_HEIGHT,
)


class OMRSheetGenerator:
    def __init__(self, layout: Optional[OMRLayoutConfig] = None):
        self.layout = layout or OMRLayoutConfig(question_count=100)
        self.scale_x = A4_POINTS_WIDTH / CANONICAL_WIDTH
        self.scale_y = A4_POINTS_HEIGHT / CANONICAL_HEIGHT

    def _pt_x(self, px: float) -> float:
        return px * self.scale_x

    def _pt_y(self, py: float) -> float:
        return A4_POINTS_HEIGHT - (py * self.scale_y)

    def _pt_radius(self, pr: float) -> float:
        return pr * self.scale_x

    def generate_pdf(
        self,
        exam_title: str,
        exam_code: str,
        subject: str = "General",
        class_grade: str = "Class 10",
        exam_date: str = "2026-10-21",
        sheet_id: Optional[str] = None
    ) -> bytes:
        """Generates a geometrically aligned A4 OMR answer sheet PDF."""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        c.setTitle(f"OMR Answer Sheet - {exam_code}")
        
        # 1. Draw Corner Registration Markers (Solid black squares)
        half_marker = self.layout.marker_size / 2.0
        c.setFillColor(colors.black)
        c.setStrokeColor(colors.black)
        
        for name, (cx, cy) in self.layout.markers.items():
            rx = self._pt_x(cx - half_marker)
            ry = self._pt_y(cy + half_marker)
            rw = self._pt_x(self.layout.marker_size)
            rh = self.scale_y * self.layout.marker_size
            c.rect(rx, ry, rw, rh, fill=1, stroke=0)

        # 2. Draw Header Details
        c.setFont("Helvetica-Bold", 14)
        c.drawString(self._pt_x(120), self._pt_y(130), exam_title)
        
        c.setFont("Helvetica", 9)
        c.drawString(self._pt_x(120), self._pt_y(155), f"Exam Code: {exam_code}  |  Subject: {subject}  |  Class: {class_grade}")
        c.drawString(self._pt_x(120), self._pt_y(175), f"Date: {exam_date}  |  Questions: {self.layout.question_count}  |  Print Scale: 100%")

        # Student Name Entry Field
        c.setLineWidth(0.8)
        c.drawString(self._pt_x(120), self._pt_y(210), "STUDENT NAME:")
        c.line(self._pt_x(220), self._pt_y(212), self._pt_x(710), self._pt_y(212))

        # Instructions Box
        c.setFont("Helvetica-Bold", 8)
        c.drawString(self._pt_x(120), self._pt_y(240), "IMPORTANT INSTRUCTIONS:")
        c.setFont("Helvetica", 7.5)
        instructions = [
            "- Use dark blue or black ballpoint pen only. Do NOT use gel pens or pencil.",
            "- Completely darken the bubble corresponding to your answer.",
            "- Do not make stray marks on the sheet or fold / wrinkle the paper.",
            "- Ensure the 4 corner registration squares are clearly printed and unsoiled."
        ]
        y_inst = 258
        for line in instructions:
            c.drawString(self._pt_x(120), self._pt_y(y_inst), line)
            y_inst += 16

        # Draw Sample Fill Demonstration
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(self._pt_x(120), self._pt_y(340), "CORRECT: ")
        correct_bx = self._pt_x(185)
        correct_by = self._pt_y(337)
        c.circle(correct_bx, correct_by, self._pt_radius(self.layout.bubble_radius - 2), fill=1, stroke=1)
        
        c.setFillColor(colors.black)
        c.drawString(self._pt_x(230), self._pt_y(340), "WRONG:  [X]   [/]   [.]")

        # 3. Draw Student Roll Number Grid
        c.setFont("Helvetica-Bold", 8)
        c.drawString(self._pt_x(760), self._pt_y(140), "ROLL NUMBER")
        
        # Draw box headers for the 6 roll number digits
        for col in range(self.layout.roll_digit_count):
            box_x = self._pt_x(760 + (col * 38) - 10)
            box_y = self._pt_y(162)
            c.rect(box_x, box_y, self._pt_x(20), self.scale_y * 16, fill=0, stroke=1)

        # Draw Roll Number Bubbles
        c.setFont("Helvetica", 6)
        for r_bubble in self.layout.roll_bubbles:
            bx = self._pt_x(r_bubble.cx)
            by = self._pt_y(r_bubble.cy)
            br = self._pt_radius(r_bubble.radius)
            c.setLineWidth(0.6)
            c.circle(bx, by, br, fill=0, stroke=1)
            c.drawString(bx - 1.8, by - 2.2, str(r_bubble.digit))

        # 4. Draw QR Code
        qr_content = f"{exam_code}:{sheet_id or 'SHEET-0001'}"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=1
        )
        qr.add_data(qr_content)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        
        qr_x = self._pt_x(self.layout.qr_box["x"])
        qr_y = self._pt_y(self.layout.qr_box["y"] + self.layout.qr_box["height"])
        qr_w = self._pt_x(self.layout.qr_box["width"])
        qr_h = self.scale_y * self.layout.qr_box["height"]
        c.drawImage(ImageReader(img_buffer), qr_x, qr_y, width=qr_w, height=qr_h)

        # Draw Dividing Line
        c.setLineWidth(1.0)
        c.line(self._pt_x(100), self._pt_y(410), self._pt_x(self.layout.width - 100), self._pt_y(410))

        # 5. Draw Question Bubbles Grid
        c.setFont("Helvetica-Bold", 8)
        for q_num, options in self.layout.bubbles.items():
            first_opt = next(iter(options.values()))
            q_label_x = self._pt_x(first_opt.cx - 55)
            q_label_y = self._pt_y(first_opt.cy + 3)
            c.setFillColor(colors.black)
            c.drawString(q_label_x, q_label_y, f"{q_num:02d}.")

            for opt_key, bubble in options.items():
                bx = self._pt_x(bubble.cx)
                by = self._pt_y(bubble.cy)
                br = self._pt_radius(bubble.radius)
                
                # Draw bubble outline
                c.setLineWidth(0.7)
                c.circle(bx, by, br, fill=0, stroke=1)
                
                # Centered option text
                c.setFont("Helvetica", 7)
                c.drawString(bx - 2.5, by - 2.5, opt_key)

        # 6. Draw Footer
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.gray)
        footer_text = f"Digital OMR Cloud | Template: OMR-A4-{self.layout.question_count}Q-V1 | Always Print at 100% Scale (Do Not Fit/Shrink)"
        c.drawCentredString(A4_POINTS_WIDTH / 2.0, self._pt_y(self.layout.height - 40), footer_text)

        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
