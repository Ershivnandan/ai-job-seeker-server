import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID


class ApplicationBatchCreate(BaseModel):
    job_ids: list[uuid.UUID]


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    match_score: Optional[float] = None
    match_details: Optional[dict] = None
    cover_letter: Optional[str] = None
    applied_at: Optional[datetime] = None
    error_log: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResumeVariantResponse(BaseModel):
    id: uuid.UUID
    latex_source: str
    compiled_pdf_path: Optional[str] = None
    tailoring_notes: Optional[dict] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
