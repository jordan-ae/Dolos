import json

import redis

from app.config import get_settings

settings = get_settings()

redis_client = redis.from_url(settings.redis_url, decode_responses=True)


def job_channel(job_id: str) -> str:
    return f"job:{job_id}:updates"


def publish_status(job_id: str, stage: str, *, error: str | None = None,
                    preview_url: str | None = None, export_url: str | None = None) -> None:
    payload = {
        "job_id": job_id,
        "stage": stage,
        "error": error,
        "preview_url": preview_url,
        "export_url": export_url,
    }
    redis_client.publish(job_channel(job_id), json.dumps(payload))
