import subprocess
import os
import tempfile
import cv2
import re
import numpy as np
from backend.app.omr.vidyakashi_generator import VidyakashiOMRGenerator

def recognize_winrt(crop_img):
    tmp = os.path.join(tempfile.gettempdir(), f'winrt_{os.getpid()}.png').replace('/', '\\')
    cv2.imwrite(tmp, crop_img)
    ps_path = os.path.join(tempfile.gettempdir(), f'winrt_{os.getpid()}.ps1')
    script = f"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Foundation, ContentType = WindowsRuntime]
function Await($op, [Type]$t) {{
    $m = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.IsGenericMethod }})[0].MakeGenericMethod($t)
    $task = $m.Invoke($null, @($op))
    $task.Wait()
    return $task.Result
}}
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync('{tmp}')) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bmp = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$eng = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$res = Await ($eng.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
Write-Output $res.Text
$stream.Dispose()
"""
    with open(ps_path, 'w', encoding='utf-8') as f:
        f.write(script)
    try:
        out = subprocess.check_output(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps_path],
            encoding='utf-8',
            timeout=8
        )
        return out.strip()
    finally:
        for p in (tmp, ps_path):
            try:
                os.remove(p)
            except OSError:
                pass

def build_candidate_canvas(raw_or_rectified_img):
    canon = (
        cv2.resize(raw_or_rectified_img, (1654, 2338))
        if (raw_or_rectified_img.shape[1] != 1654 or raw_or_rectified_img.shape[0] != 2338)
        else raw_or_rectified_img
    )
    crop = canon[380:680, 1030:1580].copy()
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop.copy()

    left_name_crop = canon[425:504, 240:820].copy()
    left_gray = cv2.cvtColor(left_name_crop, cv2.COLOR_BGR2GRAY) if len(left_name_crop.shape) == 3 else left_name_crop.copy()
    inv_left = (left_gray < 210).astype(np.uint8) * 255
    hline_l = cv2.morphologyEx(inv_left, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (45, 1)))
    hline_l_dil = cv2.dilate(hline_l, np.ones((3, 1), np.uint8), iterations=1)
    vert_l = cv2.morphologyEx(inv_left, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5)))
    vert_l_dil = cv2.dilate(vert_l, np.ones((5, 2), np.uint8), iterations=1)
    left_cleaned = left_gray.copy()
    left_cleaned[(hline_l_dil > 0) & (vert_l_dil == 0)] = 255

    inv42 = (gray < 210).astype(np.uint8) * 255
    h42 = cv2.morphologyEx(inv42, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (42, 1)))
    v42 = cv2.morphologyEx(inv42, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 42)))
    lines42 = cv2.dilate(cv2.bitwise_or(h42, v42), np.ones((3, 1), np.uint8), iterations=1)
    vert_r = cv2.morphologyEx(inv42, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5)))
    vert_r_dil = cv2.dilate(vert_r, np.ones((5, 2), np.uint8), iterations=1)
    cleaned42 = gray.copy()
    cleaned42[(lines42 > 0) & (vert_r_dil == 0)] = 255

    if int(np.sum(cleaned42 < 160)) < 300 and int(np.sum(left_cleaned < 160)) < 250:
        return None

    inv36 = (gray < 200).astype(np.uint8) * 255
    v36 = cv2.morphologyEx(inv36, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 36)))
    h36 = cv2.morphologyEx(inv36, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (36, 1)))
    lines36 = cv2.dilate(cv2.bitwise_or(h36, v36), np.ones((3, 1), np.uint8), iterations=1)
    cleaned36 = gray.copy()
    cleaned36[(lines36 > 0) & (vert_r_dil == 0)] = 255

    ys, _ = np.where(v36 > 0)
    canvas = np.full((520, 620), 255, dtype=np.uint8)
    canvas[0:300, 0:550] = cleaned42
    if len(ys) > 0:
        r_y1, r_y2 = int(np.percentile(ys, 5)), int(np.percentile(ys, 95))
        if (r_y2 - r_y1) <= 65:
            band_y1, band_y2 = max(0, r_y1 - 4), min(cleaned36.shape[0], r_y2 + 4)
        else:
            band_y1, band_y2 = 200, min(cleaned36.shape[0], 255)
        roll_band = 255 - cleaned36[band_y1:band_y2, :]
        roll_bin = (roll_band > 45).astype(np.uint8) * 255
        num, _, stats, _ = cv2.connectedComponentsWithStats(roll_bin)
        glyphs = [
            stats[i][:4]
            for i in range(1, num)
            if stats[i][4] >= 10 and 10 <= stats[i][3] <= 42 and 2 <= stats[i][2] <= 38
        ]
        glyphs.sort(key=lambda g: g[0])
        cx = 25
        for (x, y, w, h) in glyphs:
            if cx + w * 2 < 580:
                patch = cleaned36[band_y1 + y : band_y1 + y + h, x : x + w]
                patch_up = cv2.resize(patch, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
                y0 = 325 + max(0, (48 - h * 2) // 2)
                canvas[y0 : y0 + h * 2, cx : cx + w * 2] = patch_up
                cx += w * 2 + 8

    if int(np.sum(left_cleaned < 160)) >= 250:
        canvas[410:489, 0:580] = left_cleaned

    return canvas

def recognize_canvas_ocr(canvas):
    tmp = os.path.join(tempfile.gettempdir(), f'winrt_{os.getpid()}.png').replace('/', '\\')
    cv2.imwrite(tmp, canvas)
    ps_path = os.path.join(tempfile.gettempdir(), f'winrt_{os.getpid()}.ps1')
    script = f"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Foundation, ContentType = WindowsRuntime]
function Await($op, [Type]$t) {{
    $m = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.IsGenericMethod }})[0].MakeGenericMethod($t)
    $task = $m.Invoke($null, @($op))
    $task.Wait()
    return $task.Result
}}
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync('{tmp}')) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bmp = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$eng = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$res = Await ($eng.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
foreach ($line in $res.Lines) {{
    foreach ($w in $line.Words) {{
        Write-Output ('W|' + [int]$w.BoundingRect.X + '|' + [int]$w.BoundingRect.Y + '|' + $w.Text)
    }}
}}
$stream.Dispose()
"""
    with open(ps_path, 'w', encoding='utf-8') as f:
        f.write(script)
    try:
        out = subprocess.check_output(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps_path],
            encoding='utf-8',
            timeout=8
        )
    finally:
        for p in (tmp, ps_path):
            try:
                os.remove(p)
            except OSError:
                pass

    words = []
    for ln in out.splitlines():
        if ln.startswith("W|"):
            _, sx, sy, txt = ln.split("|", 3)
            words.append((int(sx), int(sy), txt.strip()))

    words.sort(key=lambda w: w[1])
    rows = []
    for wx, wy, wt in words:
        if not rows or abs(wy - rows[-1][0][1]) > 18:
            rows.append([(wx, wy, wt)])
        else:
            rows[-1].append((wx, wy, wt))

    trans_map = str.maketrans({
        "O": "0", "o": "0", "ø": "0", "Ø": "0", "Q": "0", "D": "0", "@": "0",
        "I": "1", "l": "1", "i": "1", "|": "1",
        "Z": "2", "z": "2",
        "S": "5", "s": "5",
        "B": "8",
    })
    roll_candidates = []
    left_name_candidate = None
    right_name_candidate = None
    ignore_words = {
        "general", "ability", "test", "mental", "abilitq", "science",
        "standard", "sec-a", "8th", "10th", "maths", "physics", "roll", "name", "class", "subject", "practice", "benchmark", "vks"
    }
    for r in rows:
        r.sort(key=lambda w: w[0])
        row_y = r[0][1]
        raw_str = " ".join(w[2] for w in r).replace(",", ".").replace(":", " ")
        digit_mapped = "".join(w[2] for w in r).translate(trans_map)
        digits_only = re.sub(r"\D", "", digit_mapped)
        alpha_after_map = re.sub(r"[^A-Za-z]", "", digit_mapped)
        alpha_only = re.sub(r"[^A-Za-z. ]", "", raw_str).strip()

        if 310 <= row_y <= 385:
            if len(digits_only) >= 2 and len(alpha_after_map) <= 1:
                roll_candidates.append(digits_only)
        elif len(digits_only) >= 5 and len(alpha_after_map) <= 1:
            roll_candidates.append(digits_only)

        if len(alpha_only) >= 3:
            low_words = set(alpha_only.lower().split())
            if not (low_words & ignore_words):
                if row_y >= 390 and left_name_candidate is None:
                    left_name_candidate = alpha_only
                elif row_y < 300 and right_name_candidate is None:
                    right_name_candidate = alpha_only

    name_candidate = left_name_candidate or right_name_candidate
    best_roll = max(roll_candidates, key=len) if roll_candidates else None
    conf = 0.95 if (best_roll or name_candidate) else 0.0
    return best_roll, name_candidate, conf

def test():
    gen = VidyakashiOMRGenerator(25)
    sheet = gen.generate_image(
        exam_title='Benchmark', exam_code='VKS', subject='Physics',
        class_grade='10th', exam_date='22/10/2026', pre_filled_answers={},
        student_name='Aarav Sharma', student_roll='250710001'
    )
    canvas = build_candidate_canvas(sheet)
    best_roll, name_cand, conf = recognize_canvas_ocr(canvas)
    print("Parsed Result:")
    print("  Roll:", repr(best_roll))
    print("  Name:", repr(name_cand))
    print("  Conf:", conf)

if __name__ == '__main__':
    test()

