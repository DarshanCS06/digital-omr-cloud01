# ==========================================
# Multi-stage Dockerfile for Digital OMR Cloud
# Vidyakashi Study Circle
# Single-origin SPA + FastAPI Engine
# ==========================================

# Stage 1: Build Vite React Frontend SPA
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci --prefer-offline --no-audit || npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Backend + OpenCV + PyMuPDF Engine
FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000

WORKDIR /app

# Install system dependencies required for OpenCV, PyPDFium2, and Tesseract OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    tesseract-ocr \
    tesseract-ocr-eng \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy built frontend assets from Stage 1 into backend SPA path
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Copy backend application and assets
COPY backend/ /app/backend/
COPY generated/ /app/generated/
COPY scripts/ /app/scripts/

# Create persistent storage directories
RUN mkdir -p /app/storage /app/uploads /app/rectified /app/data

# Non-root user setup for container security
RUN useradd -m -u 1000 omruser && \
    chown -R omruser:omruser /app

USER omruser

EXPOSE 8000

# Start server dynamically listening on cloud-assigned $PORT (Render/Railway/Fly/CloudRun)
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
