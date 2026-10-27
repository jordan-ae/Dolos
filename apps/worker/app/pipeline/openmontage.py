"""Direct integration with OpenMontage (https://github.com/calesthio/OpenMontage).

OpenMontage is agent-first: its normal usage mode is an AI coding assistant
reading pipeline_defs/ and skills/pipelines/ and driving tools interactively
with human approval at each stage. There is no headless "run pipeline"
entrypoint. For an unattended backend job, we bypass the agent orchestration
and call the underlying Python tools directly - every tool subclasses
BaseTool and exposes a uniform `execute(inputs: dict) -> ToolResult`
(see tools/base_tool.py in the OpenMontage repo), and its own loader
explicitly supports being imported this way ("even when tools are imported
directly without going through the registry").

This module chains three tools to approximate the talking-head flow:
  1. tools.audio.piper_tts.PiperTTS       - free/local TTS -> wav
  2. tools.avatar.talking_head.TalkingHead - SadTalker photo+audio -> mp4
     (combines what our job stages call "lipsync" + "animating": SadTalker
     animates the face AND syncs lips to the driving audio in one pass.
     Note: TalkingHead's model="musetalk" branch is a stub in the upstream
     repo as of this writing and always fails - use model="sadtalker".)
  3. ffmpeg (subprocess)                   - transcode to the preview/export
     resolutions our API serves to the frontend

OPENMONTAGE_REPO_PATH must point to a local clone of the OpenMontage repo
with `make setup` (and, for this pipeline, `make install-gpu` / SadTalker)
already run - see README.md "GPU worker setup".
"""

import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from app.config import get_settings
from app.pipeline.base import PipelineContext

settings = get_settings()

# SadTalker ships this as one of its own example fixtures
# (examples/source_image/full3.png) specifically for testing the pipeline -
# it's a synthetic/AI-generated portrait, not a real person, so it carries no
# likeness/consent concerns. Used only when a job doesn't supply avatar_ref.
DEFAULT_TEST_AVATAR = "examples/source_image/full3.png"  # relative to SADTALKER_PATH


def _openmontage_tools():
    """Import OpenMontage's tool classes on first use, once OPENMONTAGE_REPO_PATH
    is on sys.path. Deferred so this module can be imported (e.g. for tests)
    without the OpenMontage repo present."""
    repo_path = settings.openmontage_repo_path
    if not repo_path:
        raise RuntimeError(
            "OPENMONTAGE_REPO_PATH is not set. Point it at a local clone of "
            "https://github.com/calesthio/OpenMontage with `make setup` run."
        )
    if repo_path not in sys.path:
        sys.path.insert(0, repo_path)

    from tools.audio.piper_tts import PiperTTS
    from tools.avatar.talking_head import TalkingHead

    return PiperTTS(), TalkingHead()


class OpenMontagePipeline:
    def __init__(self):
        self._workdir = Path(tempfile.mkdtemp(prefix="dolos-job-"))

    def synthesize_voice(self, ctx: PipelineContext) -> None:
        piper, _ = _openmontage_tools()
        audio_path = self._workdir / "narration.wav"

        result = piper.execute({
            "text": ctx.script,
            "output_path": str(audio_path),
        })
        if not result.success:
            raise RuntimeError(f"TTS stage failed: {result.error}")

        ctx.audio_path = result.artifacts[0]

    def lipsync(self, ctx: PipelineContext) -> None:
        # SadTalker performs lip-sync and face animation in a single model
        # pass (see module docstring), so this stage just validates inputs
        # and the real work happens in animate().
        if not ctx.audio_path:
            raise RuntimeError("lipsync stage requires synthesize_voice to run first")

    def _resolve_avatar_image(self, avatar_ref: str) -> str:
        if not avatar_ref.startswith(("http://", "https://")):
            return avatar_ref

        suffix = Path(avatar_ref.split("?")[0]).suffix or ".png"
        local_path = self._workdir / f"avatar{suffix}"
        urllib.request.urlretrieve(avatar_ref, local_path)
        return str(local_path)

    def animate(self, ctx: PipelineContext) -> None:
        _, talking_head = _openmontage_tools()
        if ctx.avatar_ref:
            avatar_ref = self._resolve_avatar_image(ctx.avatar_ref)
        else:
            sadtalker_path = os.environ.get("SADTALKER_PATH", "")
            if not sadtalker_path:
                raise RuntimeError(
                    "No avatar_ref on the job and SADTALKER_PATH is not set, so "
                    "the default test avatar can't be located either."
                )
            avatar_ref = str(Path(sadtalker_path) / DEFAULT_TEST_AVATAR)
        output_path = self._workdir / "talking_head.mp4"

        result = talking_head.execute({
            "image_path": avatar_ref,
            "audio_path": ctx.audio_path,
            "output_path": str(output_path),
            "model": "sadtalker",
        })
        if not result.success:
            raise RuntimeError(f"animate stage failed: {result.error}")

        ctx.animated_frames_dir = result.artifacts[0]  # actually the rendered mp4 path

    def composite_preview(self, ctx: PipelineContext) -> str:
        return self._transcode(ctx, height=480)

    def composite_full_res(self, ctx: PipelineContext) -> str:
        return self._transcode(ctx, height=1080)

    def _transcode(self, ctx: PipelineContext, height: int) -> str:
        out_path = self._workdir / f"final_{height}p.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", ctx.animated_frames_dir,
                "-vf", f"scale=-2:{height}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac",
                str(out_path),
            ],
            check=True,
            capture_output=True,
        )
        return str(out_path)
