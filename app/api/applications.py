import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.job_application import JobApplication
from app.models.resume_variant import ResumeVariant
from app.schemas.application import (
    ApplicationCreate,
    ApplicationBatchCreate,
    ApplicationResponse,
    ResumeVariantResponse,
)
from app.tasks.tailoring_tasks import tailor_application, batch_tailor

router = APIRouter(prefix="/applications", tags=["Applications"])


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    data: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.id == data.job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    existing = await db.execute(
        select(JobApplication).where(
            JobApplication.user_id == current_user.id,
            JobApplication.job_id == data.job_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application already exists for this job",
        )

    application = JobApplication(
        user_id=current_user.id,
        job_id=data.job_id,
        status="pending",
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)

    tailor_application.delay(str(application.id))

    return application


@router.post("/batch", response_model=list[ApplicationResponse], status_code=status.HTTP_201_CREATED)
async def batch_create_applications(
    data: ApplicationBatchCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    applications = []
    for job_id in data.job_ids:
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            continue

        existing = await db.execute(
            select(JobApplication).where(
                JobApplication.user_id == current_user.id,
                JobApplication.job_id == job_id,
            )
        )
        if existing.scalar_one_or_none():
            continue

        application = JobApplication(
            user_id=current_user.id,
            job_id=job_id,
            status="pending",
        )
        db.add(application)
        applications.append(application)

    await db.commit()
    for app in applications:
        await db.refresh(app)

    if applications:
        batch_tailor.delay([str(a.id) for a in applications])

    return applications


@router.get("/", response_model=list[ApplicationResponse])
async def list_applications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    application_status: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
):
    query = select(JobApplication).where(JobApplication.user_id == current_user.id)

    if application_status:
        query = query.where(JobApplication.status == application_status)

    query = query.order_by(JobApplication.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobApplication).where(
            JobApplication.id == application_id,
            JobApplication.user_id == current_user.id,
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


@router.patch("/{application_id}/approve", response_model=ApplicationResponse)
async def approve_application(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobApplication).where(
            JobApplication.id == application_id,
            JobApplication.user_id == current_user.id,
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    if application.status not in ("ready_to_apply", "pending"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve application in '{application.status}' status",
        )

    application.status = "approved"
    await db.commit()
    await db.refresh(application)

    # TODO: Trigger auto-apply task (Phase 5)

    return application


@router.patch("/{application_id}/apply", response_model=ApplicationResponse)
async def trigger_apply(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobApplication).where(
            JobApplication.id == application_id,
            JobApplication.user_id == current_user.id,
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    if application.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application must be approved before applying",
        )

    application.status = "applying"
    await db.commit()
    await db.refresh(application)

    # TODO: Trigger Celery apply task (Phase 5)

    return application


@router.get("/{application_id}/resume-variant", response_model=ResumeVariantResponse)
async def get_resume_variant(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ResumeVariant).where(
            ResumeVariant.application_id == application_id,
            ResumeVariant.user_id == current_user.id,
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume variant not found for this application",
        )
    return variant


@router.get("/{application_id}/download-pdf")
async def download_resume_pdf(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ResumeVariant).where(
            ResumeVariant.application_id == application_id,
            ResumeVariant.user_id == current_user.id,
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume variant not found for this application",
        )

    if not variant.compiled_pdf_path or not os.path.exists(variant.compiled_pdf_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compiled PDF not available",
        )

    return FileResponse(
        path=variant.compiled_pdf_path,
        media_type="application/pdf",
        filename=f"tailored_resume_{application_id}.pdf",
    )


@router.get("/{application_id}/download-tex")
async def download_resume_tex(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ResumeVariant).where(
            ResumeVariant.application_id == application_id,
            ResumeVariant.user_id == current_user.id,
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume variant not found for this application",
        )

    from fastapi.responses import Response
    return Response(
        content=variant.latex_source,
        media_type="application/x-tex",
        headers={"Content-Disposition": f"attachment; filename=tailored_resume_{application_id}.tex"},
    )


@router.post("/{application_id}/retailor", response_model=ApplicationResponse)
async def retailor_application(
    application_id: uuid.UUID,
    template: str = Query("resume_classic", regex="^resume_(classic|modern|minimal)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobApplication).where(
            JobApplication.id == application_id,
            JobApplication.user_id == current_user.id,
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    if application.status in ("applying", "applied"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retailor application in '{application.status}' status",
        )

    application.status = "pending"
    await db.commit()
    await db.refresh(application)

    tailor_application.delay(str(application.id), template)

    return application
