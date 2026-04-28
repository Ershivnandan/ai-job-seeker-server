import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class JobSearchParams(BaseModel):
    query: str
    location: Optional[str] = None
    platforms: Optional[list[str]] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    remote_type: Optional[str] = None


class JobResponse(BaseModel):
    id: uuid.UUID
    platform_id: uuid.UUID
    external_id: Optional[str] = None
    url: str
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    description: str
    remote_type: Optional[str] = None
    posted_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class JobMatchResponse(BaseModel):
    job: JobResponse
    match_score: float
    match_details: Optional[dict] = None


class JobSearchStatusResponse(BaseModel):
    task_id: str
    status: str
    jobs_found: int = 0
