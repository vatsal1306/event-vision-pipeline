"""FaceService facade: detect, embed, cluster, and match selfies."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.ml.clustering import CLUSTER_TYPE, SWEEPER_TYPE, ClusterManager
from app.ml.clustering.locks import FACE_PIPELINE_LOCK_KEY_TEMPLATE, EventClusteringLock
from app.ml.clustering.types import ClusteringResult
from app.ml.config import MLConfig, get_ml_config
from app.ml.exceptions import ClusteringLockBusyError, ClusteringLockError
from app.ml.image_io import decode_photo_bytes
from app.ml.matching.pipeline import SelfieMatchPipeline
from app.ml.matching.types import MatchResult, MatchStatus
from app.ml.model_registry import ModelRegistry, get_model_registry
from app.ml.registry_bootstrap import register_default_model_loaders
from app.models.event import Event
from app.models.face_embedding import FaceEmbedding
from app.models.photo import Photo
from app.services.storage_service import get_storage_service

if TYPE_CHECKING:
    import redis.asyncio as redis

    from app.ml.clustering.recovery.types import RecoveryPipelineResult
    from app.ml.detection.face_cropper import FaceCropper
    from app.ml.detection.scrfd import SCRFDDetector
    from app.ml.embedding.dual_embedder import DualEmbedder
    from app.ml.quality.quality_filter import QualityFilter

logger = structlog.get_logger(__name__)

__all__ = [
    "ClusteringPipelineResult",
    "EventFacePipelineResult",
    "FaceService",
    "ProcessingResult",
]


@dataclass
class ProcessingResult:
    """Outcome of running detection and embedding on one photo."""

    photo_id: uuid.UUID
    face_count: int
    quality_passed_count: int
    embedding_ids: list[uuid.UUID] = field(default_factory=list)
    error: str | None = None


@dataclass
class ClusteringPipelineResult:
    """Outcome of cluster + sweeper + orphan recovery for one event."""

    event_id: uuid.UUID
    cluster_pass: ClusteringResult
    sweeper_pass: ClusteringResult | None
    recovery: RecoveryPipelineResult


@dataclass
class EventFacePipelineResult:
    """Outcome of bulk photo processing plus clustering for one event."""

    event_id: uuid.UUID
    photos_processed: int
    photos_failed: int
    clustering: ClusteringPipelineResult | None


class FaceService:
    """Orchestrate the full face pipeline for Celery workers and the guest API.

    Upload clustering runs on the ``face_processing`` Celery queue. Guest selfie
    matching is a synchronous API call on the app host (CPU).
    """

    def __init__(
        self,
        db: AsyncSession,
        redis_client: redis.Redis | None = None,
        config: MLConfig | None = None,
        registry: ModelRegistry | None = None,
        *,
        detector: SCRFDDetector | None = None,
        cropper: FaceCropper | None = None,
        quality_filter: QualityFilter | None = None,
        embedder: DualEmbedder | None = None,
    ) -> None:
        """Create a service bound to one database session.

        Args:
            db: Async SQLAlchemy session.
            redis_client: Required for clustering and the event pipeline lock.
            config: Optional ML settings override.
            registry: Optional model registry override.
            detector: Optional SCRFD override for tests.
            cropper: Optional cropper override for tests.
            quality_filter: Optional quality-filter override for tests.
            embedder: Optional embedder override for tests.
        """
        self._db = db
        self._redis = redis_client
        self._config = config or get_ml_config()
        self._registry = registry
        self._detector = detector
        self._cropper = cropper
        self._quality_filter = quality_filter
        self._embedder = embedder

    async def process_photo(self, photo_id: uuid.UUID, image_bytes: bytes) -> ProcessingResult:
        """Detect, filter, embed, and store faces for a single original photo.

        Does not run clustering. Failed photos are logged and marked processed
        so the event can still complete.

        Args:
            photo_id: Photo row to update.
            image_bytes: Original file bytes (JPEG/HEIC/PNG/WebP), not the WebP proxy.

        Returns:
            Face counts and stored embedding IDs.
        """
        photo = await self._db.get(Photo, photo_id)
        if photo is None:
            return ProcessingResult(
                photo_id=photo_id,
                face_count=0,
                quality_passed_count=0,
                error=f"Photo {photo_id} not found",
            )

        image = decode_photo_bytes(
            image_bytes,
            filename=photo.filename,
            mime_type=photo.mime_type,
        )
        if image is None:
            logger.warning(
                "face_process_photo_decode_failed",
                photo_id=str(photo_id),
                event_id=str(photo.event_id),
            )
            return await self._finish_photo(
                photo,
                ProcessingResult(
                    photo_id=photo_id,
                    face_count=0,
                    quality_passed_count=0,
                    error="Failed to decode image",
                ),
            )

        try:
            detector, cropper, quality_filter, embedder = self._resolve_upload_models()
            faces = detector.detect(image)
            crops = cropper.crop_all(image, faces, source_photo_id=photo.id)
            embedding_ids: list[uuid.UUID] = []
            passed_crops = []
            passed_quality = []
            for crop in crops:
                quality = quality_filter.filter(crop)
                if not quality.passed:
                    continue
                passed_crops.append(crop)
                passed_quality.append(quality)

            if passed_crops:
                embeddings = embedder.embed_batch([crop.aligned_face for crop in passed_crops])
                for crop, quality, embedding in zip(
                    passed_crops, passed_quality, embeddings, strict=True
                ):
                    bbox = crop.source_detection.bbox
                    yaw = pitch = roll = None
                    if quality.ypr is not None:
                        yaw, pitch, roll = quality.ypr
                    row = FaceEmbedding(
                        photo_id=photo.id,
                        event_id=photo.event_id,
                        embedding=embedding.primary.astype(float).tolist(),
                        secondary_embedding=(
                            embedding.secondary.astype(float).tolist()
                            if embedding.secondary is not None
                            else None
                        ),
                        bbox_x=float(bbox[0]),
                        bbox_y=float(bbox[1]),
                        bbox_w=float(bbox[2]),
                        bbox_h=float(bbox[3]),
                        detection_score=float(crop.source_detection.score),
                        blur_score=quality.blur_score,
                        yaw=yaw,
                        pitch=pitch,
                        roll=roll,
                        quality_passed=True,
                    )
                    self._db.add(row)
                    await self._db.flush()
                    embedding_ids.append(row.id)

            result = ProcessingResult(
                photo_id=photo.id,
                face_count=len(faces),
                quality_passed_count=len(embedding_ids),
                embedding_ids=embedding_ids,
            )
        except Exception as exc:
            logger.warning(
                "face_process_photo_failed",
                photo_id=str(photo_id),
                event_id=str(photo.event_id),
                error=str(exc),
            )
            result = ProcessingResult(
                photo_id=photo.id,
                face_count=0,
                quality_passed_count=0,
                error=str(exc),
            )

        return await self._finish_photo(photo, result)

    async def run_clustering(self, event_id: uuid.UUID) -> ClusteringPipelineResult:
        """Run cluster pass, sweeper, and orphan recovery for an event.

        Args:
            event_id: Event whose stored embeddings should be clustered.

        Returns:
            Combined clustering and recovery results.

        Raises:
            ClusteringLockBusyError: If another clustering pass holds the lock.
        """
        manager = ClusterManager(self._db, redis_client=self._redis, ml_config=self._config)
        cluster_pass = await manager.run_clustering_pass(event_id, CLUSTER_TYPE)
        sweeper_pass = None
        if self._config.sweeper_enabled:
            sweeper_pass = await manager.run_clustering_pass(event_id, SWEEPER_TYPE)
        recovery = await manager.run_recovery(event_id)
        logger.info(
            "face_run_clustering_complete",
            event_id=str(event_id),
            new_clusters=len(cluster_pass.new_clusters),
        )
        return ClusteringPipelineResult(
            event_id=event_id,
            cluster_pass=cluster_pass,
            sweeper_pass=sweeper_pass,
            recovery=recovery,
        )

    async def match_selfie(self, image_bgr: np.ndarray, event_id: uuid.UUID) -> MatchResult:
        """Match a guest selfie against event clusters on the app CPU host.

        Args:
            image_bgr: Decoded selfie image.
            event_id: Event whose clusters are searched.

        Returns:
            Match result. Times out after ``ML_SELFIE_MATCH_TIMEOUT_SECONDS``.
        """
        register_default_model_loaders()
        pipeline = SelfieMatchPipeline(
            self._db,
            config=self._config,
            registry=self._registry_or_default(),
            detector=self._detector,
            cropper=self._cropper,
            quality_filter=self._quality_filter,
            embedder=self._embedder,
        )
        timeout = self._config.selfie_match_timeout_seconds
        try:
            return await asyncio.wait_for(pipeline.run(image_bgr, event_id), timeout=timeout)
        except (TimeoutError, asyncio.TimeoutError):
            logger.error(
                "selfie_match_timeout",
                event_id=str(event_id),
                timeout_seconds=timeout,
            )
            return MatchResult(status=MatchStatus.ERROR)

    async def process_event_photos(self, event_id: uuid.UUID) -> EventFacePipelineResult:
        """Process all photos that have not had faces extracted, then cluster.

        Holds ``face_pipeline_lock`` so a second trigger is a no-op until this
        run finishes. Per-photo failures do not abort the event.

        Args:
            event_id: Event to process.

        Returns:
            Counts plus clustering result when clustering ran.

        Raises:
            ClusteringLockBusyError: If another pipeline run holds the lock.
            ClusteringLockError: If Redis is not configured.
        """
        lock = await self._acquire_pipeline_lock(event_id)
        photos_processed = 0
        photos_failed = 0
        clustering: ClusteringPipelineResult | None = None
        try:
            pending = await self._load_pending_photos(event_id)
            storage = get_storage_service()
            settings = get_settings()
            for photo in pending:
                try:
                    image_bytes = await storage.get_object(
                        settings.s3_bucket_originals,
                        photo.original_s3_key,
                    )
                    result = await self.process_photo(photo.id, image_bytes)
                    if result.error:
                        photos_failed += 1
                    else:
                        photos_processed += 1
                except Exception as exc:
                    logger.warning(
                        "face_event_photo_failed",
                        photo_id=str(photo.id),
                        event_id=str(event_id),
                        error=str(exc),
                    )
                    photos_failed += 1
                    photo.faces_processed = True
                    await self._db.commit()
                await lock.extend()

            clustering = await self.run_clustering(event_id)
        finally:
            await lock.release()

        return EventFacePipelineResult(
            event_id=event_id,
            photos_processed=photos_processed,
            photos_failed=photos_failed,
            clustering=clustering,
        )

    async def _finish_photo(self, photo: Photo, result: ProcessingResult) -> ProcessingResult:
        """Persist face_count, faces_processed, and event.total_faces."""
        photo.face_count = result.face_count
        photo.faces_processed = True
        await self._refresh_event_total_faces(photo.event_id)
        await self._db.commit()
        return result

    async def _refresh_event_total_faces(self, event_id: uuid.UUID) -> None:
        """Set ``events.total_faces`` to the sum of photo face counts."""
        total = await self._db.scalar(
            select(func.coalesce(func.sum(Photo.face_count), 0)).where(Photo.event_id == event_id)
        )
        event = await self._db.get(Event, event_id)
        if event is not None:
            event.total_faces = int(total or 0)

    async def _load_pending_photos(self, event_id: uuid.UUID) -> list[Photo]:
        """Load photos that have not completed face extraction."""
        result = await self._db.execute(
            select(Photo)
            .where(Photo.event_id == event_id, Photo.faces_processed.is_(False))
            .order_by(Photo.uploaded_at)
        )
        return list(result.scalars().all())

    async def _acquire_pipeline_lock(self, event_id: uuid.UUID) -> EventClusteringLock:
        """Acquire the per-event face pipeline lock with backoff."""
        if self._redis is None:
            raise ClusteringLockError(f"Redis client is required to process event {event_id}.")

        lock = EventClusteringLock(
            self._redis,
            event_id,
            ttl_seconds=self._config.face_pipeline_lock_ttl_seconds,
            key_template=FACE_PIPELINE_LOCK_KEY_TEMPLATE,
        )
        delay = self._config.clustering_lock_retry_base_delay_seconds
        attempts = self._config.clustering_lock_retry_attempts
        for attempt in range(1, attempts + 1):
            if await lock.acquire():
                return lock
            logger.info(
                "face_pipeline_lock_retry",
                event_id=str(event_id),
                attempt=attempt,
                delay_seconds=delay,
            )
            if attempt < attempts:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 8.0)
        raise ClusteringLockBusyError(str(event_id))

    def _registry_or_default(self) -> ModelRegistry:
        """Return the injected registry or the process singleton."""
        return self._registry or get_model_registry()

    def _resolve_upload_models(
        self,
    ) -> tuple[SCRFDDetector, FaceCropper, QualityFilter, DualEmbedder]:
        """Load detection, quality, and embedding models for event photos."""
        from app.ml.detection.face_cropper import FaceCropper
        from app.ml.detection.scrfd import SCRFDDetector
        from app.ml.embedding.dual_embedder import DualEmbedder
        from app.ml.quality.quality_filter import QualityFilter

        register_default_model_loaders()
        registry = self._registry_or_default()
        detector = self._detector or registry.get_model("scrfd")
        cropper = self._cropper or FaceCropper(detector=detector)
        quality_filter = self._quality_filter or registry.get_model("quality_filter")
        embedder = self._embedder or registry.get_model("dual_embedder")
        if self._detector is None and not isinstance(detector, SCRFDDetector):
            raise TypeError("Expected SCRFDDetector from the model registry.")
        if self._quality_filter is None and not isinstance(quality_filter, QualityFilter):
            raise TypeError("Expected QualityFilter from the model registry.")
        if self._embedder is None and not isinstance(embedder, DualEmbedder):
            raise TypeError("Expected DualEmbedder from the model registry.")
        return detector, cropper, quality_filter, embedder
