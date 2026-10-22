from fastapi import APIRouter

from backend.app.api.auth_routes import router as auth_router
from backend.app.api.user_routes import router as user_router
from backend.app.api.examination_routes import router as exam_router
from backend.app.api.template_routes import router as template_router
from backend.app.api.batch_routes import router as batch_router
from backend.app.api.submission_routes import router as submission_router
from backend.app.api.review_routes import router as review_router
from backend.app.api.report_routes import router as report_router
from backend.app.api.dashboard_routes import router as dashboard_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(user_router)
api_router.include_router(exam_router)
api_router.include_router(template_router)
api_router.include_router(batch_router)
api_router.include_router(submission_router)
api_router.include_router(review_router)
api_router.include_router(report_router)
api_router.include_router(dashboard_router)
