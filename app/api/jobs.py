import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.job import Job
from app.schemas.job import JobResponse, JobSearchParams, JobSearchStatusResponse

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("/search", response_model=JobSearchStatusResponse)
async def search_jobs(
    params: JobSearchParams,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # TODO: Trigger Celery task for job scraping (Phase 3)
    task_id = "placeholder-task-id"

    return JobSearchStatusResponse(
        task_id=task_id,
        status="queued",
        jobs_found=0,
    )


@router.get("/", response_model=list[JobResponse])
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    platform: str | None = Query(None),
    job_type: str | None = Query(None),
    remote_type: str | None = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
):
    query = select(Job).where(Job.is_active == True)

    if platform:
        query = query.join(Job.platform).filter_by(name=platform)
    if job_type:
        query = query.where(Job.job_type == job_type)
    if remote_type:
        query = query.where(Job.remote_type == remote_type)

    query = query.order_by(Job.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
