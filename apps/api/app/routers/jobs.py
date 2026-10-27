from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_client import enqueue_export, enqueue_generation
from app.database import get_db
from app.models import Job, JobStage
from app.schemas import GenerateRequest, GenerateResponse, JobResponse
from app.storage import signed_url

router = APIRouter(tags=["jobs"])


def _to_response(job: Job) -> JobResponse:
    return JobResponse(
        job_id=job.id,
        stage=job.stage,
        error=job.error,
        preview_url=signed_url(job.preview_key),
        export_url=signed_url(job.export_key),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate(body: GenerateRequest, db: AsyncSession = Depends(get_db)):
    if not body.script.strip():
        raise HTTPException(status_code=422, detail="script must not be empty")

    job = Job(script=body.script, voice_id=body.voice_id, avatar_ref=body.avatar_ref)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    enqueue_generation(job.id)

    return GenerateResponse(job_id=job.id)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _to_response(job)


@router.post("/jobs/{job_id}/export", response_model=JobResponse)
async def export_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.stage != JobStage.DONE:
        raise HTTPException(status_code=409, detail="job must reach 'done' stage before exporting")

    job.export_requested = True
    await db.commit()
    await db.refresh(job)

    enqueue_export(job.id)

    return _to_response(job)
