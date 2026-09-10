"""Schemas for tusd upload webhooks."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _empty_if_none(value: Any) -> Any:
    """tusd sends JSON null for unset ID/Storage on pre-create."""
    return "" if value is None else value


def _empty_dict_if_none(value: Any) -> Any:
    """tusd sends Storage: null before the object exists."""
    return {} if value is None else value


def _zero_if_none(value: Any) -> Any:
    """tusd may send Size/Offset as null when length is deferred."""
    return 0 if value is None else value


class TusUploadInfo(BaseModel):
    """Upload information provided by tusd."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default="", alias="ID")
    size: int = Field(default=0, alias="Size")
    offset: int = Field(default=0, alias="Offset")
    metadata: dict[str, str] = Field(default_factory=dict, alias="MetaData")
    storage: dict[str, Any] = Field(default_factory=dict, alias="Storage")

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, value: Any) -> Any:
        return _empty_if_none(value)

    @field_validator("size", "offset", mode="before")
    @classmethod
    def _coerce_int(cls, value: Any) -> Any:
        return _zero_if_none(value)

    @field_validator("storage", mode="before")
    @classmethod
    def _coerce_storage(cls, value: Any) -> Any:
        return _empty_dict_if_none(value)


class TusEventInfo(BaseModel):
    """Event wrapper in the tusd payload."""

    model_config = ConfigDict(populate_by_name=True)

    upload: TusUploadInfo = Field(alias="Upload")


class TusHookPayload(BaseModel):
    """Payload sent by tusd on webhooks."""

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(alias="Type")
    event: TusEventInfo = Field(alias="Event")
