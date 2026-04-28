import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PlatformResponse(BaseModel):
    id: uuid.UUID
    name: str
    base_url: str
    is_active: bool

    class Config:
        from_attributes = True


class CredentialCreate(BaseModel):
    username: str
    password: str


class CredentialResponse(BaseModel):
    id: uuid.UUID
    platform_id: uuid.UUID
    platform_name: str
    username: Optional[str] = None
    is_valid: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
