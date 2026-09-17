"""Shared loader options for photo listing queries.

``Photo`` declares ``lazy="selectin"`` on all five of its relationships, which
is convenient for detail views but ruinous for galleries: selecting one page of
photos fires five extra queries and pulls in every face embedding, favourite,
and analytics row for the page. Gallery responses read scalar columns only, so
the relationships are suppressed explicitly.
"""

from __future__ import annotations

from sqlalchemy.orm import noload
from sqlalchemy.orm.interfaces import LoaderOption

from app.models.photo import Photo


def gallery_load_options() -> tuple[LoaderOption, ...]:
    """Return loader options that suppress every ``Photo`` relationship.

    Returns:
        Options to pass to ``select(Photo).options(...)``.
    """
    return (
        noload(Photo.event),
        noload(Photo.folder),
        noload(Photo.face_embeddings),
        noload(Photo.favorites),
        noload(Photo.analytics_events),
    )
