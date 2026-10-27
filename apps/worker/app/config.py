from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://dolos:dolos@localhost:5432/dolos"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "dolos-media"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_region: str = "us-east-1"

    worker_stub_mode: bool = True

    # Which real (non-stub) pipeline to run when WORKER_STUB_MODE=false:
    #   "studio"      -> StudioPipeline: XTTS voice + Hallo2 talking head +
    #                    RVM matting composited over a lively studio background
    #                    (app/pipeline/studio.py). This is the default.
    #   "openmontage" -> legacy OpenMontagePipeline: Piper voice + SadTalker on
    #                    a frozen background (app/pipeline/openmontage.py).
    real_pipeline: str = "studio"

    video_gen_local_enabled: bool = True
    video_gen_local_model: str = "wan2.1-14b"

    # --- Voice / TTS (StudioPipeline) ---
    # "xtts" (Coqui XTTS-v2, natural + voice cloning) or "piper" (fast, robotic).
    tts_engine: str = "xtts"
    xtts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    xtts_language: str = "en"
    # Reference wav for voice cloning. When empty, XTTS uses xtts_speaker below.
    xtts_speaker_wav: str = ""
    # One of XTTS-v2's built-in studio speakers, used when no clone ref is given.
    xtts_speaker: str = "Ana Florence"

    # --- Talking head (StudioPipeline) ---
    # "hallo2" (livelier, higher-res, audio-driven) or "sadtalker" (legacy).
    talking_head_model: str = "hallo2"
    # Local clone of https://github.com/fudan-generative-vision/hallo2 with its
    # models downloaded. Required when talking_head_model="hallo2".
    hallo_repo_path: str = ""
    # Local clone of https://github.com/OpenTalker/SadTalker (talking_head_model
    # ="sadtalker", or the legacy OpenMontage pipeline). Also read from env.
    sadtalker_path: str = ""

    # --- Background matting + studio composite (StudioPipeline) ---
    enable_studio_composite: bool = True
    # Looping background clip (mp4) the matted subject is composited over -
    # soft studio bokeh, LED panels, plants, etc. Empty disables compositing
    # and the talking head is transcoded on its native background instead.
    studio_bg_path: str = ""
    # Subtle slow-zoom "life" applied to the background during compositing.
    bg_motion: bool = True
    # Robust Video Matting: clone of https://github.com/PeterL1n/RobustVideoMatting.
    rvm_repo_path: str = ""
    rvm_variant: str = "mobilenetv3"  # or "resnet50"
    rvm_weights: str = ""  # path to rvm_mobilenetv3.pth / rvm_resnet50.pth

    # Path to a local clone of https://github.com/calesthio/OpenMontage with
    # `make setup` (and SadTalker, for the talking-head pipeline) installed.
    # Required whenever the OpenMontage (Piper/SadTalker) path is used.
    openmontage_repo_path: str = ""

    openmontage_remote_endpoint: str = ""
    openmontage_remote_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
