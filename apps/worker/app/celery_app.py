from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "dolos_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    worker_prefetch_multiplier=1,
    # Generation jobs are long-running (GPU-bound); avoid killing them via
    # visibility timeout resends while a worker is legitimately still busy.
    broker_transport_options={"visibility_timeout": 3600 * 4},
)
