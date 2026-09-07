"""Stub FaceService for Phase 1."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession


class MatchResult:
    """Result of a selfie match operation."""

    def __init__(
        self,
        status: str,
        clusters: list[uuid.UUID],
        photo_ids: list[uuid.UUID],
        quality_issue: str | None = None,
    ) -> None:
        self.status = status
        self.clusters = clusters
        self.photo_ids = photo_ids
        self.quality_issue = quality_issue


class FaceService:
    """Stub implementation of face matching for guest selfies."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def match_selfie(self, selfie_image_bytes: bytes, event_id: uuid.UUID) -> MatchResult:
        """Simulate matching a guest selfie.

        Since ML pipeline is not yet available on the app server,
        this stub just returns 'no_match' for now.
        """
        # In a real implementation, this would detect a face, extract embeddings,
        # and compare against clusters for the given event_id.
        return MatchResult(status="no_match", clusters=[], photo_ids=[])
