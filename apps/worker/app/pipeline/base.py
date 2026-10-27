from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class PipelineContext:
    job_id: str
    script: str
    voice_id: str | None = None
    avatar_ref: str | None = None
    # Optional reference voice sample (wav) for TTS voice cloning. When unset,
    # the TTS stage falls back to a built-in speaker preset.
    voice_ref_wav: str | None = None
    # Populated as stages complete, so later stages can consume earlier
    # stages' output without re-deriving it.
    audio_path: str | None = None
    lipsync_frames_dir: str | None = None
    animated_frames_dir: str | None = None
    # The matted + background-composited 1080p master, from which both the
    # preview and export renders are downscaled. Cached so the (expensive)
    # matting/compositing runs once per pipeline instance.
    composited_master_path: str | None = None
    artifacts: dict = field(default_factory=dict)


class Pipeline(Protocol):
    """One implementation runs stubbed (for e2e wiring), the other calls
    the real OpenMontage models. Both must produce the same artifacts so
    apps/worker/app/tasks.py can stay agnostic to which one is active."""

    def synthesize_voice(self, ctx: PipelineContext) -> None: ...

    def lipsync(self, ctx: PipelineContext) -> None: ...

    def animate(self, ctx: PipelineContext) -> None: ...

    def composite_preview(self, ctx: PipelineContext) -> str:
        """Returns the local file path of a low-res preview render."""
        ...

    def composite_full_res(self, ctx: PipelineContext) -> str:
        """Returns the local file path of the full-res export render."""
        ...
