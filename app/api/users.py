import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.skill import Skill
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.skill import SkillCreate, SkillUpdate, SkillResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_profile(
    updates: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/me/skills", response_model=list[SkillResponse])
async def get_skills(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Skill).where(Skill.user_id == current_user.id).order_by(Skill.category, Skill.name)
    )
    return result.scalars().all()


@router.post("/me/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def add_skill(
    skill_data: SkillCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    skill = Skill(
        user_id=current_user.id,
        name=skill_data.name,
        category=skill_data.category,
        proficiency=skill_data.proficiency,
        years_used=skill_data.years_used,
        source="manual",
        confidence=1.0,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill


@router.put("/me/skills/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: uuid.UUID,
    updates: SkillUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.user_id == current_user.id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(skill, field, value)

    await db.commit()
    await db.refresh(skill)
    return skill


@router.delete("/me/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.user_id == current_user.id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    await db.delete(skill)
    await db.commit()
