"""Pydantic schemas for photographer profile and storage."""

from __future__ import annotations

from pydantic import BaseModel


class StorageInfo(BaseModel):
    """Storage usage breakdown for a photographer."""

    used: int
    limit: int
    active_bytes: int
    archived_bytes: int
    used_percentage: float
