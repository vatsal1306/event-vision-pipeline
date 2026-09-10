"""Celery application for background workers."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "spotme",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.notification_tasks",
        "app.tasks.archival_tasks",
        "app.tasks.photo_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_default_queue="photo_processing",
    task_routes={
        "app.tasks.photo_tasks.*": {"queue": "photo_processing"},
        "app.tasks.notification_tasks.*": {"queue": "photo_processing"},
        "app.tasks.archival_tasks.*": {"queue": "photo_processing"},
    },
    beat_schedule={
        "check-archival": {
            "task": "app.tasks.archival_tasks.check_events_for_archival",
            "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM IST
        },
        "send-archival-warnings": {
            "task": "app.tasks.archival_tasks.send_archival_warnings",
            "schedule": crontab(hour=10, minute=0),  # Daily at 10 AM IST
        },
    },
)
