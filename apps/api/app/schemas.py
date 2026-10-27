from datetime import datetime

from pydantic import BaseModel

from app.models import JobStage


class GenerateRequest(BaseModel):
    script: str
    voice_id: str | None = None
    avatar_ref: str | None = None


class GenerateResponse(BaseModel):
    job_id: str


class JobResponse(BaseModel):
    job_id: str
    stage: JobStage
    error: str | None = None
    preview_url: str | None = None
    export_url: str | None = None
    created_at: datetime
    updated_at: datetime


class JobStatusMessage(BaseModel):
    job_id: str
    stage: JobStage
    error: str | None = None
    preview_url: str | None = None
    export_url: str | None = None
