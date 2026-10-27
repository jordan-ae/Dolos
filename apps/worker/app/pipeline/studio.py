"""Studio pipeline: a natural voice on a lively, professional-looking set.

This is the default real (non-stub) pipeline. It upgrades the three weak
spots of the legacy OpenMontage/SadTalker path (see openmontage.py):

  1. Voice  - Coqui **XTTS-v2** instead of Piper. XTTS is a natural,
     expressive neural TTS with zero-shot voice cloning (give it a ~6s
     reference wav and it speaks your script in that voice). Piper is fast
     but unmistakably robotic; XTTS is the single biggest quality win here.

  2. Talking head - **Hallo2** instead of SadTalker. Hallo2 is audio-driven
     (image + audio -> lip-synced video, same interface as SadTalker) but
     produces livelier head motion, blinking and expression at higher
     resolution. `talking_head_model="sadtalker"` keeps the old model.

     NOTE ON LivePortrait: it is driven by a *driving video*, not audio, so
     it can't lip-sync to TTS on its own - wrong tool for a script->voice
     pipeline. It belongs as an optional expression-enhancement pass on top
     of an audio-driven result, not as the talking-head model. Hence Hallo2.

  3. Background - the talking-head models only animate the *face* on a still
     image, so their background is a frozen photo. We fix that by matting the
     subject out with **Robust Video Matting (RVM)** and compositing them over
     a looping studio background clip (soft bokeh/LED panels/plants), with a
     subtle slow zoom for a bit of "life". This is the compositing stage.

Everything is config-driven (see app/config.py) so models, the background
clip and speaker can be swapped on the GPU box without editing this file.

Heavy deps (torch, TTS, RVM, Hallo2) are imported lazily inside each stage so
this module still imports in the lightweight stub/CI image where they're
absent - matching openmontage.py's deferred-import pattern.
"""

import glob
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from app.config import get_settings
from app.pipeline.base import PipelineContext

settings = get_settings()


