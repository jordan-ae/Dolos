import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()

redis_client = redis.from_url(settings.redis_url, decode_responses=True)


def job_channel(job_id: str) -> str:
    return f"job:{job_id}:updates"
