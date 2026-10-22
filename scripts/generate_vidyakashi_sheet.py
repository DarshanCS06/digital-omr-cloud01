import os
import sys
import cv2
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# Paths
base_dir = r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud"
out_dir = os.path.join(base_dir, "generated")
artifact_dir = r"C:\Users\rahul\.gemini\antigravity\brain\f9891136-5e91-4fcb-baf2-cf8007c6bf8c"
os.makedirs(out_dir, exist_ok=True)
os.makedirs(artifact_dir, exist_ok=True)

header_crop_path = os.path.join(out_dir, "vidyakashi_header.png")

# Page Dimensions (A4 Points: 595.28 x 841.89)
PAGE_W, PAGE_H = A4

def pt_x(x): return x
def pt_y(y): return PAGE_H - y

def generate_vidyakashi_pdf():
    pdf_path = os.path.join(out_dir, "Vidyakashi_OMR_Sheet_25Q.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    c.setTitle("Vidyakashi Study Circle - OMR Answer Sheet (25 Questions)")

    # 1. Corner Registration Markers (Solid black rectangular blocks at 4 corners)
    # Width 22 pt, height 14 pt
    c.setFillColor(colors.black)
    c.setStrokeColor(colors.black)
    c.rect(14, pt_y(22), 24, 14, fill=1, stroke=0)                   # Top-Left
    c.rect(PAGE_W - 14 - 24, pt_y(22), 24, 14, fill=1, stroke=0)     # Top-Right
    c.rect(14, pt_y(PAGE_H - 14), 24, 14, fill=1, stroke=0)          # Bottom-Left
    c.rect(PAGE_W - 14 - 24, pt_y(PAGE_H - 14), 24, 14, fill=1, stroke=0) # Bottom-Right

    # 2. Top Header Banner
    # We draw the black header with header crop or exact typography
    banner_x = 24
    banner_y = 28
    banner_w = PAGE_W - 48
    banner_h = 100

    if os.path.exists(header_crop_path):
        c.drawImage(ImageReader(header_crop_path), banner_x, pt_y(banner_y + banner_h), width=banner_w, height=banner_h)
    else:
        # Fallback vector banner
        c.setFillColor(colors.black)
        c.rect(banner_x, pt_y(banner_y + banner_h), banner_w, banner_h, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(PAGE_W / 2.0, pt_y(banner_y + 40), "VIDYAKASHI STUDY CIRCLE")

    # 3. Candidate Details Box
    # Y from 135 to 225
    cand_y = 135
    cand_h = 88
    c.setLineWidth(1.2)
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.white)
    # Outer rounded rect
    c.roundRect(banner_x, pt_y(cand_y + cand_h), banner_w, cand_h, 6, fill=0, stroke=1)
    # Vertical dividing line
    mid_split_x = banner_x + (banner_w * 0.52)
    c.line(mid_split_x, pt_y(cand_y), mid_split_x, pt_y(cand_y + cand_h))

    # Left Column Details: Test Name, Date, Time
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(banner_x + 12, pt_y(cand_y + 24), "Test Name  :")
    c.line(banner_x + 85, pt_y(cand_y + 24), mid_split_x - 12, pt_y(cand_y + 24))

    c.drawString(banner_x + 12, pt_y(cand_y + 52), "Date           :")
    c.line(banner_x + 85, pt_y(cand_y + 52), banner_x + 200, pt_y(cand_y + 52))

    c.drawString(banner_x + 12, pt_y(cand_y + 76), "Time           :")
    c.line(banner_x + 85, pt_y(cand_y + 76), banner_x + 200, pt_y(cand_y + 76))

    # Right Column Details: Roll No (7 boxes), Name, Class, Subject
    c.drawString(mid_split_x + 12, pt_y(cand_y + 24), "Roll No.   :")
    # 7 Roll Number digit boxes
    box_start_x = mid_split_x + 78
    box_size = 18
    for b_idx in range(7):
        bx = box_start_x + (b_idx * 21)
        by = cand_y + 11
        c.rect(bx, pt_y(by + box_size), box_size, box_size, fill=0, stroke=1)

    c.drawString(mid_split_x + 12, pt_y(cand_y + 44), "Name       :")
    c.line(mid_split_x + 78, pt_y(cand_y + 44), banner_x + banner_w - 12, pt_y(cand_y + 44))

    c.drawString(mid_split_x + 12, pt_y(cand_y + 64), "Class        :")
    c.line(mid_split_x + 78, pt_y(cand_y + 64), banner_x + banner_w - 12, pt_y(cand_y + 64))

    c.drawString(mid_split_x + 12, pt_y(cand_y + 82), "Subject    :")
    c.line(mid_split_x + 78, pt_y(cand_y + 82), banner_x + banner_w - 12, pt_y(cand_y + 82))

    # 4. Instructions to Candidates Box
    # Y from 230 to 325
    inst_y = 230
    inst_h = 92
    c.roundRect(banner_x, pt_y(inst_y + inst_h), banner_w, inst_h, 6, fill=0, stroke=1)

    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(banner_x + 12, pt_y(inst_y + 16), "Instructions to Candidates :")

    c.setFont("Helvetica", 7.5)
    instructions = [
        "1.    Use only Blue or Black Ball Point Pen to fill the circles.",
        "2.    Darken only one circle for each question.",
        "3.    Do not make any stray marks on the OMR sheet.",
        "4.    If you want to change an answer, erase completely and darken the new circle.",
        "5.    Each question has four options (A), (B), (C) and (D). Only one option is correct.",
        "6.    Rough work must not be done on this sheet."
    ]
    cur_iy = inst_y + 28
    for line in instructions:
        c.drawString(banner_x + 12, pt_y(cur_iy), line)
        cur_iy += 10.5

    # Correct / Wrong Method demonstration box on right
    method_box_w = 175
    method_box_h = 60
    method_box_x = banner_x + banner_w - method_box_w - 12
    method_box_y = inst_y + 24
    c.rect(method_box_x, pt_y(method_box_y + method_box_h), method_box_w, method_box_h, fill=0, stroke=1)
    c.line(method_box_x + 85, pt_y(method_box_y), method_box_x + 85, pt_y(method_box_y + method_box_h))

    # Headers
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(method_box_x + 42, pt_y(method_box_y + 11), "Correct Method")
    c.drawCentredString(method_box_x + 85 + 45, pt_y(method_box_y + 11), "Wrong Methods")
    c.line(method_box_x, pt_y(method_box_y + 16), method_box_x + method_box_w, pt_y(method_box_y + 16))

    # Correct Demo (A shaded, B, C, D empty)
    demo_opts = ["A", "B", "C", "D"]
    for idx, opt in enumerate(demo_opts):
        bx = method_box_x + 15 + (idx * 18)
        by = method_box_y + 28
        c.setLineWidth(0.7)
        if idx == 0:
            c.circle(bx, pt_y(by), 5.5, fill=1, stroke=1)
        else:
            c.circle(bx, pt_y(by), 5.5, fill=0, stroke=1)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(bx, pt_y(by + 16), opt)

    # Wrong Demo (X, check, half, dot)
    for idx, opt in enumerate(demo_opts):
        bx = method_box_x + 98 + (idx * 18)
        by = method_box_y + 28
        c.circle(bx, pt_y(by), 5.5, fill=0, stroke=1)
        if idx == 0: # X
            c.line(bx - 3, pt_y(by - 3), bx + 3, pt_y(by + 3))
            c.line(bx - 3, pt_y(by + 3), bx + 3, pt_y(by - 3))
        elif idx == 1: # check
            c.line(bx - 3, pt_y(by), bx, pt_y(by + 3))
            c.line(bx, pt_y(by + 3), bx + 4, pt_y(by - 4))
        elif idx == 2: # half
            c.wedge(bx - 5.5, pt_y(by + 5.5), bx + 5.5, pt_y(by - 5.5), 0, 180, fill=1, stroke=0)
        elif idx == 3: # dot
            c.circle(bx, pt_y(by), 2, fill=1, stroke=1)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(bx, pt_y(by + 16), opt)

    # 5. Question Grid (2 Major Columns: Q01-13 on left, Q14-25 on right)
    # Y from 332 to 735
    grid_start_y = 332
    grid_w = (banner_w - 12) / 2.0  # ~268 pt per table
    table_left_x = banner_x
    table_right_x = banner_x + grid_w + 12

    row_h = 28.5
    col_w_qno = 54
    col_w_opt = (grid_w - col_w_qno) / 4.0  # ~53.5 pt per option

    # Bubble radius
    bubble_radius = 8.5
    bubble_coords = {}

    def draw_omr_table(base_x, start_q, count):
        # Draw table border
        total_rows = 14 # 1 header + 13 question rows
        table_h = total_rows * row_h
        
        # Header background
        c.setFillColor(colors.HexColor("#E2E8F0"))
        c.rect(base_x, pt_y(grid_start_y + row_h), grid_w, row_h, fill=1, stroke=1)

        # Header Text
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawCentredString(base_x + (col_w_qno / 2.0), pt_y(grid_start_y + 19), "Q. No.")
        for idx, opt in enumerate(["A", "B", "C", "D"]):
            ox = base_x + col_w_qno + (idx * col_w_opt) + (col_w_opt / 2.0)
            c.drawCentredString(ox, pt_y(grid_start_y + 19), opt)

        # Rows
        c.setLineWidth(0.8)
        for r_idx in range(1, total_rows):
            ry = grid_start_y + (r_idx * row_h)
            c.setFillColor(colors.white)
            c.rect(base_x, pt_y(ry + row_h), grid_w, row_h, fill=0, stroke=1)

            # Vertical column lines
            c.line(base_x + col_w_qno, pt_y(ry), base_x + col_w_qno, pt_y(ry + row_h))
            for i in range(1, 4):
                lx = base_x + col_w_qno + (i * col_w_opt)
                c.line(lx, pt_y(ry), lx, pt_y(ry + row_h))

            q_num = start_q + r_idx - 1
            if q_num <= 25 and (r_idx - 1) < count:
                # Question Number
                c.setFillColor(colors.black)
                c.setFont("Helvetica-Bold", 9.5)
                c.drawCentredString(base_x + (col_w_qno / 2.0), pt_y(ry + 19), f"{q_num:02d}")

                # Answer Bubbles A, B, C, D
                bubble_coords[q_num] = {}
                for idx, opt in enumerate(["A", "B", "C", "D"]):
                    cx = base_x + col_w_qno + (idx * col_w_opt) + (col_w_opt / 2.0)
                    cy = ry + (row_h / 2.0)
                    c.circle(cx, pt_y(cy), bubble_radius, fill=0, stroke=1)
                    bubble_coords[q_num][opt] = (cx, cy, bubble_radius)

    draw_omr_table(table_left_x, 1, 13)    # Q01 to Q13
    draw_omr_table(table_right_x, 14, 12)  # Q14 to Q25

    # 6. Bottom Section: Office Use Only & Invigilator Signature
    # Y from 742 to 818
    bot_y = 742
    bot_h = 76
    bot_split_x = banner_x + (banner_w * 0.52)

    # Left Box: For Office Use Only
    c.roundRect(banner_x, pt_y(bot_y + bot_h), bot_split_x - banner_x - 8, bot_h, 6, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 9.5)
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

    # Right Box: Invigilator's Signature
    c.roundRect(bot_split_x, pt_y(bot_y + bot_h), banner_x + banner_w - bot_split_x, bot_h, 6, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(bot_split_x + 12, pt_y(bot_y + 22), "Invigilator's Signature")
    c.setLineWidth(0.8)
    c.line(bot_split_x + 14, pt_y(bot_y + 68), banner_x + banner_w - 14, pt_y(bot_y + 68))

    c.showPage()
    c.save()
    print(f"Generated PDF: {pdf_path}")
    return pdf_path, bubble_coords

pdf_file, bubbles = generate_vidyakashi_pdf()

# Copy PDF to artifact dir
import shutil
shutil.copy2(pdf_file, os.path.join(artifact_dir, "Vidyakashi_OMR_Sheet_25Q.pdf"))
print("Copied PDF to artifact directory.")
