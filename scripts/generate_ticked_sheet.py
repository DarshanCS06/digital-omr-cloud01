import os, shutil
import pypdfium2 as pdfium
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

base_dir = r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud"
out_dir = os.path.join(base_dir, "generated")
artifact_dir = r"C:\Users\rahul\.gemini\antigravity\brain\f9891136-5e91-4fcb-baf2-cf8007c6bf8c"
header_crop_path = os.path.join(out_dir, "vidyakashi_header.png")

PAGE_W, PAGE_H = A4

def pt_y(y):
    return PAGE_H - y

# ── Sample answers key (cyclic A B C D A B C D … for 25 questions) ──────────
ANSWERS = {
     1:'A',  2:'B',  3:'C',  4:'D',  5:'A',
     6:'B',  7:'C',  8:'D',  9:'A', 10:'B',
    11:'C', 12:'D', 13:'A', 14:'B', 15:'C',
    16:'D', 17:'A', 18:'B', 19:'C', 20:'D',
    21:'A', 22:'B', 23:'C', 24:'D', 25:'A',
}

STUDENT_NAME  = "Rahul Kumar"
STUDENT_ROLL  = "1023456"
STUDENT_CLASS = "10th  Sec-A"
STUDENT_SUBJ  = "Science"
TEST_NAME     = "Chapter Test - Unit 3"
TEST_DATE     = "21 / 10 / 2026"
TEST_TIME     = "10:00 AM"

