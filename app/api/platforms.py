import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.job_platform import JobPlatform, PlatformCredential
from app.schemas.platform import PlatformResponse, CredentialCreate, CredentialResponse
from app.services.encryption_service import encryption_service

router = APIRouter(prefix="/platforms", tags=["Platforms"])


@router.get("/", response_model=list[PlatformResponse])
async def list_platforms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(JobPlatform).where(JobPlatform.is_active == True))
    return result.scalars().all()


@router.post("/{platform_id}/credentials", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def save_credentials(
    platform_id: uuid.UUID,
    data: CredentialCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(JobPlatform).where(JobPlatform.id == platform_id))
    platform = result.scalar_one_or_none()
    if not platform:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform not found")

    existing = await db.execute(
        select(PlatformCredential).where(
            PlatformCredential.user_id == current_user.id,
            PlatformCredential.platform_id == platform_id,
        )
    )
    credential = existing.scalar_one_or_none()

    encrypted_pw = encryption_service.encrypt(data.password)

    if credential:
        credential.username = data.username
        credential.encrypted_password = encrypted_pw
        credential.is_valid = True
    else:
        credential = PlatformCredential(
            user_id=current_user.id,
            platform_id=platform_id,
            username=data.username,
            encrypted_password=encrypted_pw,
            is_valid=True,
        )
        db.add(credential)

    await db.commit()
    await db.refresh(credential)

    return CredentialResponse(
        id=credential.id,
        platform_id=credential.platform_id,
        platform_name=platform.name,
        username=credential.username,
        is_valid=credential.is_valid,
        last_login_at=credential.last_login_at,
        created_at=credential.created_at,
    )


@router.delete("/{platform_id}/credentials", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credentials(
    platform_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlatformCredential).where(
            PlatformCredential.user_id == current_user.id,
            PlatformCredential.platform_id == platform_id,
        )
    )
    credential = result.scalar_one_or_none()
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credentials not found")

    await db.delete(credential)
    await db.commit()
