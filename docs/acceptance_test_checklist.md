# Field Acceptance Testing Checklist — Physical OMR Pilot

Use this checklist to perform real-world pilot verification using printed sheets and mobile phone cameras before official institutional rollout.

---

## Phase 1: Physical Printing Verification

- [ ] **Paper Specification**: Standard white A4 paper (70–80 GSM).
- [ ] **Printer Settings**:
  - Print Scale: **100% Scale / Actual Size** (Do **NOT** select "Fit to Printable Area" or "Shrink to Fit").
  - Orientation: Portrait.
  - Print Quality: Normal or High (600 DPI monochrome laser or inkjet).
- [ ] **Visual Inspection**:
  - All 4 solid black corner registration squares are completely visible and crisp.
  - Student roll number matrix (6 columns, 0–9) is cleanly printed.
  - Question bubbles (A, B, C, D) are sharp circles with visible centered letters.
  - QR code in top right is crisp and scannable.

---

## Phase 2: Marking Verification (Test Scenarios)

Prepare 5 sample physical sheets filled with different marking tools:

1. **Sheet A (Ideal Candidate)**: Dark black ballpoint pen, completely filled bubbles.
2. **Sheet B (Blue Pen Candidate)**: Dark blue ballpoint pen, completely filled bubbles.
3. **Sheet C (Faint Pencil / Erasure)**: Light 2B pencil shading on Q5; erased mark on Q10.
4. **Sheet D (Ambiguous / Multiple)**: Both A and B shaded on Q15; crossmark on Q20.
5. **Sheet E (Unanswered / Blank)**: Odd questions shaded, even questions left blank.

---

## Phase 3: Mobile Phone Camera Capture

Test across different mobile phone hardware (Android / iOS):

- [ ] **Distance**: Hold phone camera 30–45 cm directly above sheet.
- [ ] **Lighting**: Even room illumination without harsh glare or direct shadows.
- [ ] **Angle**: Sheet plane parallel to camera lens (tilt $< 15^\circ$).
- [ ] **Capture Action**:
  - Test Option A: Web camera interface with OMR overlay box.
  - Test Option B: Native mobile camera app photo uploaded via gallery file picker.

---

## Phase 4: System Verification & Automated Scoring

- [ ] **Upload Batch**: Upload the 5 test photos simultaneously.
- [ ] **Status Monitoring**: Batch status progresses from `QUEUED` to `PROCESSING` to `COMPLETED`.
- [ ] **Detection Accuracy**:
  - Sheet A: 100% accurate bubble detection.
  - Sheet B: 100% accurate bubble detection.
  - Sheet C & D: Flagged with `NEEDS_REVIEW` badge.
- [ ] **Review Interface**:
  - Zoom into Q10 erasure and override answer with audit reason.
  - Zoom into Q15 multiple mark and confirm `MULTIPLE` penalty.
- [ ] **Scoring Calculations**:
  - Positive marks awarded for correct answers.
  - Configured negative marks deducted for wrong answers.
  - Blank answers rewarded or untouched as configured.
- [ ] **Reports Export**:
  - Download Excel report (`.xlsx`) and verify student scores and correctness columns.
  - Download CSV report and confirm formula neutralization (`'` prefix on formula characters).
- [ ] **Publication**:
  - Click **Publish Results** once all flagged reviews are resolved.
  - Verify official scores match institutional expectation.
