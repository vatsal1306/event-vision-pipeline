"""FaceService facade: detect, embed, cluster, and match selfies."""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
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
from app.ml.face_rows import (
    FAILED_FACE_PLACEHOLDER_EMBEDDING,
    FaceCropWithMeta,
    build_face_embedding_row,
    embedding_vector_to_list,
)
from app.ml.image_io import decode_photo_bytes
from app.ml.matching.pipeline import SelfieMatchPipeline
from app.ml.matching.types import MatchResult, MatchStatus
from app.ml.model_registry import ModelRegistry, get_model_registry
from app.ml.processing_progress import ProcessingProgressTracker
from app.ml.registry_bootstrap import register_default_model_loaders
from app.models.event import Event
from app.models.photo import Photo
from app.services.storage_prefetch import iter_prefetched
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
    total_faces: int = 0
    total_embedded: int = 0
    clustering: ClusteringPipelineResult | None = None


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
            buffer, result = await self._detect_and_buffer_photo(
                photo, image, detector, cropper, quality_filter
            )
            if buffer:
                flushed_ids = await self._flush_embedding_batch(buffer, embedder)
                result.embedding_ids.extend(flushed_ids)
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

    async def process_event_bulk(self, event_id: uuid.UUID) -> EventFacePipelineResult:
        """Alias for :meth:`process_event_photos` (ML-010 bulk entrypoint)."""
        return await self.process_event_photos(event_id)

    async def process_event_photos(self, event_id: uuid.UUID) -> EventFacePipelineResult:
        """Process pending photos with crop buffering, then cluster once.

        Downloads originals through a sliding S3/MinIO window (never loads the
        whole event into RAM). Quality-passed crops accumulate until
        ``embedding_batch_size``, then one GPU embed flush. Clustering runs
        exactly once after the last flush. Per-photo failures do not abort
        the event.

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
        total_faces = 0
        total_embedded = 0
        clustering: ClusteringPipelineResult | None = None
        tracker = (
            ProcessingProgressTracker(
                self._redis,
                event_id,
                ttl_seconds=self._config.processing_progress_ttl_seconds,
            )
            if self._redis is not None
            else None
        )
        try:
            pending = await self._load_pending_photos(event_id)
            if tracker is not None:
                await tracker.start(len(pending))

            storage = get_storage_service()
            settings = get_settings()
            bucket = settings.s3_bucket_originals
            detector, cropper, quality_filter, embedder = self._resolve_upload_models()
            crop_buffer: list[FaceCropWithMeta] = []
            awaiting_flush: dict[uuid.UUID, ProcessingResult] = {}
            batch_size = max(1, self._config.embedding_batch_size)

            async def _download(photo: Photo) -> bytes:
                return await storage.get_object(bucket, photo.original_s3_key)

            async def _publish_progress() -> None:
                if tracker is None:
                    return
                await tracker.update(
                    total_photos=len(pending),
                    processed_photos=photos_processed + photos_failed,
                    failed_photos=photos_failed,
                    total_faces=total_faces,
                    embedded_faces=total_embedded,
                )

            async for photo, image_bytes, download_error in iter_prefetched(
                pending,
                _download,
                ahead=self._config.download_ahead,
            ):
                try:
                    if download_error is not None or image_bytes is None:
                        raise download_error or RuntimeError("Empty download")
                    image = decode_photo_bytes(
                        image_bytes,
                        filename=photo.filename,
                        mime_type=photo.mime_type,
                    )
                    if image is None:
                        raise RuntimeError("Failed to decode image")
                    buffer, result = await self._detect_and_buffer_photo(
                        photo, image, detector, cropper, quality_filter
                    )
                    total_faces += result.face_count
                    if buffer:
                        crop_buffer.extend(buffer)
                        awaiting_flush[photo.id] = result
                    else:
                        await self._finish_photo(photo, result)
                        photos_processed += 1
                    del image
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
                try:
                    while len(crop_buffer) >= batch_size:
                        to_flush = crop_buffer[:batch_size]
                        del crop_buffer[:batch_size]
                        finished, embedded = await self._persist_passed_crops(
                            to_flush, crop_buffer, awaiting_flush, embedder
                        )
                        photos_processed += finished
                        total_embedded += embedded
                except Exception as exc:
                    logger.warning(
                        "face_event_flush_failed",
                        event_id=str(event_id),
                        error=str(exc),
                    )
                    failed_now = await self._fail_awaiting_photos(awaiting_flush)
                    photos_failed += failed_now
                    crop_buffer.clear()
                await lock.extend()
                await _publish_progress()

            if crop_buffer:
                try:
                    finished, embedded = await self._persist_passed_crops(
                        crop_buffer, [], awaiting_flush, embedder
                    )
                    photos_processed += finished
                    total_embedded += embedded
                    crop_buffer.clear()
                except Exception as exc:
                    logger.warning(
                        "face_event_flush_failed",
                        event_id=str(event_id),
                        error=str(exc),
                    )
                    failed_now = await self._fail_awaiting_photos(awaiting_flush)
                    photos_failed += failed_now

            if tracker is not None:
                await tracker.mark_clustering(
                    total_photos=len(pending),
                    processed_photos=photos_processed + photos_failed,
                    failed_photos=photos_failed,
                    total_faces=total_faces,
                    embedded_faces=total_embedded,
                )
            clustering = await self.run_clustering(event_id)
            if tracker is not None:
                await tracker.mark_complete(
                    total_photos=len(pending),
                    processed_photos=photos_processed + photos_failed,
                    failed_photos=photos_failed,
                    total_faces=total_faces,
                    embedded_faces=total_embedded,
                )
        except Exception:
            if tracker is not None:
                await tracker.mark_error("bulk_pipeline_failed")
            raise
        finally:
            await lock.release()

        return EventFacePipelineResult(
            event_id=event_id,
            photos_processed=photos_processed,
            photos_failed=photos_failed,
            total_faces=total_faces,
            total_embedded=total_embedded,
            clustering=clustering,
        )

    async def _detect_and_buffer_photo(
        self,
        photo: Photo,
        image: np.ndarray,
        detector: SCRFDDetector,
        cropper: FaceCropper,
        quality_filter: QualityFilter,
    ) -> tuple[list[FaceCropWithMeta], ProcessingResult]:
        """Detect faces, persist quality rejects, and buffer crops that need GPU embed.

        Args:
            photo: Photo row being processed.
            image: Decoded BGR original.
            detector: SCRFD detector.
            cropper: ArcFace cropper.
            quality_filter: Quality orchestrator.

        Returns:
            Passed crops waiting for embedding, plus a partial processing result.
        """
        faces = await asyncio.to_thread(detector.detect, image)
        crops = await asyncio.to_thread(cropper.crop_all, image, faces, photo.id)
        passed: list[FaceCropWithMeta] = []
        stored_ids: list[uuid.UUID] = []
        for crop in crops:
            quality = quality_filter.filter(crop)
            if quality.passed:
                passed.append(
                    FaceCropWithMeta(
                        crop=crop,
                        photo_id=photo.id,
                        event_id=photo.event_id,
                        quality=quality,
                    )
                )
                continue
            row = build_face_embedding_row(
                photo_id=photo.id,
                event_id=photo.event_id,
                crop=crop,
                quality=quality,
                primary=list(FAILED_FACE_PLACEHOLDER_EMBEDDING),
                secondary=None,
                quality_passed=False,
            )
            self._db.add(row)
            await self._db.flush()
            stored_ids.append(row.id)
        await self._db.commit()
        return passed, ProcessingResult(
            photo_id=photo.id,
            face_count=len(faces),
            quality_passed_count=len(passed),
            embedding_ids=stored_ids,
        )

    async def _flush_embedding_batch(
        self,
        crops: list[FaceCropWithMeta],
        embedder: DualEmbedder,
    ) -> list[uuid.UUID]:
        """Embed a crop buffer and bulk-insert passed-face rows.

        Args:
            crops: Quality-passed crops (may be smaller than config batch size).
            embedder: Dual embedder (already applies CUDA OOM batch halving).

        Returns:
            IDs of inserted embedding rows, in crop order.
        """
        if not crops:
            return []
        face_arrays = [item.crop.aligned_face for item in crops]
        results = await asyncio.to_thread(embedder.embed_batch, face_arrays)
        inserted: list[uuid.UUID] = []
        for item, embedding in zip(crops, results, strict=True):
            secondary = None
            if embedding.secondary is not None:
                secondary = embedding_vector_to_list(embedding.secondary)
            row = build_face_embedding_row(
                photo_id=item.photo_id,
                event_id=item.event_id,
                crop=item.crop,
                quality=item.quality,
                primary=embedding_vector_to_list(embedding.primary),
                secondary=secondary,
                quality_passed=True,
            )
            self._db.add(row)
            await self._db.flush()
            inserted.append(row.id)
        await self._db.commit()
        return inserted

    async def _persist_passed_crops(
        self,
        to_flush: list[FaceCropWithMeta],
        remaining_buffer: list[FaceCropWithMeta],
        awaiting_flush: dict[uuid.UUID, ProcessingResult],
        embedder: DualEmbedder,
    ) -> tuple[int, int]:
        """Flush embeddings and finish photos that have no remaining buffered crops.

        Args:
            to_flush: Crops to embed now.
            remaining_buffer: Crops still waiting for a later flush.
            awaiting_flush: Photos that cannot be marked processed yet.
            embedder: Dual embedder.

        Returns:
            ``(photos_finished, faces_embedded)``.
        """
        inserted = await self._flush_embedding_batch(to_flush, embedder)
        ids_by_photo: dict[uuid.UUID, list[uuid.UUID]] = {}
        for item, row_id in zip(to_flush, inserted, strict=True):
            ids_by_photo.setdefault(item.photo_id, []).append(row_id)
        remaining = Counter(item.photo_id for item in remaining_buffer)
        finished = 0
        for photo_id, row_ids in ids_by_photo.items():
            partial = awaiting_flush.get(photo_id)
            if partial is not None:
                partial.embedding_ids.extend(row_ids)
            if remaining[photo_id] == 0 and photo_id in awaiting_flush:
                photo = await self._db.get(Photo, photo_id)
                if photo is not None:
                    await self._finish_photo(photo, awaiting_flush.pop(photo_id))
                    finished += 1
        return finished, len(inserted)

    async def _fail_awaiting_photos(self, awaiting_flush: dict[uuid.UUID, ProcessingResult]) -> int:
        """Mark photos that never received a successful embed flush as processed failures.

        Args:
            awaiting_flush: Photos still waiting on GPU embed results.

        Returns:
            Number of photos marked failed.
        """
        failed = 0
        for photo_id in list(awaiting_flush):
            leftover = await self._db.get(Photo, photo_id)
            if leftover is not None:
                leftover.faces_processed = True
            awaiting_flush.pop(photo_id, None)
            failed += 1
        if failed:
            await self._db.commit()
        return failed

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
