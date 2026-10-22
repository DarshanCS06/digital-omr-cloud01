import cv2
import numpy as np
from typing import Dict, Tuple, Optional, List
from backend.app.omr.layout import (
    OMRLayoutConfig,
    CANONICAL_WIDTH,
    CANONICAL_HEIGHT,
)


class SyntheticOMRGenerator:
    """Generates synthetic OMR test images with known ground truth for validation and calibration."""

    def __init__(self, layout: Optional[OMRLayoutConfig] = None):
        self.layout = layout or OMRLayoutConfig(question_count=100)

    def create_synthetic_sheet(
        self,
        ground_truth: Dict[int, str],
        roll_number: str = "123456",
        faint_questions: Optional[List[int]] = None,
        erased_questions: Optional[List[int]] = None,
        tick_questions: Optional[List[int]] = None,
        apply_distortion: bool = False,
    ) -> Tuple[np.ndarray, Dict[int, str]]:
        """Generates a synthetic OMR sheet image matching the canonical layout."""
        # 1. Blank white page with slight paper grain
        img = np.ones((CANONICAL_HEIGHT, CANONICAL_WIDTH, 3), dtype=np.uint8) * 255
        
        # Add subtle paper texture
        noise = np.random.normal(0, 3, (CANONICAL_HEIGHT, CANONICAL_WIDTH, 3)).astype(np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # 2. Draw 4 Corner Registration Markers
        half_m = self.layout.marker_size // 2
        for name, (cx, cy) in self.layout.markers.items():
            cv2.rectangle(
                img,
                (cx - half_m, cy - half_m),
                (cx + half_m, cy + half_m),
                (10, 10, 10),
                -1
            )

        # 3. Draw Header text and instructions
        cv2.putText(img, "DIGITAL OMR CLOUD - SYNTHETIC BENCHMARK SHEET", (120, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20, 20, 20), 2)
        cv2.putText(img, f"Roll Number: {roll_number}  |  Questions: {self.layout.question_count}", (120, 165), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (50, 50, 50), 1)

        # 4. Draw Roll Number Matrix & Shade Roll Bubbles
        roll_digits = [int(ch) if ch.isdigit() else 0 for ch in roll_number[:self.layout.roll_digit_count]]
        for rb in self.layout.roll_bubbles:
            # Draw outline
            cv2.circle(img, (rb.cx, rb.cy), rb.radius, (40, 40, 40), 1)
            cv2.putText(img, str(rb.digit), (rb.cx - 4, rb.cy + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (80, 80, 80), 1)
            
            # Fill if matches digit in this column
            if rb.column_index < len(roll_digits) and rb.digit == roll_digits[rb.column_index]:
                # Realistic hand-filled bubble with pen pressure
                cv2.circle(img, (rb.cx, rb.cy), rb.radius - 2, (15, 15, 20), -1)

        # 5. Draw Question Bubbles & Shade ground truth
        faint_set = set(faint_questions or [])
        erased_set = set(erased_questions or [])
        tick_set = set(tick_questions or [])

        for q_num, opt_map in self.layout.bubbles.items():
            first_b = next(iter(opt_map.values()))
            cv2.putText(img, f"{q_num:02d}.", (first_b.cx - 52, first_b.cy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (30, 30, 30), 1)

            target_val = ground_truth.get(q_num, "BLANK")

            for opt_key, bubble in opt_map.items():
                # Draw bubble ring
                cv2.circle(img, (bubble.cx, bubble.cy), bubble.radius, (40, 40, 40), 1)
                cv2.putText(img, opt_key, (bubble.cx - 4, bubble.cy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (70, 70, 70), 1)

                # Simulate different filling scenarios
                if target_val == opt_key:
                    if q_num in faint_set:
                        # Faint pencil/light shade (gray fill ~ 160)
                        cv2.circle(img, (bubble.cx, bubble.cy), bubble.radius - 2, (160, 160, 165), -1)
                    elif q_num in erased_set:
                        # Erased mark (patchy gray smudge)
                        cv2.circle(img, (bubble.cx, bubble.cy), bubble.radius - 3, (195, 195, 200), -1)
                    elif q_num in tick_set:
                        # Tick mark across bubble
                        cv2.line(img, (bubble.cx - 6, bubble.cy), (bubble.cx, bubble.cy + 6), (20, 20, 20), 2)
                        cv2.line(img, (bubble.cx, bubble.cy + 6), (bubble.cx + 8, bubble.cy - 7), (20, 20, 20), 2)
                    else:
                        # Normal solid dark blue/black ink fill
                        cv2.circle(img, (bubble.cx, bubble.cy), bubble.radius - 2, (20, 15, 25), -1)

                elif target_val == "MULTIPLE" and opt_key in ["A", "B"]:
                    # Shade multiple options
                    cv2.circle(img, (bubble.cx, bubble.cy), bubble.radius - 2, (25, 20, 30), -1)

        # 6. Optional camera perspective warping and slight rotation
        if apply_distortion:
            src_pts = np.float32([[0, 0], [CANONICAL_WIDTH, 0], [CANONICAL_WIDTH, CANONICAL_HEIGHT], [0, CANONICAL_HEIGHT]])
            # Add perspective tilt simulation typical of mobile camera holding
            dst_pts = np.float32([
                [40, 50],
                [CANONICAL_WIDTH - 60, 25],
                [CANONICAL_WIDTH - 20, CANONICAL_HEIGHT - 35],
                [55, CANONICAL_HEIGHT - 60]
            ])
            matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
            img = cv2.warpPerspective(img, matrix, (CANONICAL_WIDTH, CANONICAL_HEIGHT), borderValue=(235, 235, 235))

        return img, ground_truth
