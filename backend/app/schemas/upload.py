"""Schemas for tusd upload webhooks."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TusUploadInfo(BaseModel):
    """Upload information provided by tusd."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="ID")
    size: int = Field(alias="Size")
    offset: int = Field(alias="Offset")
    metadata: dict[str, str] = Field(default_factory=dict, alias="MetaData")
    storage: dict[str, Any] = Field(default_factory=dict, alias="Storage")


class TusEventInfo(BaseModel):
    """Event wrapper in the tusd payload."""

    model_config = ConfigDict(populate_by_name=True)

    upload: TusUploadInfo = Field(alias="Upload")


class TusHookPayload(BaseModel):
    """Payload sent by tusd on webhooks."""

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(alias="Type")
    event: TusEventInfo = Field(alias="Event")
