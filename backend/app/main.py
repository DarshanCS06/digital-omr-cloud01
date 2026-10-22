import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import engine, Base, SessionLocal
from backend.app.models.user import User, UserRole
from backend.app.models.template import TemplateVersion
from backend.app.omr.layout import OMRLayoutConfig
from backend.app.auth.security import hash_password
from backend.app.api import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("digital_omr")


def bootstrap_database():
    """Initializes tables and bootstraps initial admin user and template configurations."""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        # 1. Seed Initial Administrator
        admin = db.query(User).filter(User.email == settings.INITIAL_ADMIN_EMAIL.lower()).first()
        if not admin:
            admin = User(
                email=settings.INITIAL_ADMIN_EMAIL.lower(),
                full_name=settings.INITIAL_ADMIN_NAME,
                hashed_password=hash_password(settings.INITIAL_ADMIN_PASSWORD),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            logger.info(f"Bootstrapped Initial Admin: {admin.email}")

        # 2. Seed Default Teacher for Demonstration
        demo_teacher = db.query(User).filter(User.email == "teacher@digitalomr.edu").first()
        if not demo_teacher:
            demo_teacher = User(
                email="teacher@digitalomr.edu",
                full_name="Vidyakashi",
                hashed_password=hash_password("Teacher1234!"),
                role=UserRole.TEACHER,
                is_active=True,
            )
            db.add(demo_teacher)
            logger.info("Bootstrapped Demo Teacher: teacher@digitalomr.edu")
        elif demo_teacher.full_name != "Vidyakashi":
            demo_teacher.full_name = "Vidyakashi"

        # 3. Seed Default Template Versions (25Q, 50Q, 100Q, 200Q)
        for q_count in [25, 40, 50, 100, 150, 200]:
            name = f"OMR-A4-{q_count}Q-V1"
            tmpl = db.query(TemplateVersion).filter(TemplateVersion.name == name).first()
            if not tmpl:
                layout = OMRLayoutConfig(question_count=q_count)
                tmpl = TemplateVersion(
                    name=name,
                    question_count=q_count,
                    options_per_question=4,
                    layout_config=layout.to_dict(),
                )
                db.add(tmpl)

        db.commit()
    except Exception as e:
        logger.error(f"Error during bootstrap: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables and bootstrap
    logger.info("Starting Digital OMR Cloud backend...")
    bootstrap_database()
    yield
    logger.info("Shutting down Digital OMR Cloud backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Multi-Teacher Online OMR Sheet Evaluation System with Mobile Camera Capture and OpenCV Detection",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Central API Router
app.include_router(api_router)


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
def health_check():
    """Health check endpoint for cloud load balancers and deployment verification."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0",
    }


@app.get("/api/mobile-access", tags=["Mobile Access"])
def get_mobile_access_info():
    """Returns LAN Wi-Fi URL, Public HTTPS Mobile URL (if active), and scannable QR code data URLs."""
    import base64
    import io
    import os
    import socket
    import qrcode

    def _make_qr_data_url(url_str: str) -> str:
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(url_str)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"

    lan_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    lan_url = f"http://{lan_ip}:8000"
    tunnel_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", ".mobile_tunnel_url.txt")
    )
    public_url = None
    if os.path.isfile(tunnel_file):
        try:
            with open(tunnel_file, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val.startswith("http"):
                    public_url = val
        except Exception:
            pass

    primary_url = public_url or lan_url
    return {
        "primary_url": primary_url,
        "lan_url": lan_url,
        "public_url": public_url,
        "primary_qr_data_url": _make_qr_data_url(primary_url),
        "lan_qr_data_url": _make_qr_data_url(lan_url),
    }


# Serve Built Production Frontend Website (frontend/dist)
import os
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

FRONTEND_DIST = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
)

if os.path.isdir(FRONTEND_DIST):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend_assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa_website(full_path: str):
        if full_path:
            candidate = os.path.normpath(os.path.join(FRONTEND_DIST, full_path))
            if candidate.startswith(FRONTEND_DIST) and os.path.isfile(candidate):
                return FileResponse(candidate)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
