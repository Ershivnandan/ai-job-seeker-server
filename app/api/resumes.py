import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import get_current_user, get_current_user_from_token_param
from app.models.user import User
from app.models.resume import Resume
from app.models.skill import Skill
from app.schemas.resume import ResumeResponse, ResumeUploadResponse
from app.schemas.skill import SkillResponse
from app.services.storage_service import storage_service
from app.tasks.resume_tasks import parse_resume

router = APIRouter(prefix="/resumes", tags=["Resumes"])


@router.post("/upload", response_model=ResumeUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted",
        )

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit",
        )

    file_path, file_hash = await storage_service.save_resume(file.filename, content)

    resume = Resume(
        user_id=current_user.id,
        filename=file.filename,
        file_path=file_path,
        file_hash=file_hash,
        parse_status="pending",
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    parse_resume.delay(str(resume.id))

    return ResumeUploadResponse(
        id=resume.id,
        filename=resume.filename,
        parse_status=resume.parse_status,
        message="Resume uploaded successfully. Parsing will begin shortly.",
    )


@router.get("/", response_model=list[ResumeResponse])
async def list_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return resume


@router.get("/{resume_id}/download")
async def download_resume(
    resume_id: uuid.UUID,
    preview: bool = Query(False),
    current_user: User = Depends(get_current_user_from_token_param),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    if not os.path.exists(resume.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

    if preview:
        with open(resume.file_path, "rb") as f:
            content = f.read()
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"},
        )

    return FileResponse(
        path=resume.file_path,
        media_type="application/pdf",
        filename=resume.filename,
    )


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    storage_service.delete_file(resume.file_path)
    await db.delete(resume)
    await db.commit()


@router.patch("/{resume_id}/primary", response_model=ResumeResponse)
async def set_primary_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )
    resumes = result.scalars().all()

    target = None
    for resume in resumes:
        if resume.id == resume_id:
            resume.is_primary = True
            target = resume
        else:
            resume.is_primary = False

    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    await db.commit()
    await db.refresh(target)
    return target


@router.get("/{resume_id}/skills", response_model=list[SkillResponse])
async def get_resume_skills(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    skills_result = await db.execute(
        select(Skill).where(Skill.resume_id == resume_id).order_by(Skill.category, Skill.name)
    )
    return skills_result.scalars().all()


@router.post("/{resume_id}/reparse", response_model=ResumeUploadResponse)
async def reparse_resume(
    resume_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    resume.parse_status = "pending"
    resume.parsed_text = None
    resume.parsed_json = None
    await db.commit()

    parse_resume.delay(str(resume.id))

    return ResumeUploadResponse(
        id=resume.id,
        filename=resume.filename,
        parse_status="pending",
        message="Resume re-parsing initiated.",
    )
