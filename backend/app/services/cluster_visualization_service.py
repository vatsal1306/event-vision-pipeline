"""Export face-cluster galleries for visual inspection."""

from __future__ import annotations

import html
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.exceptions import NotFoundError, StorageError
from app.ml.image_io import decode_photo_bytes
from app.models.event import Event
from app.models.face_cluster import FaceCluster
from app.models.face_embedding import FaceEmbedding
from app.models.photo import Photo
from app.services.storage_service import StorageService, get_storage_service

DEFAULT_MAX_FACES_PER_CLUSTER = 36
CROP_PADDING = 0.25
CROP_SIZE = 160


class EventLabel(Protocol):
    """Minimal event fields needed for the HTML gallery header."""

    id: uuid.UUID
    name: str
    slug: str


@dataclass(frozen=True)
class FaceCropRecord:
    """One face belonging to a cluster (or the unclustered bucket)."""

    embedding_id: uuid.UUID
    photo_id: uuid.UUID
    filename: str
    quality_passed: bool
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float


@dataclass
class ClusterExport:
    """Faces grouped under one cluster id."""

    cluster_id: uuid.UUID | None
    cluster_size: int
    faces: list[FaceCropRecord] = field(default_factory=list)

    @property
    def title(self) -> str:
        """Human-readable heading for the HTML gallery."""
        if self.cluster_id is None:
            return f"Unclustered ({len(self.faces)} faces)"
        return f"Cluster {self.cluster_id} · {self.cluster_size} faces"


def bbox_to_pixels(
    image_width: int,
    image_height: int,
    bbox_x: float,
    bbox_y: float,
    bbox_w: float,
    bbox_h: float,
    padding: float = CROP_PADDING,
) -> tuple[int, int, int, int]:
    """Convert a normalized bbox to inclusive pixel crop coordinates.

    Args:
        image_width: Source image width in pixels.
        image_height: Source image height in pixels.
        bbox_x: Left edge in ``[0, 1]``.
        bbox_y: Top edge in ``[0, 1]``.
        bbox_w: Width in ``[0, 1]``.
        bbox_h: Height in ``[0, 1]``.
        padding: Extra margin as a fraction of bbox size.

    Returns:
        ``(x1, y1, x2, y2)`` clipped to the image bounds.
    """
    pad_w = bbox_w * padding
    pad_h = bbox_h * padding
    x1 = int(round((bbox_x - pad_w) * image_width))
    y1 = int(round((bbox_y - pad_h) * image_height))
    x2 = int(round((bbox_x + bbox_w + pad_w) * image_width))
    y2 = int(round((bbox_y + bbox_h + pad_h) * image_height))
    x1 = max(0, min(x1, image_width - 1))
    y1 = max(0, min(y1, image_height - 1))
    x2 = max(x1 + 1, min(x2, image_width))
    y2 = max(y1 + 1, min(y2, image_height))
    return x1, y1, x2, y2


BgrImage = np.ndarray[Any, Any]


def crop_face_bgr(image_bgr: BgrImage, face: FaceCropRecord) -> BgrImage | None:
    """Crop and resize a face from a BGR image.

    Args:
        image_bgr: Source photo.
        face: Bounding box to crop.

    Returns:
        Square BGR crop, or ``None`` when the bbox is invalid.
    """
    height, width = image_bgr.shape[:2]
    if width <= 0 or height <= 0:
        return None
    x1, y1, x2, y2 = bbox_to_pixels(
        width, height, face.bbox_x, face.bbox_y, face.bbox_w, face.bbox_h
    )
    crop = image_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    return cv2.resize(crop, (CROP_SIZE, CROP_SIZE), interpolation=cv2.INTER_AREA)


