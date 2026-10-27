from celery import Celery

from app.config import get_settings

settings = get_settings()

# Thin client used only to enqueue tasks by name. The API process does not
# import worker code (which pulls in GPU/ML deps), so task names below must
# match the @app.task names registered in apps/worker/app/tasks.py.
celery_client = Celery("dolos_api_client", broker=settings.redis_url, backend=settings.redis_url)

TASK_RUN_GENERATION = "worker.tasks.run_generation_pipeline"
TASK_RUN_EXPORT = "worker.tasks.run_export_render"


def enqueue_generation(job_id: str) -> None:
    celery_client.send_task(TASK_RUN_GENERATION, args=[job_id])


def enqueue_export(job_id: str) -> None:
    celery_client.send_task(TASK_RUN_EXPORT, args=[job_id])
