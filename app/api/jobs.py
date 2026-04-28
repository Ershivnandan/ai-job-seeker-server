import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.job_platform import JobPlatform
from app.schemas.job import JobResponse, JobSearchParams, JobSearchStatusResponse, JobMatchResponse
from app.tasks.job_tasks import search_jobs as search_jobs_task

router = APIRouter(prefix="/jobs", tags=["Jobs"])

DEFAULT_PLATFORMS = ["linkedin", "indeed", "naukri"]


@router.post("/search", response_model=JobSearchStatusResponse)
async def search_jobs(
    params: JobSearchParams,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    platforms = params.platforms or DEFAULT_PLATFORMS

    platform_result = await db.execute(
        select(JobPlatform.name).where(JobPlatform.is_active == True)
    )
    active_platforms = [p for p in platform_result.scalars().all()]
    valid_platforms = [p for p in platforms if p in active_platforms]

    if not valid_platforms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No valid active platforms. Available: {active_platforms}",
        )

    task = search_jobs_task.delay(
        user_id=str(current_user.id),
        keywords=params.query,
        location=params.location,
        platforms=valid_platforms,
        max_results=25,
    )

    return JobSearchStatusResponse(
        task_id=task.id,
        status="queued",
        jobs_found=0,
    )


@router.get("/search/status/{task_id}", response_model=JobSearchStatusResponse)
async def get_search_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    from app.tasks.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)

    if result.ready():
        info = result.result or {}
        return JobSearchStatusResponse(
            task_id=task_id,
            status="completed",
            jobs_found=info.get("jobs_found", 0) if isinstance(info, dict) else 0,
        )
    elif result.failed():
        return JobSearchStatusResponse(
            task_id=task_id,
            status="failed",
            jobs_found=0,
        )
    else:
        return JobSearchStatusResponse(
            task_id=task_id,
            status="processing",
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
