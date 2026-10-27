from app.config import get_settings
from app.pipeline.base import Pipeline


def get_pipeline() -> Pipeline:
    settings = get_settings()
    if settings.worker_stub_mode:
        from app.pipeline.stub import StubPipeline

        return StubPipeline()

    if settings.real_pipeline == "openmontage":
        from app.pipeline.openmontage import OpenMontagePipeline

        return OpenMontagePipeline()

    from app.pipeline.studio import StudioPipeline

    return StudioPipeline()
