"""Photo listing schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PhotoListResponse(BaseModel):
    """Paginated photo list (empty until ingest exists)."""

    items: list[dict[str, object]] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 50
