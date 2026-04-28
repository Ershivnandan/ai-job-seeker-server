from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.resumes import router as resumes_router
from app.api.jobs import router as jobs_router
from app.api.applications import router as applications_router
from app.api.platforms import router as platforms_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(resumes_router)
api_router.include_router(jobs_router)
api_router.include_router(applications_router)
api_router.include_router(platforms_router)
