# Dolos

Prompt-to-video platform: type a script, watch generation progress live, preview the result, export full-res. Generation runs on [OpenMontage](https://github.com/calesthio/OpenMontage) so there are no per-video API credits when using local/open models.

## Monorepo layout

```
apps/web       Next.js + TypeScript + Tailwind + shadcn/ui frontend
apps/api       FastAPI backend (job endpoints, WebSocket progress relay)
apps/worker    Celery worker that invokes the OpenMontage pipeline
packages/shared  Shared TS types (job status enum, API schemas)
```

## Architecture

```
Next.js (apps/web)
   |  REST + WebSocket
FastAPI (apps/api)
   |  enqueue                 |  Redis pub/sub (progress)
Celery + Redis  ---------------------------------------
   |  pull job
Celery worker (apps/worker) --> OpenMontage tools --> MinIO/S3
```

Job stages: `queued -> tts -> lipsync -> animating -> compositing -> done` (or `failed`). The worker publishes a status message to Redis after every stage; the API's `/ws/jobs/{id}` endpoint relays it to the frontend over a WebSocket. A low-res preview is rendered as soon as compositing finishes; hitting "Export" triggers a separate full-res render.

## Quick start (stubbed pipeline)

The worker ships with a stub pipeline (`WORKER_STUB_MODE=true`, the default) that fakes each generation stage with a short sleep and renders a real (but trivial) test clip via ffmpeg. Use this to validate the whole flow - frontend, API, WebSocket, storage - before touching the GPU pipeline.

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- API: http://localhost:8000 (docs at /docs)
- MinIO console: http://localhost:9001 (login from `.env`)

Submit a script on the homepage, watch the stage progress on the job page, and confirm the preview video plays once the job reaches `done`.

## Studio pipeline (default real pipeline)

`apps/worker/app/pipeline/studio.py` (`REAL_PIPELINE=studio`, the default when `WORKER_STUB_MODE=false`) is the recommended pipeline. It targets the three things that make cheap talking-head video look cheap:

1. **Natural voice** - Coqui **XTTS-v2** instead of Piper. XTTS is expressive and supports zero-shot voice cloning (set `XTTS_SPEAKER_WAV` to a ~6s reference wav; otherwise it uses the built-in `XTTS_SPEAKER`). Set `TTS_ENGINE=piper` to fall back to the old robotic voice.
2. **Livelier talking head** - **Hallo2** instead of SadTalker (`TALKING_HEAD_MODEL=hallo2`, or `sadtalker` for the legacy model). Hallo2 is audio-driven (image + audio -> video, same as SadTalker) with more natural head motion, blinking and expression at higher resolution.
3. **Lively background** - the talking-head models only animate the *face* on a still photo, so their background is frozen. The compositing stage mattes the subject out with **Robust Video Matting (RVM)** and composites them over a looping studio background clip (`STUDIO_BG_PATH`), with an optional subtle slow zoom (`BG_MOTION=true`) for a bit of life. Leave `STUDIO_BG_PATH` empty (or `ENABLE_STUDIO_COMPOSITE=false`) to keep the talking head on its native background.

> Why not LivePortrait? It's driven by a *driving video*, not audio, so it can't lip-sync to TTS on its own - it's an optional expression-enhancement pass on top of an audio-driven result, not a talking-head model for a script->voice pipeline.

### Studio GPU setup (RunPod / any CUDA box, ~24GB)

```bash
# 1. Voice
pip install TTS   # Coqui XTTS-v2 downloads on first use

# 2. Talking head
git clone https://github.com/fudan-generative-vision/hallo2 /opt/hallo2
# ...download its models per the repo README, then:
#   HALLO_REPO_PATH=/opt/hallo2

# 3. Matting
git clone https://github.com/PeterL1n/RobustVideoMatting /opt/RobustVideoMatting
# download rvm_mobilenetv3.pth into that dir, then:
#   RVM_REPO_PATH=/opt/RobustVideoMatting
#   RVM_WEIGHTS=/opt/RobustVideoMatting/rvm_mobilenetv3.pth

# 4. A looping studio background clip (soft bokeh / LED panels / plants) -
#    a free Pexels/Pixabay loop works to start:
#   STUDIO_BG_PATH=/opt/assets/studio_loop.mp4
```

Then set `WORKER_STUB_MODE=false` and the Studio vars in `.env` (see `.env.example`) and run the worker on that box. `ffmpeg` must be on `PATH`. The subprocess flags for Hallo2 in `studio.py` (`scripts/inference_long.py`) should be verified against your installed Hallo2 version.

## Real OpenMontage integration (legacy: `REAL_PIPELINE=openmontage`)

OpenMontage is **agent-first**: its normal usage is an AI coding assistant reading `pipeline_defs/` and driving tools interactively with human approval at each stage - there's no headless "run pipeline" CLI. `apps/worker/app/pipeline/openmontage.py` bypasses that orchestration layer and calls three of its underlying tool classes directly (every OpenMontage tool exposes a uniform `execute(inputs) -> ToolResult`, and the loader explicitly supports being imported this way):

1. `tools/audio/piper_tts.py` - free, fully local TTS
2. `tools/avatar/talking_head.py` (model=`sadtalker`) - photo + audio -> lip-synced, animated talking-head video in one pass
3. `ffmpeg` - transcode to preview (480p) / export (1080p) resolutions

> Upstream note: `talking_head.py`'s `model="musetalk"` branch is currently a stub that always fails - use `sadtalker`, which is what `openmontage.py` defaults to.

### GPU requirements

- **16-24GB VRAM minimum** for SadTalker + Piper on a single box (24GB recommended if you also run other GPU work concurrently).
- CPU-only inference works for Piper TTS but SadTalker inference will be very slow; a CUDA GPU is effectively required for usable turnaround.

### GPU worker setup

1. Clone and set up OpenMontage on your GPU box (local machine, or a rented box on RunPod/Lambda/Vast.ai):
   ```bash
   git clone https://github.com/calesthio/OpenMontage.git /opt/OpenMontage
   cd /opt/OpenMontage && make setup && make install-gpu
   ```
2. Install SadTalker per `tools/avatar/talking_head.py`'s `install_instructions` (clone [OpenTalker/SadTalker](https://github.com/OpenTalker/SadTalker), set `SADTALKER_PATH`).
3. In `.env`, set:
   ```bash
   WORKER_STUB_MODE=false
   OPENMONTAGE_REPO_PATH=/opt/OpenMontage
   SADTALKER_PATH=/opt/SadTalker
   ```
4. Run the worker on that box (either directly with `celery -A app.celery_app.celery_app worker`, pointed at the same `REDIS_URL`/`DATABASE_URL` as your API, or by uncommenting the `deploy.resources.reservations.devices` GPU block in `docker-compose.yml` if using `nvidia-container-toolkit`).

### Not running a GPU locally

Point the worker at a remote GPU host instead of a local device:

- Stand up OpenMontage + SadTalker on a rented GPU box (RunPod, Lambda, Vast.ai) and run the Celery worker there, connecting back to your shared Postgres/Redis/MinIO (or their managed equivalents).
- Alternatively, wrap the same three-tool call in a small HTTP service on the GPU box and set `OPENMONTAGE_REMOTE_ENDPOINT` / `OPENMONTAGE_REMOTE_API_KEY` in `.env`; `apps/worker/app/pipeline/openmontage.py` is the place to add an HTTP-backed pipeline implementation that POSTs to that endpoint instead of importing OpenMontage's tools in-process.

## Storage: MinIO -> S3

Dev uses MinIO (S3-compatible, free, run via `docker-compose.yml`). To use AWS S3 in production, only the `.env` values need to change - `apps/api/app/storage.py` and `apps/worker/app/storage.py` both use a plain `boto3` S3 client:

```bash
S3_ENDPOINT_URL=          # empty = use AWS's default endpoint for the region
S3_BUCKET=your-prod-bucket
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_REGION=us-east-1
```

## Development without Docker

```bash
# API
cd apps/api && pip install -r requirements.txt
uvicorn app.main:app --reload

# Worker
cd apps/worker && pip install -r requirements.txt
celery -A app.celery_app.celery_app worker --loglevel=INFO

# Web
cd apps/web && npm install && npm run dev
```

You'll still need Postgres, Redis, and MinIO running locally (e.g. `docker compose up postgres redis minio minio-init`).

## License

[MIT](LICENSE)
