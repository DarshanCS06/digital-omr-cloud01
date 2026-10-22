# Digital OMR Cloud — Troubleshooting Guide

This guide provides actionable solutions for operational and detection issues encountered during field deployment.

---

## 1. Image Capture & Quality Issues

### Problem: "Blurry image (score X < 40). Please hold phone steady."
- **Cause**: Mobile camera shake or macro lens autofocus failure.
- **Solution**:
  1. Hold the phone approximately 30–45 cm (12–18 inches) directly above the sheet.
  2. Tap the screen to focus on the question bubbles before taking the photo.
  3. Ensure adequate ambient room lighting.

### Problem: "Glare detected on sheet."
- **Cause**: Direct overhead light fixture or ceiling lamp reflecting off glossy paper or camera flash.
- **Solution**:
  1. Turn off the mobile phone camera flash.
  2. Tilt the camera slightly or position the sheet so reflections do not obscure registration squares.
  3. Use standard matte 75–80 GSM office paper.

---

## 2. Registration Marker & Perspective Issues

### Problem: "Corner markers could not be aligned."
- **Cause**: One or more of the 4 solid black corner squares are cropped out, folded, torn, or occluded by student fingers.
- **Solution**:
  1. Ensure the entire A4 sheet is visible inside the camera viewfinder.
  2. Confirm the printer did not crop page margins during printing. Always select **"Print at 100% (Do Not Scale / Do Not Shrink)"** in printer dialogs.

---

## 3. Duplicate Submission Detection

### Problem: Image flagged as "DUPLICATE".
- **Cause**: The identical photo has already been uploaded and processed for this examination (matching SHA-256 hash), or a student roll number was uploaded twice.
- **Solution**:
  1. Check the Submissions tab for the student's existing record.
  2. If the student submitted a genuine replacement sheet, review and override in the Review Queue.

---

## 4. Background Task Queue Issues

### Problem: "Redis connection failed. Falling back to ThreadPool."
- **Behavior**: The application seamlessly uses an in-process ThreadPool fallback if Redis is temporarily offline.
- **Production Solution**: Verify the Redis service status:
  ```bash
  docker compose restart redis
  docker compose logs redis
  ```

---

## 5. Cannot Publish Examination Results

### Problem: "Cannot publish results: X submissions still require human review."
- **Cause**: System safeguard prevents publishing provisional scores if any questions remain in `REVIEW` status.
- **Solution**:
  1. Click **Resolve** in the Submissions tab or navigate to the **Human Verification Queue**.
  2. Confirm or override the student's marks.
  3. Once unresolved reviews reach 0, the Publish button will activate.
