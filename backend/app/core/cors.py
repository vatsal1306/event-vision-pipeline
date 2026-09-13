"""CORS origin helpers for the FastAPI app."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

_LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1"})
_PRODUCTION_ENVIRONMENTS = frozenset({"production", "prod"})
# Next.js on the laptop (any port). Used when ENVIRONMENT is not production.
LOCAL_DEV_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"


def is_production_environment(environment: str) -> bool:
    """Return True when CORS must not add laptop localhost origins."""
    return environment.strip().lower() in _PRODUCTION_ENVIRONMENTS


def cors_origin_regex(environment: str) -> str | None:
    """Regex of extra origins allowed on the laptop (not in production).

    Args:
        environment: ``ENVIRONMENT`` setting.

    Returns:
        A fullmatch regex, or None when only ``FRONTEND_URL`` is allowed.
    """
    if is_production_environment(environment):
        return None
    return LOCAL_DEV_ORIGIN_REGEX


def cors_allow_origins(frontend_url: str) -> list[str]:
    """Return allowed browser origins for ``FRONTEND_URL``.

    Localhost and 127.0.0.1 are different origins to the browser. When the
    configured frontend is one of them, both are allowed so local register/login
    works with ``DEBUG=false``.

    Args:
        frontend_url: Configured frontend base URL (may include a trailing slash).

    Returns:
        Deduplicated origin strings with no path.
    """
    origin = frontend_url.strip().rstrip("/")
    if not origin:
        return []

    origins = [origin]
    parsed = urlparse(origin)
    host = parsed.hostname
    if host not in _LOCAL_HOSTNAMES:
        return origins

    alternate = "127.0.0.1" if host == "localhost" else "localhost"
    netloc = parsed.netloc.replace(host, alternate, 1)
    alternate_origin = urlunparse((parsed.scheme, netloc, "", "", "", ""))
    if alternate_origin and alternate_origin not in origins:
        origins.append(alternate_origin)
    return origins
