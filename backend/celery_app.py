from __future__ import annotations
import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Treat worker SIGTERM like SIGQUIT so container/service stops do not wait
# for long-running simulations to finish in the background.
os.environ.setdefault("REMAP_SIGTERM", "SIGQUIT")

celery_app = Celery(
    "noosphere",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_acks_on_failure_or_timeout=True,
    task_reject_on_worker_lost=False,
    task_track_started=True,
)
