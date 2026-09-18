"""SigV4 query signing that yields byte-identical URLs within a time bucket.

A stock presigned URL embeds the wall-clock second in ``X-Amz-Date``, so the
same S3 object produces a different URL on every request. Gallery clients then
re-download every thumbnail on each page load because the browser HTTP cache is
keyed by URL.

This module registers an additional SigV4 query signer that floors
``X-Amz-Date`` to a configurable bucket (one hour by default). Every request
inside a bucket therefore signs the same canonical request and yields the same
URL, which the browser can serve from disk cache. ``X-Amz-Expires`` is set to
two bucket widths so a URL minted at the end of a bucket is still valid for a
full bucket afterwards.

Only a new key is added to ``botocore.auth.AUTH_TYPE_MAPS``; stock signing
behaviour is untouched. The ``choose-signer`` hook is registered on our own
signing client only, and only for presign (``-query``) signatures.
"""

from __future__ import annotations

import time
from typing import Any

from botocore.auth import AUTH_TYPE_MAPS, SIGV4_TIMESTAMP, S3SigV4QueryAuth
from botocore.client import BaseClient

from app.core.logging import get_logger

logger = get_logger()

CACHEABLE_SIGNATURE_VERSION = "spotme-cacheable-v4-query"
_PRESIGN_SUFFIX = "-query"
_DEFAULT_BUCKET_SECONDS = 3600


# botocore ships no type information, so its signer base class is `Any`.
class CacheableSigV4QueryAuth(S3SigV4QueryAuth):  # type: ignore[misc]
    """SigV4 query signer whose signing timestamp is quantised to a bucket.

    ``botocore`` instantiates signers itself with a fixed keyword set, so the
    bucket width is a class attribute rather than a constructor argument. It is
    set once by :func:`register_cacheable_signer`.
    """

    bucket_seconds: int = _DEFAULT_BUCKET_SECONDS

    def _modify_request_before_signing(self, request: Any) -> None:
        """Replace the clock-derived timestamp with the bucket start.

        ``SigV4Auth.add_auth`` writes the current time into
        ``request.context["timestamp"]`` and every later stage (``X-Amz-Date``,
        the credential scope, and the string to sign) reads it back from there.
        Overwriting it here makes the whole signature deterministic.

        Args:
            request: The ``AWSRequest`` being signed, mutated in place.
        """
        request.context["timestamp"] = self._bucket_timestamp()
        super()._modify_request_before_signing(request)

    @classmethod
    def _bucket_timestamp(cls) -> str:
        """Return the current bucket's start time in SigV4 format."""
        bucket = max(cls.bucket_seconds, 1)
        bucket_start = (int(time.time()) // bucket) * bucket
        return time.strftime(SIGV4_TIMESTAMP, time.gmtime(bucket_start))


def bucket_expiry_seconds(bucket_seconds: int) -> int:
    """Return the ``X-Amz-Expires`` value that keeps a bucketed URL usable.

    The signature is dated at the start of the bucket, so a URL handed out in
    the bucket's final second must still cover a full bucket of viewing time.

    Args:
        bucket_seconds: Width of the caching bucket.

    Returns:
        Lifetime in seconds, measured from the bucket start.
    """
    return max(bucket_seconds, 1) * 2


def register_cacheable_signer(client: BaseClient, bucket_seconds: int) -> None:
    """Make ``client`` sign presigned URLs with the bucketed timestamp.

    Args:
        client: Synchronous botocore client used exclusively for signing.
        bucket_seconds: Width of the caching bucket, in seconds.
    """
    CacheableSigV4QueryAuth.bucket_seconds = max(bucket_seconds, 1)
    AUTH_TYPE_MAPS.setdefault(CACHEABLE_SIGNATURE_VERSION, CacheableSigV4QueryAuth)
    client.meta.events.register("choose-signer.s3", _choose_cacheable_signer)


def _choose_cacheable_signer(signature_version: str, **_: Any) -> str | None:
    """Select the bucketed signer for presigned URLs only.

    Args:
        signature_version: Version botocore resolved for this request. Presign
            flows arrive with a ``-query`` suffix already applied.

    Returns:
        The cacheable signature version for presign flows, otherwise ``None``
        so botocore keeps its own choice.
    """
    if not signature_version.endswith(_PRESIGN_SUFFIX):
        return None
    return CACHEABLE_SIGNATURE_VERSION
