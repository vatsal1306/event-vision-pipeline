"""URL slug helpers for events."""

from __future__ import annotations

import re
import secrets
import unicodedata

_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Turn a display name into a lowercase URL-safe slug fragment.

    Args:
        value: Human-readable event name.

    Returns:
        ASCII slug without leading/trailing hyphens.
    """
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = _NON_SLUG_RE.sub("-", normalized.lower()).strip("-")
    return slug or "event"


def unique_event_slug(name: str) -> str:
    """Build a unique-looking slug from a name plus a short random suffix."""
    base = slugify(name)[:80]
    suffix = secrets.token_hex(3)
    return f"{base}-{suffix}"
