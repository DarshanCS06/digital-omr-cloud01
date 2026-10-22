from typing import Dict, List, Any
from backend.app.omr.layout import OMRLayoutConfig
from backend.app.omr.detector import OMRDetector
from backend.app.omr.synthetic import SyntheticOMRGenerator


class CalibrationUtility:
    """Evaluates and tunes OMR detection thresholds against controlled synthetic test suites."""

    def __init__(self, question_count: int = 100):
        self.layout = OMRLayoutConfig(question_count=question_count)
        self.detector = OMRDetector(self.layout)
        self.synthetic_gen = SyntheticOMRGenerator(self.layout)

    def run_benchmark(self) -> Dict[str, Any]:
        """Runs evaluation over a suite of synthetic patterns."""
        # Define Ground Truth answers
        ground_truth: Dict[int, str] = {}
        for q in range(1, self.layout.question_count + 1):
            if q % 10 == 0:
                ground_truth[q] = "BLANK"
            elif q % 10 == 9:
                ground_truth[q] = "MULTIPLE"
            else:
                ground_truth[q] = ["A", "B", "C", "D"][(q - 1) % 4]

        # Designate edge-case questions
        faint_questions = [15, 25, 35]
        erased_questions = [16, 26, 36]
        tick_questions = [17, 27, 37]

        # Generate synthetic sheet
        sheet_img, _ = self.synthetic_gen.create_synthetic_sheet(
            ground_truth=ground_truth,
            roll_number="891045",
            faint_questions=faint_questions,
            erased_questions=erased_questions,
            tick_questions=tick_questions,
            apply_distortion=False
        )

        # Process through detector
        result = self.detector.process_omr_sheet(sheet_img)
        detected_questions = result["questions"]

        # Calculate metrics
        total = self.layout.question_count
        correct_matches = 0
        review_count = 0
        mismatches = 0
        category_breakdown = {
            "solid_fills": {"total": 0, "correct": 0},
            "blank": {"total": 0, "correct": 0},
            "multiple": {"total": 0, "correct": 0},
            "faint": {"total": len(faint_questions), "flagged_or_correct": 0},
            "erased": {"total": len(erased_questions), "blank_or_review": 0},
            "tick": {"total": len(tick_questions), "detected": 0},
        }

        for q_num, expected in ground_truth.items():
            det_info = detected_questions.get(q_num, {})
            det_classification = det_info.get("classification", "BLANK")

            is_valid_result = False
            if q_num in faint_questions:
                if det_classification in [expected, "REVIEW"]:
                    category_breakdown["faint"]["flagged_or_correct"] += 1
                    is_valid_result = True
            elif q_num in erased_questions:
                if det_classification in ["BLANK", "REVIEW"]:
                    category_breakdown["erased"]["blank_or_review"] += 1
                    is_valid_result = True
            elif q_num in tick_questions:
                if det_classification in [expected, "REVIEW"]:
                    category_breakdown["tick"]["detected"] += 1
                    is_valid_result = True
            elif expected == "BLANK":
                category_breakdown["blank"]["total"] += 1
                if det_classification == "BLANK":
                    category_breakdown["blank"]["correct"] += 1
                    is_valid_result = True
            elif expected == "MULTIPLE":
                category_breakdown["multiple"]["total"] += 1
                if det_classification == "MULTIPLE":
                    category_breakdown["multiple"]["correct"] += 1
                    is_valid_result = True
            else:
                category_breakdown["solid_fills"]["total"] += 1
                if det_classification == expected:
                    category_breakdown["solid_fills"]["correct"] += 1
                    is_valid_result = True

            if det_classification == "REVIEW":
                review_count += 1

            if is_valid_result:
                correct_matches += 1
            else:
                mismatches += 1

        accuracy = round(float(correct_matches) / float(total) * 100.0, 2)
        
        return {
            "total_questions": total,
            "correct_matches": correct_matches,
            "review_flagged": review_count,
            "mismatches": mismatches,
            "accuracy_percentage": accuracy,
            "roll_number_detected": result["detected_roll_number"],
            "roll_number_expected": "891045",
            "roll_number_match": result["detected_roll_number"] == "891045",
            "markers_detected": result["markers_detected"],
            "category_breakdown": category_breakdown,
            "calibrated_thresholds": {
                "fill_threshold": self.detector.fill_threshold,
                "blank_threshold": self.detector.blank_threshold,
                "multiple_threshold": self.detector.multiple_threshold,
                "contrast_margin": self.detector.contrast_margin,
            }
        }