def generate_ticked_pdf():
    pdf_path = os.path.join(out_dir, "Vidyakashi_Ticked_25Q.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    c.setTitle("Vidyakashi Study Circle - OMR Sheet (Sample Filled)")

    # ── Corner registration markers ──────────────────────────────────────────
    c.setFillColor(colors.black)
    c.setStrokeColor(colors.black)
    c.rect(14, pt_y(22), 24, 14, fill=1, stroke=0)
    c.rect(PAGE_W - 14 - 24, pt_y(22), 24, 14, fill=1, stroke=0)
    c.rect(14, pt_y(PAGE_H - 14), 24, 14, fill=1, stroke=0)
    c.rect(PAGE_W - 14 - 24, pt_y(PAGE_H - 14), 24, 14, fill=1, stroke=0)

    # ── Header banner ────────────────────────────────────────────────────────
    banner_x = 24; banner_y = 28; banner_w = PAGE_W - 48; banner_h = 100
    if os.path.exists(header_crop_path):
        c.drawImage(ImageReader(header_crop_path),
                    banner_x, pt_y(banner_y + banner_h),
                    width=banner_w, height=banner_h)
    else:
        c.setFillColor(colors.black)
        c.rect(banner_x, pt_y(banner_y + banner_h), banner_w, banner_h, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(PAGE_W / 2, pt_y(banner_y + 40), "VIDYAKASHI STUDY CIRCLE")

    # ── Candidate details box ────────────────────────────────────────────────
    cand_y = 135; cand_h = 88
    c.setLineWidth(1.2)
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.white)
    c.roundRect(banner_x, pt_y(cand_y + cand_h), banner_w, cand_h, 6, fill=0, stroke=1)
    mid_split_x = banner_x + (banner_w * 0.52)
    c.line(mid_split_x, pt_y(cand_y), mid_split_x, pt_y(cand_y + cand_h))

    # Left: Test Name / Date / Time labels
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 10)
    c.drawString(banner_x + 12, pt_y(cand_y + 24), "Test Name  :")
    c.line(banner_x + 85, pt_y(cand_y + 24), mid_split_x - 12, pt_y(cand_y + 24))
    c.drawString(banner_x + 12, pt_y(cand_y + 52), "Date           :")
    c.line(banner_x + 85, pt_y(cand_y + 52), banner_x + 200, pt_y(cand_y + 52))
    c.drawString(banner_x + 12, pt_y(cand_y + 76), "Time           :")
    c.line(banner_x + 85, pt_y(cand_y + 76), banner_x + 200, pt_y(cand_y + 76))

    # Left: Filled values (blue ink)
    c.setFont("Helvetica", 9); c.setFillColor(colors.HexColor("#1a1a8c"))
    c.drawString(banner_x + 90, pt_y(cand_y + 22), TEST_NAME)
    c.drawString(banner_x + 90, pt_y(cand_y + 50), TEST_DATE)
    c.drawString(banner_x + 90, pt_y(cand_y + 74), TEST_TIME)

    # Right: Roll No. with digit boxes
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 10)
    c.drawString(mid_split_x + 12, pt_y(cand_y + 24), "Roll No.   :")
    box_start_x = mid_split_x + 78; box_size = 18
    for b_idx in range(7):
        bx = box_start_x + (b_idx * 21)
        by = cand_y + 11
        c.rect(bx, pt_y(by + box_size), box_size, box_size, fill=0, stroke=1)
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.HexColor("#1a1a8c"))
        c.drawCentredString(bx + 9, pt_y(by + 14), STUDENT_ROLL[b_idx])
        c.setFillColor(colors.black)

    # Right: Name / Class / Subject labels + values
    c.setFont("Helvetica-Bold", 10); c.setFillColor(colors.black)
    c.drawString(mid_split_x + 12, pt_y(cand_y + 44), "Name       :")
    c.line(mid_split_x + 78, pt_y(cand_y + 44), banner_x + banner_w - 12, pt_y(cand_y + 44))
    c.setFont("Helvetica", 9); c.setFillColor(colors.HexColor("#1a1a8c"))
    c.drawString(mid_split_x + 82, pt_y(cand_y + 42), STUDENT_NAME)

    c.setFont("Helvetica-Bold", 10); c.setFillColor(colors.black)
    c.drawString(mid_split_x + 12, pt_y(cand_y + 64), "Class        :")
    c.line(mid_split_x + 78, pt_y(cand_y + 64), banner_x + banner_w - 12, pt_y(cand_y + 64))
    c.setFont("Helvetica", 9); c.setFillColor(colors.HexColor("#1a1a8c"))
    c.drawString(mid_split_x + 82, pt_y(cand_y + 62), STUDENT_CLASS)

    c.setFont("Helvetica-Bold", 10); c.setFillColor(colors.black)
    c.drawString(mid_split_x + 12, pt_y(cand_y + 82), "Subject    :")
    c.line(mid_split_x + 78, pt_y(cand_y + 82), banner_x + banner_w - 12, pt_y(cand_y + 82))
    c.setFont("Helvetica", 9); c.setFillColor(colors.HexColor("#1a1a8c"))
    c.drawString(mid_split_x + 82, pt_y(cand_y + 80), STUDENT_SUBJ)

    # ── Instructions box ─────────────────────────────────────────────────────
    inst_y = 230; inst_h = 92
    c.setFillColor(colors.white); c.setStrokeColor(colors.black)
    c.roundRect(banner_x, pt_y(inst_y + inst_h), banner_w, inst_h, 6, fill=0, stroke=1)
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 9.5)
    c.drawString(banner_x + 12, pt_y(inst_y + 16), "Instructions to Candidates :")
    c.setFont("Helvetica", 7.5)
    instructions = [
        "1.    Use only Blue or Black Ball Point Pen to fill the circles.",
        "2.    Darken only one circle for each question.",
        "3.    Do not make any stray marks on the OMR sheet.",
        "4.    If you want to change an answer, erase completely and darken the new circle.",
        "5.    Each question has four options (A), (B), (C) and (D). Only one option is correct.",
        "6.    Rough work must not be done on this sheet.",
    ]
    cur_iy = inst_y + 28
    for line in instructions:
        c.drawString(banner_x + 12, pt_y(cur_iy), line)
        cur_iy += 10.5

    # Correct / Wrong method demo
    method_box_w = 175; method_box_h = 60
    method_box_x = banner_x + banner_w - method_box_w - 12; method_box_y = inst_y + 24
    c.rect(method_box_x, pt_y(method_box_y + method_box_h), method_box_w, method_box_h, fill=0, stroke=1)
    c.line(method_box_x + 85, pt_y(method_box_y), method_box_x + 85, pt_y(method_box_y + method_box_h))
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(method_box_x + 42, pt_y(method_box_y + 11), "Correct Method")
    c.drawCentredString(method_box_x + 85 + 45, pt_y(method_box_y + 11), "Wrong Methods")
    c.line(method_box_x, pt_y(method_box_y + 16), method_box_x + method_box_w, pt_y(method_box_y + 16))
    demo_opts = ["A", "B", "C", "D"]
    for idx, opt in enumerate(demo_opts):
        bx = method_box_x + 15 + (idx * 18); by = method_box_y + 28
        c.setLineWidth(0.7)
        c.setFillColor(colors.black)
        if idx == 0:
            c.circle(bx, pt_y(by), 5.5, fill=1, stroke=1)
        else:
            c.setFillColor(colors.white)
            c.circle(bx, pt_y(by), 5.5, fill=0, stroke=1)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(bx, pt_y(by + 16), opt)
    for idx, opt in enumerate(demo_opts):
        bx = method_box_x + 98 + (idx * 18); by = method_box_y + 28
        c.setFillColor(colors.white)
        c.circle(bx, pt_y(by), 5.5, fill=0, stroke=1)
        c.setFillColor(colors.black)
        if idx == 0:
            c.line(bx-3, pt_y(by-3), bx+3, pt_y(by+3))
            c.line(bx-3, pt_y(by+3), bx+3, pt_y(by-3))
        elif idx == 1:
            c.line(bx-3, pt_y(by), bx, pt_y(by+3))
            c.line(bx, pt_y(by+3), bx+4, pt_y(by-4))
        elif idx == 2:
            c.wedge(bx-5.5, pt_y(by+5.5), bx+5.5, pt_y(by-5.5), 0, 180, fill=1, stroke=0)
        elif idx == 3:
            c.circle(bx, pt_y(by), 2, fill=1, stroke=1)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(bx, pt_y(by + 16), opt)

    # ── Question grid with FILLED bubbles ────────────────────────────────────
    grid_start_y = 332; grid_w = (banner_w - 12) / 2.0
    table_left_x = banner_x; table_right_x = banner_x + grid_w + 12
    row_h = 28.5; col_w_qno = 54; col_w_opt = (grid_w - col_w_qno) / 4.0
    bubble_radius = 8.5

    def draw_omr_table(base_x, start_q, count):
        total_rows = 14
        c.setFillColor(colors.HexColor("#E2E8F0"))
        c.rect(base_x, pt_y(grid_start_y + row_h), grid_w, row_h, fill=1, stroke=1)
        c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 9.5)
        c.drawCentredString(base_x + (col_w_qno / 2.0), pt_y(grid_start_y + 19), "Q. No.")
        for idx, opt in enumerate(["A", "B", "C", "D"]):
            ox = base_x + col_w_qno + (idx * col_w_opt) + (col_w_opt / 2.0)
            c.drawCentredString(ox, pt_y(grid_start_y + 19), opt)
        c.setLineWidth(0.8)
        for r_idx in range(1, total_rows):
            ry = grid_start_y + (r_idx * row_h)
            c.setFillColor(colors.white)
            c.rect(base_x, pt_y(ry + row_h), grid_w, row_h, fill=0, stroke=1)
            c.line(base_x + col_w_qno, pt_y(ry), base_x + col_w_qno, pt_y(ry + row_h))
            for i in range(1, 4):
                lx = base_x + col_w_qno + (i * col_w_opt)
                c.line(lx, pt_y(ry), lx, pt_y(ry + row_h))
            q_num = start_q + r_idx - 1
            if q_num <= 25 and (r_idx - 1) < count:
                c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 9.5)
                c.drawCentredString(base_x + (col_w_qno / 2.0), pt_y(ry + 19), f"{q_num:02d}")
                answered = ANSWERS.get(q_num)
                for idx, opt in enumerate(["A", "B", "C", "D"]):
                    cx = base_x + col_w_qno + (idx * col_w_opt) + (col_w_opt / 2.0)
                    cy = ry + (row_h / 2.0)
                    if opt == answered:
                        c.setFillColor(colors.black)
                        c.circle(cx, pt_y(cy), bubble_radius, fill=1, stroke=1)
                    else:
                        c.setFillColor(colors.white)
                        c.circle(cx, pt_y(cy), bubble_radius, fill=0, stroke=1)

    draw_omr_table(table_left_x, 1, 13)
    draw_omr_table(table_right_x, 14, 12)

    # ── Bottom section ───────────────────────────────────────────────────────
    bot_y = 742; bot_h = 76; bot_split_x = banner_x + (banner_w * 0.52)
    c.roundRect(banner_x, pt_y(bot_y + bot_h), bot_split_x - banner_x - 8, bot_h, 6, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 9.5); c.setFillColor(colors.black)
    c.drawString(banner_x + 12, pt_y(bot_y + 18), "For Office Use Only")
    c.line(banner_x, pt_y(bot_y + 24), bot_split_x - 8, pt_y(bot_y + 24))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(banner_x + 12, pt_y(bot_y + 44), "Total Correct :")
    for b_idx in range(5):
        bx = banner_x + 95 + (b_idx * 20)
        c.rect(bx, pt_y(bot_y + 49), 20, 16, fill=0, stroke=1)
    c.drawString(banner_x + 12, pt_y(bot_y + 68), "Total Marks :")
    for b_idx in range(3):
        bx = banner_x + 95 + (b_idx * 20)
        c.rect(bx, pt_y(bot_y + 73), 20, 16, fill=0, stroke=1)
    c.roundRect(bot_split_x, pt_y(bot_y + bot_h), banner_x + banner_w - bot_split_x, bot_h, 6, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(bot_split_x + 12, pt_y(bot_y + 22), "Invigilator's Signature")
    c.setLineWidth(0.8)
    c.line(bot_split_x + 14, pt_y(bot_y + 68), banner_x + banner_w - 14, pt_y(bot_y + 68))

    c.showPage()
    c.save()
    print(f"PDF saved: {pdf_path}")
    return pdf_path

pdf_file = generate_ticked_pdf()

# Render to PNG
out_png = os.path.join(artifact_dir, "Vidyakashi_Ticked_25Q.png")
pdf = pdfium.PdfDocument(pdf_file)
page = pdf[0]
bitmap = page.render(scale=2)
pil_image = bitmap.to_pil()
pil_image.save(out_png)
print(f"PNG: {out_png} ({pil_image.width}x{pil_image.height}px)")

# Copy PDF to artifact dir
shutil.copy2(pdf_file, os.path.join(artifact_dir, "Vidyakashi_Ticked_25Q.pdf"))
print("Done.")