def render_cluster_html(
    event: EventLabel,
    clusters: list[ClusterExport],
    skipped_faces: int,
) -> str:
    """Build a standalone HTML gallery from exported cluster folders.

    Args:
        event: Event whose clusters were exported.
        clusters: Cluster groups with relative crop paths already written.
        skipped_faces: Count of faces that could not be cropped.

    Returns:
        HTML document as a string.
    """
    sections: list[str] = []
    for index, cluster in enumerate(clusters, start=1):
        folder = "unclustered" if cluster.cluster_id is None else str(cluster.cluster_id)
        cards: list[str] = []
        for face_index, face in enumerate(cluster.faces):
            rel = f"{folder}/{face_index:04d}_{face.embedding_id}.jpg"
            quality = "ok" if face.quality_passed else "filtered"
            cards.append(
                "<figure class='face'>"
                f"<img src='{html.escape(rel)}' alt='face' "
                f"width='{CROP_SIZE}' height='{CROP_SIZE}' />"
                f"<figcaption>{html.escape(face.filename)} · {quality}</figcaption>"
                "</figure>"
            )
        if not cards:
            cards.append("<p class='empty'>No crops written for this cluster.</p>")
        sections.append(
            f"<section><h2>{index}. {html.escape(cluster.title)}</h2>"
            f"<div class='grid'>{''.join(cards)}</div></section>"
        )

    body = "".join(sections) or "<p>No clusters found for this event.</p>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Clusters · {html.escape(event.name)}</title>
  <style>
    body {{
      font-family: ui-sans-serif, system-ui, sans-serif;
      margin: 24px; background: #f3f0ee; color: #141413;
    }}
    h1 {{ font-size: 1.5rem; }}
    h2 {{ font-size: 1.05rem; margin: 2rem 0 0.75rem; }}
    .meta {{ color: #5c5c57; font-size: 0.9rem; }}
    .grid {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .face {{ margin: 0; width: {CROP_SIZE}px; }}
    .face img {{ display: block; border-radius: 8px; background: #ddd; }}
    .face figcaption {{ font-size: 11px; color: #5c5c57; margin-top: 4px; word-break: break-all; }}
  </style>
</head>
<body>
  <h1>{html.escape(event.name)}</h1>
  <p class="meta">slug={html.escape(event.slug)} · event_id={event.id} ·
  {len(clusters)} groups · skipped crops={skipped_faces}</p>
  {body}
</body>
</html>
"""


class ClusterVisualizationService:
    """Load clustered faces and write an inspectable HTML gallery."""

    def __init__(
        self,
        db: AsyncSession,
        storage: StorageService | None = None,
    ) -> None:
        """Create a visualization service.

        Args:
            db: Database session.
            storage: Object storage used to load originals or proxies.
        """
        self.db = db
        self.storage = storage or get_storage_service()

    async def resolve_event(
        self,
        *,
        event_id: uuid.UUID | None = None,
        event_slug: str | None = None,
    ) -> Event:
        """Load an event by id or slug.

        Args:
            event_id: Event UUID.
            event_slug: Unique event slug.

        Returns:
            Matching event.

        Raises:
            NotFoundError: If neither identifier matches.
            ValueError: If neither identifier is provided.
        """
        if event_id is None and not event_slug:
            raise ValueError("Provide --event-id or --event-slug")
        stmt = select(Event)
        if event_id is not None:
            stmt = stmt.where(Event.id == event_id)
        else:
            stmt = stmt.where(Event.slug == event_slug)
        event = (await self.db.execute(stmt)).scalar_one_or_none()
        if event is None:
            raise NotFoundError("Event")
        return event

    async def load_clusters(
        self,
        event_id: uuid.UUID,
        *,
        include_unclustered: bool,
        max_faces_per_cluster: int,
    ) -> list[ClusterExport]:
        """Load cluster membership for an event.

        Args:
            event_id: Event to inspect.
            include_unclustered: Whether to append faces with no cluster.
            max_faces_per_cluster: Cap on crops written per group.

        Returns:
            Cluster groups ordered by size descending.
        """
        clusters_stmt = (
            select(FaceCluster)
            .where(FaceCluster.event_id == event_id)
            .order_by(FaceCluster.cluster_size.desc(), FaceCluster.created_at.asc())
        )
        db_clusters = list((await self.db.execute(clusters_stmt)).scalars().all())

        faces_stmt = (
            select(FaceEmbedding)
            .options(selectinload(FaceEmbedding.photo))
            .where(FaceEmbedding.event_id == event_id)
            .order_by(FaceEmbedding.created_at.asc())
        )
        embeddings = list((await self.db.execute(faces_stmt)).scalars().all())

        grouped: dict[uuid.UUID | None, list[FaceCropRecord]] = {
            cluster.id: [] for cluster in db_clusters
        }
        if include_unclustered:
            grouped[None] = []

        for embedding in embeddings:
            if embedding.cluster_id not in grouped:
                continue
            bucket = grouped[embedding.cluster_id]
            if len(bucket) >= max_faces_per_cluster:
                continue
            photo = embedding.photo
            bucket.append(
                FaceCropRecord(
                    embedding_id=embedding.id,
                    photo_id=embedding.photo_id,
                    filename=photo.filename if photo is not None else str(embedding.photo_id),
                    quality_passed=embedding.quality_passed,
                    bbox_x=embedding.bbox_x,
                    bbox_y=embedding.bbox_y,
                    bbox_w=embedding.bbox_w,
                    bbox_h=embedding.bbox_h,
                )
            )

        exports: list[ClusterExport] = []
        for cluster in db_clusters:
            exports.append(
                ClusterExport(
                    cluster_id=cluster.id,
                    cluster_size=cluster.cluster_size,
                    faces=grouped.get(cluster.id, []),
                )
            )
        if include_unclustered:
            unclustered = grouped.get(None, [])
            exports.append(
                ClusterExport(cluster_id=None, cluster_size=len(unclustered), faces=unclustered)
            )
        return exports

    async def export_gallery(
        self,
        event: Event,
        output_dir: Path,
        *,
        include_unclustered: bool = False,
        max_faces_per_cluster: int = DEFAULT_MAX_FACES_PER_CLUSTER,
        prefer_proxy: bool = True,
    ) -> Path:
        """Write face crops and ``index.html`` under ``output_dir``.

        Args:
            event: Event to visualize.
            output_dir: Destination directory (created if missing).
            include_unclustered: Include faces with ``cluster_id`` unset.
            max_faces_per_cluster: Per-cluster crop cap.
            prefer_proxy: Load the WebP proxy when present (faster).

        Returns:
            Path to ``index.html``.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        clusters = await self.load_clusters(
            event.id,
            include_unclustered=include_unclustered,
            max_faces_per_cluster=max_faces_per_cluster,
        )
        skipped = 0
        image_cache: dict[uuid.UUID, BgrImage | None] = {}

        for cluster in clusters:
            folder_name = "unclustered" if cluster.cluster_id is None else str(cluster.cluster_id)
            folder = output_dir / folder_name
            folder.mkdir(parents=True, exist_ok=True)
            written: list[FaceCropRecord] = []
            for face_index, face in enumerate(cluster.faces):
                image = await self._load_photo(
                    face.photo_id, image_cache, prefer_proxy=prefer_proxy
                )
                if image is None:
                    skipped += 1
                    continue
                crop = crop_face_bgr(image, face)
                if crop is None:
                    skipped += 1
                    continue
                dest = folder / f"{face_index:04d}_{face.embedding_id}.jpg"
                if not cv2.imwrite(str(dest), crop):
                    skipped += 1
                    continue
                written.append(face)
            cluster.faces = written

        index_path = output_dir / "index.html"
        index_path.write_text(render_cluster_html(event, clusters, skipped), encoding="utf-8")
        return index_path

    async def _load_photo(
        self,
        photo_id: uuid.UUID,
        cache: dict[uuid.UUID, BgrImage | None],
        *,
        prefer_proxy: bool,
    ) -> BgrImage | None:
        """Load and decode a photo, caching by photo id."""
        if photo_id in cache:
            return cache[photo_id]
        photo = await self.db.get(Photo, photo_id)
        if photo is None:
            cache[photo_id] = None
            return None
        settings = get_settings()
        candidates: list[tuple[str, str, str]] = []
        if prefer_proxy and photo.proxy_s3_key:
            candidates.append((settings.s3_bucket_proxies, photo.proxy_s3_key, photo.filename))
        candidates.append((settings.s3_bucket_originals, photo.original_s3_key, photo.filename))
        if not prefer_proxy and photo.proxy_s3_key:
            candidates.append((settings.s3_bucket_proxies, photo.proxy_s3_key, photo.filename))

        decoded: BgrImage | None = None
        for bucket, key, filename in candidates:
            try:
                data = await self.storage.get_object(bucket, key)
            except StorageError:
                continue
            decoded = decode_photo_bytes(data, filename=filename, mime_type=photo.mime_type)
            if decoded is not None:
                break
        cache[photo_id] = decoded
        return decoded
