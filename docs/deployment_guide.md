# Digital OMR Cloud — Production Cloud Deployment Guide

This guide details step-by-step instructions to deploy **Digital OMR Cloud** on production infrastructure.

---

## 1. Cloud Architecture Overview

In production, Digital OMR Cloud comprises 5 dedicated tiers:
1. **Frontend Service**: React SPA served by Nginx or distributed via Cloudflare / AWS CloudFront.
2. **Backend API Service**: Python 3.12 FastAPI application running behind an ASGI server (Uvicorn / Gunicorn).
3. **Background Worker**: Dedicated container executing asynchronous image processing and OpenCV OMR detection.
4. **Database**: Managed PostgreSQL 15+ (AWS RDS, DigitalOcean Managed PostgreSQL, Supabase, or self-hosted).
5. **Private Object Storage**: AWS S3, MinIO, or Cloudflare R2 configured with private ACLs (never public).
6. **Task Broker / Cache**: Managed Redis 7+ (AWS ElastiCache, DigitalOcean Managed Redis, or self-hosted).

---

## 2. Infrastructure Costs & Hosting Recommendations

> [!NOTE] Cost Transparency Notice
> Cloud hosting services require a payment method. Digital OMR Cloud can be operated in low-cost single-node VPS mode (~$10–$20/mo) or high-availability managed multi-tier mode (~$60–$120/mo).

| Tier | Option A: Low-Cost Single VPS (Hetzner / DigitalOcean) | Option B: Production Managed Cloud (AWS / GCP) |
|---|---|---|
| **Web & Worker** | 4 vCPU, 8 GB RAM VPS (~$14–$24/month) | AWS ECS Fargate or App Runner (~$40/month) |
| **Database** | Dockerized PostgreSQL (included on VPS) | AWS RDS PostgreSQL db.t4g.micro (~$18/month) |
| **Queue / Redis** | Dockerized Redis (included on VPS) | AWS ElastiCache t4g.micro (~$15/month) |
| **Object Storage**| MinIO on VPS disk or Cloudflare R2 (~$0–$5) | AWS S3 Standard (~$0.023/GB/month) |
| **SSL / HTTPS** | Let's Encrypt Certbot (Free) | AWS Certificate Manager (Free) |
| **Estimated Total**| **~$15 – $25 / month** | **~$75 – $120 / month** |

---

## 3. Step-by-Step Deployment Instructions

### Step 1: Provision Server and Install Docker
On an Ubuntu 22.04 / 24.04 LTS server:
```bash
sudo apt-get update && sudo apt-get install -y curl git ufw
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
sudo systemctl enable docker
```

Configure firewall:
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

### Step 2: Clone Repository and Configure Environment Variables
```bash
git clone https://github.com/your-org/digital-omr-cloud.git /opt/digital-omr-cloud
cd /opt/digital-omr-cloud
cp .env.example .env
```

Generate a secure 64-character secret key:
```bash
openssl rand -hex 32
```

Edit `.env` using `nano .env`:
```ini
PROJECT_NAME="Digital OMR Cloud"
ENVIRONMENT="production"
DEBUG=false

# PostgreSQL Connection String
DATABASE_URL="postgresql+psycopg2://postgres:YOUR_STRONG_DB_PASS@postgres:5432/omr_cloud"

# Security
SECRET_KEY="<paste_output_of_openssl_rand_hex_32>"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Task Queue
REDIS_URL="redis://redis:6379/0"

# Storage Configuration (Private S3 or Local)
STORAGE_BACKEND="local"
STORAGE_LOCAL_DIR="/app/storage"

# If using AWS S3 / Cloudflare R2:
# STORAGE_BACKEND="s3"
# S3_BUCKET_NAME="institution-omr-private-sheets"
# S3_ACCESS_KEY="AKIA..."
# S3_SECRET_KEY="..."
# S3_REGION="us-east-1"
# S3_ENDPOINT_URL=""

# Initial Admin Bootstrap
INITIAL_ADMIN_EMAIL="admin@yourinstitution.edu"
INITIAL_ADMIN_PASSWORD="StrongAdminPassword2026!"
INITIAL_ADMIN_NAME="Primary Examination Controller"
```

---

### Step 3: Run Database Migrations and Bootstrap Database
Digital OMR Cloud will automatically run schema generation on first launch. If you wish to run Alembic migrations manually:
```bash
docker compose run --rm backend alembic -c backend/alembic.ini upgrade head
```

---

### Step 4: Launch Application with Docker Compose
```bash
docker compose up -d --build
```

Verify that all 5 containers are running and healthy:
```bash
docker compose ps
```

Check backend application logs:
```bash
docker compose logs -f backend
```

---

### Step 5: Configure HTTPS with Let's Encrypt (Certbot)
Install Certbot for automated TLS certificate issuance:
```bash
sudo apt-get install -y certbot python3-certbot-nginx
```

If running Nginx as the host reverse proxy:
```bash
sudo certbot --nginx -d omr.yourinstitution.edu
```

---

### Step 6: Initial Administrator Login and Teacher Invitations
1. Open `https://omr.yourinstitution.edu` in your web browser.
2. Sign in using the `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` defined in `.env`.
3. In the top navigation bar, click **Teachers**.
4. Click **Add Teacher** to create accounts for faculty members.
5. Provide the teacher with their temporary password and instruct them to update their password under their profile upon first login.

---

### Step 7: Verify Health and Automated Endpoints
Test health endpoint:
```bash
curl -i https://omr.yourinstitution.edu/health
```
Expected response:
```json
{
  "status": "healthy",
  "service": "Digital OMR Cloud",
  "environment": "production",
  "version": "1.0.0"
}
```

---

## 4. Backup and Disaster Recovery

### Automated Database Backups
Create a cron job `/etc/cron.daily/backup-omr-db`:
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/omr_db"
mkdir -p "$BACKUP_DIR"
docker exec omr_postgres pg_dump -U postgres omr_cloud | gzip > "$BACKUP_DIR/omr_$(date +\%Y\%m\%d_\%H\%M\%S).sql.gz"
# Keep 30 days of retention
find "$BACKUP_DIR" -type f -name "*.sql.gz" -mtime +30 -delete
```
Make it executable:
```bash
sudo chmod +x /etc/cron.daily/backup-omr-db
```

### Database Restore Procedure
To restore from backup:
```bash
gunzip -c /var/backups/omr_db/omr_20261021.sql.gz | docker exec -i omr_postgres psql -U postgres omr_cloud
```