class StudioPipeline:
    def __init__(self):
        self._workdir = Path(tempfile.mkdtemp(prefix="dolos-job-"))

    # ------------------------------------------------------------------ #
    # 1. Voice
    # ------------------------------------------------------------------ #
    def synthesize_voice(self, ctx: PipelineContext) -> None:
        if settings.tts_engine == "piper":
            return self._synthesize_voice_piper(ctx)

        # Coqui XTTS-v2. `TTS.api.TTS` is a stable pip package (`pip install
        # TTS`); loading the model onto CUDA and calling tts_to_file is the
        # whole integration. Long scripts are sentence-split internally.
        from TTS.api import TTS  # noqa: PLC0415 (deferred: heavy import)

        audio_path = self._workdir / "narration.wav"
        tts = TTS(settings.xtts_model).to(self._device())

        ref_wav = ctx.voice_ref_wav or settings.xtts_speaker_wav or None
        kwargs = {
            "text": ctx.script,
            "language": settings.xtts_language,
            "file_path": str(audio_path),
        }
        if ref_wav:
            # Zero-shot clone from a reference sample.
            kwargs["speaker_wav"] = ref_wav
        else:
            # Fall back to one of XTTS's built-in studio speakers.
            kwargs["speaker"] = settings.xtts_speaker

        tts.tts_to_file(**kwargs)
        if not audio_path.exists():
            raise RuntimeError("TTS stage failed: XTTS produced no audio file")
        ctx.audio_path = str(audio_path)

    def _synthesize_voice_piper(self, ctx: PipelineContext) -> None:
        # Legacy fast/robotic path, reusing OpenMontage's Piper tool.
        from app.pipeline.openmontage import _openmontage_tools  # noqa: PLC0415

        piper, _ = _openmontage_tools()
        audio_path = self._workdir / "narration.wav"
        result = piper.execute({"text": ctx.script, "output_path": str(audio_path)})
        if not result.success:
            raise RuntimeError(f"TTS stage failed: {result.error}")
        ctx.audio_path = result.artifacts[0]

    # ------------------------------------------------------------------ #
    # 2. Lip-sync (both models fold lip-sync into the animate pass)
    # ------------------------------------------------------------------ #
    def lipsync(self, ctx: PipelineContext) -> None:
        if not ctx.audio_path:
            raise RuntimeError("lipsync stage requires synthesize_voice to run first")

    # ------------------------------------------------------------------ #
    # 3. Talking head
    # ------------------------------------------------------------------ #
    def animate(self, ctx: PipelineContext) -> None:
        avatar_image = self._resolve_avatar_image(ctx)
        if settings.talking_head_model == "sadtalker":
            ctx.animated_frames_dir = self._animate_sadtalker(ctx, avatar_image)
        else:
            ctx.animated_frames_dir = self._animate_hallo2(ctx, avatar_image)

    def _animate_hallo2(self, ctx: PipelineContext, avatar_image: str) -> str:
        """Run Hallo2 inference as a subprocess (it's a repo of inference
        scripts, not a pip API - so we shell out, like the SadTalker path).

        Verify these flags against your installed Hallo2 version: the repo's
        `scripts/inference_long.py --config configs/inference/long.yaml
        --source_image ... --driving_audio ...` is the current shape.
        """
        repo = settings.hallo_repo_path
        if not repo:
            raise RuntimeError(
                "HALLO_REPO_PATH is not set. Clone "
                "https://github.com/fudan-generative-vision/hallo2, download its "
                "models, and point HALLO_REPO_PATH at the clone."
            )
        out_dir = self._workdir / "hallo_out"
        out_dir.mkdir(exist_ok=True)
        config = os.path.join(repo, "configs", "inference", "long.yaml")

        subprocess.run(
            [
                sys.executable, os.path.join(repo, "scripts", "inference_long.py"),
                "--config", config,
                "--source_image", avatar_image,
                "--driving_audio", ctx.audio_path,
                "--output", str(out_dir),
            ],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        return self._find_output_video(out_dir, stage="hallo2")

    def _animate_sadtalker(self, ctx: PipelineContext, avatar_image: str) -> str:
        # Legacy path via OpenMontage's TalkingHead (SadTalker) tool.
        from app.pipeline.openmontage import _openmontage_tools  # noqa: PLC0415

        _, talking_head = _openmontage_tools()
        output_path = self._workdir / "talking_head.mp4"
        result = talking_head.execute({
            "image_path": avatar_image,
            "audio_path": ctx.audio_path,
            "output_path": str(output_path),
            "model": "sadtalker",
        })
        if not result.success:
            raise RuntimeError(f"animate stage failed: {result.error}")
        return result.artifacts[0]

    # ------------------------------------------------------------------ #
    # 4. Composite (matte + studio background) then transcode
    # ------------------------------------------------------------------ #
    def composite_preview(self, ctx: PipelineContext) -> str:
        return self._transcode(self._composited_master(ctx), height=480)

    def composite_full_res(self, ctx: PipelineContext) -> str:
        return self._transcode(self._composited_master(ctx), height=1080)

    def _composited_master(self, ctx: PipelineContext) -> str:
        """The matted+composited 1080p master, computed once and cached on ctx
        (matting is expensive; preview and export both downscale from it)."""
        if ctx.composited_master_path:
            return ctx.composited_master_path

        talking_head = ctx.animated_frames_dir
        if not (settings.enable_studio_composite and settings.studio_bg_path):
            # Compositing disabled or no background clip: use the talking head
            # on its native (frozen) background.
            ctx.composited_master_path = talking_head
            return talking_head

        fgr, pha = self._matte(talking_head)
        master = self._workdir / "composited_master.mp4"
        self._composite_over_background(talking_head, fgr, pha, master)
        ctx.composited_master_path = str(master)
        return ctx.composited_master_path

    def _matte(self, talking_head: str) -> tuple[str, str]:
        """Robust Video Matting -> (foreground rgb mp4, alpha mp4)."""
        repo = settings.rvm_repo_path
        if not repo:
            raise RuntimeError(
                "RVM_REPO_PATH is not set. Clone "
                "https://github.com/PeterL1n/RobustVideoMatting and download its "
                "weights (rvm_mobilenetv3.pth), then set RVM_REPO_PATH/RVM_WEIGHTS."
            )
        if repo not in sys.path:
            sys.path.insert(0, repo)

        import torch  # noqa: PLC0415
        from model import MattingNetwork  # noqa: PLC0415 (from the RVM repo)
        from inference import convert_video  # noqa: PLC0415

        model = MattingNetwork(settings.rvm_variant).eval().to(self._device())
        weights = settings.rvm_weights or os.path.join(
            repo, f"rvm_{settings.rvm_variant}.pth"
        )
        model.load_state_dict(torch.load(weights, map_location=self._device()))

        fgr = self._workdir / "fgr.mp4"
        pha = self._workdir / "pha.mp4"
        convert_video(
            model,
            input_source=talking_head,
            output_type="video",
            output_foreground=str(fgr),
            output_alpha=str(pha),
            seq_chunk=12,
        )
        return str(fgr), str(pha)

    def _composite_over_background(
        self, talking_head: str, fgr: str, pha: str, out_path: Path
    ) -> None:
        """Composite the matted subject over the looping studio background at
        1080p, keeping the talking head's audio, with an optional subtle slow
        zoom on the background for a bit of life."""
        canvas = "1920:1080"
        bg_chain = (
            f"[0:v]scale={canvas}:force_original_aspect_ratio=increase,"
            f"crop={canvas},setsar=1"
        )
        if settings.bg_motion:
            # Slow, endless-feeling zoom drift. Gated so it can be turned off
            # if a given background clip already has enough motion.
            bg_chain += (
                ",zoompan=z='min(zoom+0.0004,1.08)':d=1"
                ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":s=1920x1080:fps=25"
            )
        filtergraph = (
            f"[1:v][2:v]alphamerge,scale=-1:1080[subj];"
            f"{bg_chain}[bg];"
            f"[bg][subj]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p[v]"
        )
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", settings.studio_bg_path,  # 0: background
                "-i", fgr,                                            # 1: foreground rgb
                "-i", pha,                                            # 2: alpha
                "-i", talking_head,                                   # 3: audio source
                "-filter_complex", filtergraph,
                "-map", "[v]", "-map", "3:a?",
                "-r", "25",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "aac",
                "-shortest",
                str(out_path),
            ],
            check=True,
            capture_output=True,
        )

    def _transcode(self, source: str, height: int) -> str:
        out_path = self._workdir / f"final_{height}p.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", source,
                "-vf", f"scale=-2:{height}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac",
                str(out_path),
            ],
            check=True,
            capture_output=True,
        )
        return str(out_path)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _device(self) -> str:
        import torch  # noqa: PLC0415

        return "cuda" if torch.cuda.is_available() else "cpu"

    def _resolve_avatar_image(self, ctx: PipelineContext) -> str:
        avatar_ref = ctx.avatar_ref
        if not avatar_ref:
            # SadTalker ships a synthetic test portrait (no likeness/consent
            # concerns); reuse it when a job supplies no avatar.
            sadtalker_path = settings.sadtalker_path or os.environ.get("SADTALKER_PATH", "")
            if not sadtalker_path:
                raise RuntimeError(
                    "No avatar_ref on the job and SADTALKER_PATH is not set, so "
                    "the default test avatar can't be located either."
                )
            return str(Path(sadtalker_path) / "examples/source_image/full3.png")

        if not avatar_ref.startswith(("http://", "https://")):
            return avatar_ref
        suffix = Path(avatar_ref.split("?")[0]).suffix or ".png"
        local_path = self._workdir / f"avatar{suffix}"
        urllib.request.urlretrieve(avatar_ref, local_path)
        return str(local_path)

    def _find_output_video(self, out_dir: Path, stage: str) -> str:
        vids = sorted(glob.glob(str(out_dir / "**" / "*.mp4"), recursive=True))
        if not vids:
            raise RuntimeError(f"{stage} stage produced no .mp4 in {out_dir}")
        # Newest file is the render for this run.
        return max(vids, key=os.path.getmtime)
