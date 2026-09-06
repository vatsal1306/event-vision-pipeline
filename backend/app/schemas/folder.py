"""Hierarchical folder schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FolderNode(BaseModel):
    """Nested folder node returned in the event folder tree."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    parent_id: UUID | None
    name: str
    sort_order: int
    photo_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None
    children: list[FolderNode] = Field(default_factory=list)


class FolderTreeResponse(BaseModel):
    """Root folder tree for an event."""

    folders: list[FolderNode]


class CreateFolderRequest(BaseModel):
    """Create a folder under an optional parent."""

    name: str = Field(min_length=1, max_length=255)
    parent_id: UUID | None = None


class UpdateFolderRequest(BaseModel):
    """Rename, reorder, or reparent a folder."""

    name: str | None = Field(None, min_length=1, max_length=255)
    parent_id: UUID | None = None
    sort_order: int | None = None


FolderNode.model_rebuild()
