import uuid

from app.celery_app import celery_app
from app.database import get_session
from app.models import Job, JobStage
from app.pipeline import get_pipeline
from app.pipeline.base import PipelineContext
from app.redis_client import publish_status
from app.storage import signed_url, upload_file


def _set_stage(job_id: str, stage: JobStage, **kwargs) -> None:
    with get_session() as session:
        job = session.get(Job, job_id)
        job.stage = stage
        for key, value in kwargs.items():
            setattr(job, key, value)
        session.commit()

    with get_session() as session:
        job = session.get(Job, job_id)
        publish_status(
            job_id,
            stage.value,
            error=job.error,
            preview_url=signed_url(job.preview_key),
            export_url=signed_url(job.export_key),
        )


@celery_app.task(name="worker.tasks.run_generation_pipeline")
def run_generation_pipeline(job_id: str) -> None:
    with get_session() as session:
        job = session.get(Job, job_id)
        ctx = PipelineContext(
            job_id=job_id,
            script=job.script,
            voice_id=job.voice_id,
            avatar_ref=job.avatar_ref,
        )

    pipeline = get_pipeline()
    stages = [
        (JobStage.TTS, pipeline.synthesize_voice),
        (JobStage.LIPSYNC, pipeline.lipsync),
        (JobStage.ANIMATING, pipeline.animate),
    ]

    try:
        for stage, fn in stages:
            _set_stage(job_id, stage)
            fn(ctx)

        _set_stage(job_id, JobStage.COMPOSITING)
        preview_path = pipeline.composite_preview(ctx)
        preview_key = f"jobs/{job_id}/preview-{uuid.uuid4().hex}.mp4"
        upload_file(preview_path, preview_key)

        _set_stage(job_id, JobStage.DONE, preview_key=preview_key)
    except Exception as exc:
        _set_stage(job_id, JobStage.FAILED, error=str(exc))


@celery_app.task(name="worker.tasks.run_export_render")
def run_export_render(job_id: str) -> None:
    with get_session() as session:
        job = session.get(Job, job_id)
        ctx = PipelineContext(
            job_id=job_id,
            script=job.script,
            voice_id=job.voice_id,
            avatar_ref=job.avatar_ref,
        )

    pipeline = get_pipeline()
    try:
        # Re-run the generation stages so we have the intermediate artifacts
        # this pipeline instance needs to render a full-res composite. The
        # stub/real pipelines are cheap-per-stage-idempotent for MVP purposes;
        # a production version would cache stage artifacts instead of redoing
        # TTS/animation on every export.
        pipeline.synthesize_voice(ctx)
        pipeline.lipsync(ctx)
        pipeline.animate(ctx)

        export_path = pipeline.composite_full_res(ctx)
        export_key = f"jobs/{job_id}/export-{uuid.uuid4().hex}.mp4"
        upload_file(export_path, export_key)

        _set_stage(job_id, JobStage.DONE, export_key=export_key)
    except Exception as exc:
        _set_stage(job_id, JobStage.FAILED, error=str(exc))
