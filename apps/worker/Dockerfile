FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY apps/worker/requirements.txt apps/worker/requirements.txt
RUN pip install --no-cache-dir -r apps/worker/requirements.txt

COPY apps/worker/app apps/worker/app

WORKDIR /app/apps/worker
ENV PYTHONPATH=/app/apps/worker

CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--loglevel=INFO"]
