"""
Memory-Safe Bulk PDF OMR Processor using pypdfium2 and OpenCV.
Supports:
- Validation of PDF magic bytes, file size, page count, encryption, and corruption
- On-demand single-page rendering (avoids loading all pages into memory at once)
- Blank page detection
- Multi-sheet page segmentation (2-up side-by-side or stacked OMR sheets on a single page)
- Safe temporary file handling and cleanup
"""
import os
import cv2
import numpy as np
import pypdfium2 as pdfium
from typing import Dict, Any, List, Tuple, Union, Optional

from backend.app.config import settings


class PDFProcessor:
    @staticmethod
    def is_pdf_file(filename: str = "", raw_bytes: bytes = b"") -> bool:
        """Checks if the uploaded file is a PDF by extension or magic header."""
        if filename and filename.lower().endswith(".pdf"):
            return True
        if raw_bytes and raw_bytes.lstrip()[:5].startswith(b"%PDF-"):
            return True
        return False

    @staticmethod
    def validate_pdf_bytes(raw_bytes: bytes, filename: str = "upload.pdf") -> Dict[str, Any]:
        """
        Validates a PDF file before queuing or rendering.
        Gracefully handles empty, oversized, encrypted, corrupted, and zero-page PDFs.
        """
        if not raw_bytes or len(raw_bytes) == 0:
            raise ValueError("The uploaded PDF file is empty.")

        max_pdf_bytes = getattr(settings, "MAX_PDF_UPLOAD_SIZE_BYTES", 100 * 1024 * 1024)
        if len(raw_bytes) > max_pdf_bytes:
            max_mb = max_pdf_bytes // (1024 * 1024)
            raise ValueError(f"The PDF file exceeds the maximum allowed size limit ({max_mb} MB).")

        stripped = raw_bytes.lstrip()
        if not stripped.startswith(b"%PDF-"):
            raise ValueError("Unsupported or invalid PDF file format.")

        doc = None
        try:
            doc = pdfium.PdfDocument(raw_bytes)
            page_count = len(doc)
        except Exception as exc:
            err_msg = str(exc).lower()
            if "password" in err_msg or "encrypt" in err_msg or b"/Encrypt" in raw_bytes:
                raise ValueError(
                    "The PDF file is password-protected or encrypted. Please upload an unencrypted PDF."
                )
            raise ValueError(
                "The PDF file is corrupted or unreadable. Please upload a valid PDF."
            )
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

        if page_count <= 0:
            raise ValueError("The PDF file contains no pages.")

        max_pages = getattr(settings, "MAX_PDF_PAGES", 300)
        if page_count > max_pages:
            raise ValueError(
                f"The PDF contains {page_count} pages, which exceeds the maximum limit of {max_pages} pages."
            )

        return {
            "filename": filename,
            "file_size_bytes": len(raw_bytes),
            "page_count": page_count,
            "is_valid": True,
        }

    @staticmethod
    def render_single_page(
        pdf_source: Union[bytes, str],
        page_index: int,
        dpi: int = 200,
    ) -> np.ndarray:
        """
        Renders a single page (0-indexed) from a PDF file path or byte buffer into a high-resolution
        OpenCV BGR numpy array while preserving aspect ratio and freeing PDFium resources immediately.
        """
        if isinstance(pdf_source, str) and not os.path.isfile(pdf_source):
            raise ValueError("Temporary PDF source file not found.")

        doc = None
        page = None
        bmp = None
        try:
            doc = pdfium.PdfDocument(pdf_source)
            total_pages = len(doc)
            if page_index < 0 or page_index >= total_pages:
                raise ValueError(f"Page index {page_index + 1} is out of range (1..{total_pages}).")

            page = doc[page_index]
            w_pt, h_pt = page.get_size()
            if w_pt <= 0 or h_pt <= 0:
                raise ValueError(f"Page {page_index + 1} has invalid dimensions.")

            scale = float(dpi) / 72.0
            min_pt = min(w_pt, h_pt)
            max_pt = max(w_pt, h_pt)
            # Ensure sufficient resolution for small-point PDFs while bounding max memory
            if min_pt * scale < 900.0:
                scale = 900.0 / float(max(1.0, min_pt))
            if max_pt * scale > 3400.0:
                scale = 3400.0 / float(max_pt)

            bmp = page.render(scale=scale)
            img_bgr = bmp.to_numpy().copy()
            if img_bgr.ndim == 3 and img_bgr.shape[2] == 4:
                img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2BGR)
            return img_bgr
        except ValueError:
            raise
        except Exception as exc:
            err_msg = str(exc).lower()
            if "password" in err_msg:
                raise ValueError("The PDF file is password-protected or encrypted.")
            raise ValueError(f"Failed to render PDF page {page_index + 1}: corrupted page content.")
        finally:
            if bmp is not None:
                try:
                    bmp.close()
                except Exception:
                    pass
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

    @staticmethod
    def is_blank_page(img: np.ndarray) -> bool:
        """Detects whether a rendered PDF page is blank (empty white or flat solid fill)."""
        if img is None or img.size == 0:
            return True
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        std_val = float(np.std(gray))
        p99_p1 = float(np.percentile(gray, 99) - np.percentile(gray, 1))
        return std_val < 5.0 or p99_p1 < 18.0

    @staticmethod
    def _looks_like_omr_sheet(sub_img: np.ndarray) -> bool:
        """Checks whether a segmented sub-image contains a recognizable OMR sheet."""
        gray = cv2.cvtColor(sub_img, cv2.COLOR_BGR2GRAY) if len(sub_img.shape) == 3 else sub_img
        sh, sw = gray.shape[:2]
        if sh < 400 or sw < 300:
            return False
        # Check for Vidyakashi top header banner
        top_banner = gray[int(sh * 0.02) : int(sh * 0.16), int(sw * 0.15) : int(sw * 0.85)]
        if top_banner.size > 0 and float(np.mean(top_banner)) < 168.0:
            return True
        # Or check for 4-corner registration markers
        from backend.app.omr.detector import OMRDetector
        det = OMRDetector()
        if det.find_registration_markers(sub_img) is not None:
            return True
        return False

    @staticmethod
    def extract_page_candidate_text(
        pdf_source: Union[bytes, str],
        page_index: int,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts student name and roll number directly from the PDF page's text layer
        (if available from digital / vector PDF generators) in < 1 ms.
        """
        import re
        doc = None
        page = None
        textpage = None
        try:
            doc = pdfium.PdfDocument(pdf_source)
            if page_index < 0 or page_index >= len(doc):
                return None, None
            page = doc[page_index]
            textpage = page.get_textpage()
            text = textpage.get_text_bounded()
            if not text:
                return None, None

            found_roll = None
            found_name = None

            # Look for Roll Number: e.g. "Roll No. : 250710001", "Roll Number: 102345", "Roll: 250710"
            roll_match = re.search(
                r"(?:roll\s*(?:no\.?|number)?|registration\s*(?:no\.?|number)?|reg\s*no\.?)\s*[:\-]\s*([A-Za-z0-9\-]+)",
                text,
                re.IGNORECASE,
            )
            if roll_match:
                cand_r = roll_match.group(1).strip()
                if len(cand_r) >= 2 and cand_r.lower() not in ("box", "boxes"):
                    found_roll = cand_r

            # Look for Student Name: e.g. "Name : Aarav Sharma", "Student Name: Diya Nair"
            name_match = re.search(
                r"(?:student\s*name|candidate\s*name|^name)\s*[:\-]\s*([A-Za-z][A-Za-z .]{2,40})",
                text,
                re.IGNORECASE | re.MULTILINE,
            )
            if name_match:
                cand_n = name_match.group(1).strip()
                ignore_n = {"vidyakashi", "study circle", "general", "science", "physics", "maths"}
                if cand_n.lower() not in ignore_n and not any(cand_n.lower().startswith(x) for x in ignore_n):
                    found_name = cand_n

            return found_roll, found_name
        except Exception:
            return None, None
        finally:
            if textpage is not None:
                try:
                    textpage.close()
                except Exception:
                    pass
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

    @classmethod
    def segment_page_sheets(cls, page_img: np.ndarray) -> List[Tuple[np.ndarray, str]]:
        """
        Detects if a single PDF page contains multiple OMR sheets (e.g. 2-up side-by-side
        on a wide page or 2 stacked vertically on a tall page) and segments each sheet.
        Returns a list of (sheet_img, suffix_label) tuples.
        """
        h, w = page_img.shape[:2]

        # 1. Check for 2 side-by-side portrait OMR sheets on a landscape page
        if w > int(h * 1.25):
            mid_x = w // 2
            left_half = page_img[:, :mid_x]
            right_half = page_img[:, mid_x:]
            # Ensure each half is portrait (height > width * 1.15)
            if h > int(mid_x * 1.15) and cls._looks_like_omr_sheet(left_half) and cls._looks_like_omr_sheet(right_half):
                return [(left_half, "Sheet 1"), (right_half, "Sheet 2")]

        # 2. Check for 2 vertically stacked OMR sheets on a tall page
        if h > int(w * 2.1):
            mid_y = h // 2
            top_half = page_img[:mid_y, :]
            bottom_half = page_img[mid_y:, :]
            if cls._looks_like_omr_sheet(top_half) and cls._looks_like_omr_sheet(bottom_half):
                return [(top_half, "Sheet 1"), (bottom_half, "Sheet 2")]

        return [(page_img, "")]
