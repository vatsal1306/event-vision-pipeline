"""SQLAlchemy ORM models."""

from __future__ import annotations

from app.models.analytics_event import AnalyticsEvent
from app.models.base import Base
from app.models.couple_session import CoupleSession
from app.models.enums import AnalyticsAction, EventStatus, EventType, ProcessingStatus
from app.models.event import Event
from app.models.face_cluster import FaceCluster
from app.models.face_embedding import FaceEmbedding
from app.models.favorite import Favorite
from app.models.folder import Folder
from app.models.guest_session import GuestSession
from app.models.photo import Photo
from app.models.photographer import Photographer

__all__ = [
    "AnalyticsAction",
    "AnalyticsEvent",
    "Base",
    "CoupleSession",
    "Event",
    "EventStatus",
    "EventType",
    "FaceCluster",
    "FaceEmbedding",
    "Favorite",
    "Folder",
    "GuestSession",
    "Photo",
    "Photographer",
    "ProcessingStatus",
]
