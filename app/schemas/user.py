import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    years_experience: Optional[int] = None
    preferred_roles: Optional[list[str]] = None
    preferred_locations: Optional[list[str]] = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    years_experience: Optional[int] = None
    preferred_roles: Optional[list[str]] = None
    preferred_locations: Optional[list[str]] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
