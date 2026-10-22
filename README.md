# Digital OMR Cloud — Multi-Teacher Online OMR Sheet Evaluation System

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![OpenCV](https://img.shields.io/badge/OpenCV-Headless-5C3EE8.svg?logo=opencv&logoColor=white)](https://opencv.org/)
[![React](https://img.shields.io/badge/React-18.2+-61DAFB.svg?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.2+-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4+-38B2AC.svg?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![Tests](https://img.shields.io/badge/Pytest-15%20Passed-emerald.svg)](https://docs.pytest.org/)

Digital OMR Cloud is a complete, production-ready, cloud-deployable web application that evaluates printed multiple-choice OMR answer sheets using ordinary mobile phone cameras and computer vision—**without requiring expensive, dedicated OMR optical scanning machines**.

---

## 1. Key Capabilities

- **Zero Dedicated Hardware**: Uses ordinary office black-and-white printers and mobile phone cameras.
- **Synchronized Coordinate Geometry**: The ReportLab PDF generator and OpenCV detection engine share the exact same mathematical layout coordinate model (`OMRLayoutConfig`), ensuring sub-millimeter bubble alignment.
- **Robust Computer Vision Pipeline**:
  - Validates image magic bytes (protects against decompression bombs and arbitrary uploads).
  - Assesses blur (Laplacian variance), glare, underexposure, and resolution.
  - Automatically identifies 4 solid corner registration squares and rectifies perspective distortion.
  - Measures ink density strictly inside the inner 70% radius to eliminate false positives from printed circular borders.
  - Accurately classifies options: `A`, `B`, `C`, `D`, `BLANK`, `MULTIPLE`, and `REVIEW`.
- **Multi-Teacher Collaboration & RBAC**:
  - Administrators manage examinations, assign teachers, configure marking schemes, approve final marks, and review audit logs.
  - Teachers capture sheets with mobile cameras, upload batches, resolve flagged reviews, and export provisional marks.
  - Strict backend authorization ensures cross-exam access control.
- **Automated Scoring & Rescoring Engine**: Configurable positive marks, negative marks, blank marks, and multiple-mark penalties with audit-justified rescoring.
- **Dedicated Human Review Interface**: Side-by-side rectified image inspection with interactive zoom, diagnostic ink density indicators, and teacher override controls.
- **Exporting & Formula Injection Protection**: Formula-sanitized CSV and formatted Excel (`.xlsx`) downloads.

---

## 2. Technology Stack

- **Backend**: Python 3.12, FastAPI, OpenCV, NumPy, ReportLab, Pydantic v2, SQLAlchemy, Alembic, Argon2id.
- **Task Queue**: Redis with background worker and automatic high-performance concurrent ThreadPool fallback.
- **Storage**: Private object storage compatible with S3 (AWS S3, MinIO, Cloudflare R2) and local storage for development.
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Lucide icons, responsive mobile camera viewport.
- **Containerization**: Docker, Docker Compose, Nginx.

---

## 3. Project Structure

```
digital-omr-cloud/
├── backend/
│   ├── app/
│   │   ├── api/            # REST API endpoints (Auth, Exams, Batches, Reviews, Reports)
│   │   ├── auth/           # Argon2id password hashing, JWT sessions, RBAC dependencies
│   │   ├── models/         # SQLAlchemy database models
│   │   ├── schemas/        # Pydantic validation schemas
│   │   ├── omr/            # Layout configuration, ReportLab generator, OpenCV pipeline
│   │   ├── services/       # Scoring engine, private storage, audit logger
│   │   ├── workers/        # Asynchronous batch processing queue and worker tasks
│   │   ├── reports/        # Formula-sanitized CSV and styled Excel exporters
│   │   ├── config.py       # Pydantic BaseSettings environment loader
│   │   ├── database.py     # Database engine & session maker
│   │   └── main.py         # FastAPI application entry point
│   ├── migrations/         # Alembic database migrations
│   ├── tests/              # Pytest automated test suite (15 passed)
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/     # Navbar, CameraModal, ZoomModal
│   │   ├── pages/          # Login, Dashboard, Exams, Details, ReviewQueue, Users
│   │   ├── services/       # Typed API client
│   │   ├── types/          # TypeScript domain interfaces
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── docker/
│   ├── Dockerfile.frontend
│   └── nginx.conf
├── docs/                   # Deployment guide, calibration, security, acceptance tests
├── generated/              # Sample generated A4 OMR PDF
├── scripts/                # Helper utilities (generate_sample_pdf.py)
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 4. Quick Start (Local Development)

### Prerequisites
- Python 3.12+
- Node.js 18+ (LTS)

### Backend Setup
1. Open a terminal in the project root:
```bash
cd backend
python -m pip install -r requirements.txt
```

2. Run automated test suite:
```bash
python -m pytest backend/tests -v
```

3. Start backend development server:
```bash
python -m uvicorn backend.app.main:app --reload --port 8000
```
API Documentation will be available at: `http://localhost:8000/docs`

### Frontend Setup
1. Open a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 5. Pre-Seeded Demonstration Credentials

The application automatically seeds initial accounts on first startup:

| Role | Email Address | Password | Permissions |
|---|---|---|---|
| **Administrator** | `admin@digitalomr.edu` | `AdminSecurePassword123!` | Full control, teacher management, publish marks |
| **Teacher** | `teacher@digitalomr.edu` | `Teacher1234!` | Evaluation station, photo capture, review queue |

---

## 6. Docker Deployment

Deploy all tiers (PostgreSQL, Redis, Backend, Worker, Frontend SPA) with Docker Compose:

```bash
docker compose up -d --build
```
Access the application at `http://localhost`.

For complete production cloud instructions, see [`docs/deployment_guide.md`](file:///docs/deployment_guide.md).

---

## 7. Documentation Directory

- [**Production Cloud Deployment Guide**](file:///docs/deployment_guide.md)
- [**Threshold Calibration & Accuracy Validation**](file:///docs/calibration_guide.md)
- [**Security & OWASP Safeguards Checklist**](file:///docs/security_checklist.md)
- [**Troubleshooting Guide**](file:///docs/troubleshooting_guide.md)
- [**Field Acceptance Testing Checklist**](file:///docs/acceptance_test_checklist.md)
- [**Generated Sample OMR PDF (100 Questions)**](file:///generated/Sample_OMR_100Q.pdf)
