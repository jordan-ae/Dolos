import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class JobStage(str, enum.Enum):
    QUEUED = "queued"
    TTS = "tts"
    LIPSYNC = "lipsync"
    ANIMATING = "animating"
    COMPOSITING = "compositing"
    DONE = "done"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    script: Mapped[str] = mapped_column(Text)
    voice_id: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_ref: Mapped[str | None] = mapped_column(String, nullable=True)

    stage: Mapped[JobStage] = mapped_column(Enum(JobStage), default=JobStage.QUEUED)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    preview_key: Mapped[str | None] = mapped_column(String, nullable=True)
    export_key: Mapped[str | None] = mapped_column(String, nullable=True)
    export_requested: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
