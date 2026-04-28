import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SkillCreate(BaseModel):
    name: str
    category: Optional[str] = None
    proficiency: Optional[str] = None
    years_used: Optional[int] = None


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    proficiency: Optional[str] = None
    years_used: Optional[int] = None


class SkillResponse(BaseModel):
    id: uuid.UUID
    name: str
    category: Optional[str] = None
    proficiency: Optional[str] = None
    years_used: Optional[int] = None
    source: str
    confidence: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True
