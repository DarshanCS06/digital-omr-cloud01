# Calibration & Accuracy Validation Guide

This document describes how the deterministic computer vision pipeline evaluates bubble markings and explains how to run the calibration utility to benchmark detection thresholds.

---

## 1. Detection Principles and Thresholds

Rather than relying on opaque machine learning models that can hallucinate or fail silently on unusual paper types, Digital OMR Cloud utilizes deterministic computer vision with mathematically calibrated geometric sampling:

1. **Corner Registration Alignment**: Detects the four high-contrast registration squares at page corners using contour solidity and bounding box aspect ratios ($0.7 \le \text{aspect} \le 1.3$).
2. **Homography / Perspective Rectification**: Warps the camera photo into a canonical coordinate space ($1654 \times 2338$ pixels).
3. **Inner Circle Sampling**: The detector measures darkness inside the inner 70% radius of each bubble:
   $$r_{\text{inner}} = 0.70 \times r_{\text{bubble}}$$
   This completely isolates student markings from the printed circular border.
4. **Normalized Ink Density ($D$)**:
   $$D = 1.0 - \left(\frac{\bar{I}_{\text{roi}}}{255.0}\right)$$
   Where $\bar{I}_{\text{roi}}$ is the average pixel intensity of the inner bubble. Pure black pen ink yields $D \approx 0.80 - 0.95$, while clean white paper yields $D \approx 0.02 - 0.10$.

---

## 2. Threshold Calibration Parameters

The pipeline uses four empirical thresholds defined in `backend/app/omr/detector.py`:

| Parameter | Calibrated Default | Purpose |
|---|---|---|
| `fill_threshold` | `0.30` | Any bubble with ink density $\ge 0.30$ is recognized as shaded. |
| `blank_threshold` | `0.14` | Any bubble with ink density $< 0.14$ is recognized as unshaded. |
| `multiple_threshold` | `0.28` | If a second option in the same question reaches $\ge 0.28$, question is flagged `MULTIPLE`. |
| `contrast_margin` | `0.12` | The difference between the highest option and the second option must be at least $0.12$. |

### Edge Case Handling
- **Faint Markings ($0.15 \le D < 0.30$)**: Flagged as `REVIEW`.
- **Erasures / Smudges**: Incomplete erasures usually drop to $D \approx 0.10 - 0.18$. If the contrast margin between the intended option and the erasure is $\ge 0.12$, the intended option is accepted; if ambiguous, it is safely queued for teacher review.
- **Tick Marks**: A tick mark through a bubble produces a density of $D \approx 0.25 - 0.35$. If borderline, human review ensures student intent is honored.

---

## 3. Running the Synthetic Calibration Benchmark

Run the built-in calibration script:
```bash
python -c "from backend.app.omr.calibration import CalibrationUtility; import json; print(json.dumps(CalibrationUtility(100).run_benchmark(), indent=2))"
```

Sample output:
```json
{
  "total_questions": 100,
  "correct_matches": 92,
  "review_flagged": 8,
  "mismatches": 0,
  "accuracy_percentage": 92.0,
  "roll_number_detected": "891045",
  "roll_number_expected": "891045",
  "roll_number_match": true,
  "markers_detected": true,
  "category_breakdown": {
    "solid_fills": { "total": 72, "correct": 72 },
    "blank": { "total": 10, "correct": 10 },
    "multiple": { "total": 10, "correct": 10 },
    "faint": { "total": 3, "flagged_or_correct": 3 },
    "erased": { "total": 3, "blank_or_review": 3 },
    "tick": { "total": 2, "detected": 2 }
  }
}
```

> [!TIP]
> Notice that mismatched errors are **0**. Uncertain or faint cases are safely forwarded to the Teacher Review Queue rather than guessed incorrectly.
