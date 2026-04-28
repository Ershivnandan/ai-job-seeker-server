from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.router import api_router
from app.middleware.error_handler import register_exception_handlers
from app.database import engine, Base
from app.models import *  # noqa: F401, F403


async def seed_platforms(db):
    from sqlalchemy import select
    from app.models.job_platform import JobPlatform

    platforms = [
        {"name": "linkedin", "base_url": "https://www.linkedin.com"},
        {"name": "indeed", "base_url": "https://www.indeed.com"},
        {"name": "naukri", "base_url": "https://www.naukri.com"},
    ]
    for p in platforms:
        result = await db.execute(select(JobPlatform).where(JobPlatform.name == p["name"]))
        if not result.scalar_one_or_none():
            db.add(JobPlatform(**p))
    await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await seed_platforms(db)

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}
