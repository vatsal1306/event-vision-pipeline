"""CloudFront signed URLs with the same cache-bucketing property as S3.

`s3_presigner.py` floors the SigV4 signing timestamp to a bucket so the same
photo yields a byte-identical URL for the whole bucket window, letting the
browser's HTTP cache hit. A CloudFront signed URL's expiry (``date_less_than``
in its policy) plays the same role as SigV4's ``X-Amz-Date``: sign it fresh off
the wall clock and every request mints a different URL, defeating the browser
cache. This module floors that expiry the same way.

Uses ``botocore.signers.CloudFrontSigner`` with an RSA-SHA1 callback built from
the ``cryptography`` package, which is already in the dependency tree via
``python-jose[cryptography]`` (also pinned directly in ``pyproject.toml`` so a
future removal of ``python-jose`` cannot silently break this).
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from botocore.signers import CloudFrontSigner
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from app.config import Settings

_DEFAULT_BUCKET_SECONDS = 3600


def bucket_expires_at(bucket_seconds: int) -> int:
    """Return the epoch expiry for a CloudFront policy, floored to a bucket.

    Mirrors ``s3_presigner.bucket_expiry_seconds``: the expiry is pinned to the
    end of the *next* bucket boundary, so every request inside the current
    bucket signs an identical policy (same URL) and a URL minted near the end
    of a bucket still has a full bucket of remaining validity.

    Args:
        bucket_seconds: Width of the caching bucket, in seconds.

    Returns:
        Unix timestamp to use as the policy's ``date_less_than``.
    """
    bucket = max(bucket_seconds, 1)
    bucket_start = (int(time.time()) // bucket) * bucket
    return bucket_start + (bucket * 2)


class CloudFrontUrlSigner:
    """Signs CloudFront URLs for objects behind a private (OAC-locked) origin.

    Instantiate once per process (or per settings snapshot) and reuse — RSA key
    loading is not free, and signing itself is local CPU, no network I/O, so
    this is safe to call from sync or async code without blocking.
    """

    def __init__(self, settings: Settings) -> None:
        """Load the signing key and cache signing parameters.

        Args:
            settings: Application settings holding the CloudFront domain, key
                pair id, and PEM-encoded private key.
        """
        self.domain = settings.cloudfront_domain.rstrip("/")
        self.key_pair_id = settings.cloudfront_key_pair_id
        self.bucket_seconds = settings.gallery_url_cache_bucket_seconds
        self._private_key = self._load_private_key(settings.cloudfront_private_key)
        self._lock = threading.Lock()
        self._signer = CloudFrontSigner(self.key_pair_id, self._rsa_signer)

    @staticmethod
    def _load_private_key(pem: str) -> RSAPrivateKey:
        """Parse the configured PEM-encoded RSA private key.

        Args:
            pem: PEM text, e.g. loaded from ``CLOUDFRONT_PRIVATE_KEY``.

        Returns:
            A private key usable for RSA-SHA1 signing.
        """
        key = serialization.load_pem_private_key(pem.encode(), password=None)
        if not isinstance(key, RSAPrivateKey):
            raise ValueError("CLOUDFRONT_PRIVATE_KEY must be an RSA private key")
        return key

    def _rsa_signer(self, message: bytes) -> bytes:
        """Sign a CloudFront policy statement with RSA-SHA1 PKCS1v15.

        CloudFront's signed-URL scheme requires SHA1 specifically; this is a
        protocol requirement, not a cryptographic choice made here.

        Args:
            message: The canned or custom policy statement to sign.

        Returns:
            The raw signature bytes.
        """
        with self._lock:
            return self._private_key.sign(message, padding.PKCS1v15(), hashes.SHA1())

    def sign_url(self, object_key: str) -> str:
        """Return a signed CloudFront URL for an object, cache-bucketed.

        Args:
            object_key: Key of the object relative to the distribution root
                (same key used against S3 today).

        Returns:
            A signed HTTPS URL valid until the next bucket boundary.
        """
        url = f"https://{self.domain}/{object_key.lstrip('/')}"
        expires_at = datetime.fromtimestamp(bucket_expires_at(self.bucket_seconds), tz=timezone.utc)
        return str(self._signer.generate_presigned_url(url, date_less_than=expires_at))


_signer_lock = threading.Lock()
_signer_instance: CloudFrontUrlSigner | None = None


def get_cloudfront_signer(settings: Settings) -> CloudFrontUrlSigner:
    """Return the process-wide CloudFront signer, creating it on first use.

    Args:
        settings: Application settings; only read on first call, since RSA key
            parsing is not free and the signer is otherwise stateless per URL.

    Returns:
        A shared, thread-safe signer instance.
    """
    global _signer_instance
    if _signer_instance is not None:
        return _signer_instance
    with _signer_lock:
        if _signer_instance is None:
            _signer_instance = CloudFrontUrlSigner(settings)
        return _signer_instance
