import subprocess
import tempfile
import time

from app.pipeline.base import PipelineContext


class StubPipeline:
    """Fakes each stage with a short sleep and a real (but trivial) ffmpeg
    render, so the full queued->tts->lipsync->animating->compositing->done
    flow, WebSocket updates, and preview playback can be verified end to end
    before the GPU-backed OpenMontage models are wired in."""

    def synthesize_voice(self, ctx: PipelineContext) -> None:
        time.sleep(2)
        ctx.audio_path = None

    def lipsync(self, ctx: PipelineContext) -> None:
        time.sleep(2)
        ctx.lipsync_frames_dir = None

    def animate(self, ctx: PipelineContext) -> None:
        time.sleep(2)
        ctx.animated_frames_dir = None

    def _render_test_clip(self, duration: int) -> str:
        out_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=640x360:rate=24",
                "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
                "-pix_fmt", "yuv420p",
                "-shortest",
                out_path,
            ],
            check=True,
            capture_output=True,
        )
        return out_path

    def composite_preview(self, ctx: PipelineContext) -> str:
        return self._render_test_clip(duration=3)

    def composite_full_res(self, ctx: PipelineContext) -> str:
        return self._render_test_clip(duration=3)
