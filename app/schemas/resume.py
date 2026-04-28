import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ResumeResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    is_primary: bool
    parse_status: str
    parsed_json: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ResumeUploadResponse(BaseModel):
    id: uuid.UUID
    filename: str
    parse_status: str
    message: str
