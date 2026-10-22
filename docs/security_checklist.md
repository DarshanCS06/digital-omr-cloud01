# Digital OMR Cloud — Security & Privacy Architecture

This document outlines the security controls, privacy safeguards, and OWASP compliance mechanisms implemented in Digital OMR Cloud.

---

## 1. Authentication & Session Security

- **Argon2id Hashing**: Passwords are hashed using the Argon2id standard (RFC 9106) with memory cost $65,536\text{ KB}$ (64 MB), 2 time iterations, and 16-byte random salts.
- **Signed JSON Web Tokens (JWT)**: Cryptographically signed via HMAC-SHA256 (`HS256`).
- **Session Expiration**: Tokens expire in 24 hours (`ACCESS_TOKEN_EXPIRE_MINUTES=1440`).
- **Timing-Safe Password Comparison**: Argon2 verification prevents timing attacks on authentication routes.
- **Account Activation**: Deactivated users cannot refresh or authenticate requests.

---

## 2. Role-Based Access Control (RBAC) & IDOR Protection

- **Strict Backend RBAC**: Hiding UI buttons is never treated as security. Every protected route enforces authorization dependencies:
  - `require_admin`: Restricts user management, teacher creation, and result publication strictly to Administrators.
  - `require_teacher_or_admin`: Restricts examination operations to authorized staff.
  - `check_exam_access(exam_id)`: Enforces that teachers can **only** view or modify examinations they either created or were explicitly assigned to by an administrator. Cross-examination access attempts return HTTP 403 Forbidden.

---

## 3. Storage Privacy & Image Security

- **Never Publicly Accessible**: Student sheets and camera photos are never saved in public web roots.
- **Private Storage Keys**: Database stores opaque storage keys (e.g. `uploads/a1f8c4..._capture.jpg`) rather than public URLs.
- **Authenticated Streaming**: Image endpoints (`/api/submissions/{id}/images/original` and `rectified`) verify user JWT authorization and examination access permissions before streaming bytes.
- **Cryptographic File Hash (SHA-256)**: Stored for every sheet to identify and flag duplicate submissions.

---

## 4. File Upload Safeguards

- **Magic Byte Verification**: File payloads are verified using initial magic byte signatures:
  - JPEG: `\xff\xd8\xff`
  - PNG: `\x89PNG\r\n\x1a\n`
  - WebP: `RIFF....WEBP`
- **Rejection of Executables & Archives**: ZIP files, tarballs, and executables are rejected immediately with HTTP 400.
- **Decompression Bomb Protection**: Image dimensions and file sizes are strictly capped (`MAX_UPLOAD_SIZE_BYTES=15MB`).

---

## 5. Spreadsheet Formula Injection Defense (CSV / Excel Injection)

When exporting marks to Excel or CSV, malicious students or input strings could attempt formula execution (e.g., `=cmd|' /C calc'!A0` or `=HYPERLINK(...)`).

- **Sanitization Layer**: Any cell starting with `=, +, -, @, \t, \r` is automatically neutralized by prefixing with `'`:
```python
def sanitize_formula_injection(val: Any) -> Any:
    if val is None:
        return ""
    s_val = str(val).strip()
    if s_val and s_val[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s_val}"
    return s_val
```

---

## 6. Comprehensive Audit Logging

- **Audit Log Table**: Records every significant system event (login, examination creation, rescoring, teacher assignment, result publication) along with timestamp, user ID, and IP address.
- **Immutable Review Events**: Whenever a teacher overrides a detected answer, a `ReviewEvent` record captures the reviewer's ID, timestamp, original value, revised value, and mandatory reason.
