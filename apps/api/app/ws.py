import asyncio
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Job, JobStage
from app.redis_client import job_channel, redis_client
from app.storage import signed_url

router = APIRouter(tags=["jobs"])


def _job_message(job: Job) -> dict:
    return {
        "job_id": job.id,
        "stage": job.stage.value,
        "error": job.error,
        "preview_url": signed_url(job.preview_key),
        "export_url": signed_url(job.export_key),
    }


@router.websocket("/ws/jobs/{job_id}")
async def job_updates(websocket: WebSocket, job_id: str, db: AsyncSession = Depends(get_db)):
    await websocket.accept()

    job = await db.get(Job, job_id)
    if job is None:
        await websocket.close(code=4004, reason="job not found")
        return

    await websocket.send_json(_job_message(job))
    if job.stage in (JobStage.DONE, JobStage.FAILED):
        await websocket.close()
        return

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(job_channel(job_id))

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30.0)
            if message is not None:
                payload = json.loads(message["data"])
                await websocket.send_json(payload)
                if payload.get("stage") in (JobStage.DONE.value, JobStage.FAILED.value):
                    break
            else:
                # Periodic no-op check keeps the connection alive and lets us
                # notice client disconnects even during quiet stages.
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(job_channel(job_id))
        await pubsub.aclose()
        await websocket.close()
