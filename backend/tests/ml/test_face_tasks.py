"""Celery face-queue routing tests (ML-009)."""

from __future__ import annotations

from app.tasks.celery_app import APP_QUEUES, ML_QUEUES, celery_app
from app.tasks.face_tasks import process_event_photos, run_event_clustering


def test_face_tasks_route_to_face_processing_queue() -> None:
    """Face tasks must never land on the CPU photo_processing queue."""
    routes = celery_app.conf.task_routes
    assert routes["app.tasks.face_tasks.*"]["queue"] == "face_processing"
    assert process_event_photos._get_exec_options()["queue"] == "face_processing"
    assert run_event_clustering._get_exec_options()["queue"] == "face_processing"


def test_app_workers_do_not_register_face_processing_queue() -> None:
    """App EC2 worker queues exclude face_processing."""
    assert "face_processing" not in APP_QUEUES
    assert ML_QUEUES == ["face_processing"]
    photo_route = celery_app.conf.task_routes["app.tasks.photo_tasks.*"]["queue"]
    assert photo_route == "photo_processing"
    assert photo_route != "face_processing"
