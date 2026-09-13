"""Tests for cluster visualization helpers and CLI parser."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import numpy as np

from app.cli.visualize_clusters import build_parser
from app.services.cluster_visualization_service import (
    ClusterExport,
    FaceCropRecord,
    bbox_to_pixels,
    crop_face_bgr,
    render_cluster_html,
)


def test_bbox_to_pixels_clips_and_pads() -> None:
    """Normalized bbox is converted to pixel coords and padded."""
    x1, y1, x2, y2 = bbox_to_pixels(100, 200, 0.1, 0.2, 0.2, 0.1, padding=0.0)
    assert (x1, y1, x2, y2) == (10, 40, 30, 60)


def test_crop_face_bgr_returns_square() -> None:
    """Crop resizes to the fixed square used in the gallery."""
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    image[20:40, 20:40] = 255
    face = FaceCropRecord(
        embedding_id=uuid.uuid4(),
        photo_id=uuid.uuid4(),
        filename="a.jpg",
        quality_passed=True,
        bbox_x=0.25,
        bbox_y=0.25,
        bbox_w=0.25,
        bbox_h=0.25,
    )
    crop = crop_face_bgr(image, face)
    assert crop is not None
    assert crop.shape[0] == crop.shape[1]


def test_render_cluster_html_includes_event_and_crops() -> None:
    """HTML gallery names the event and relative crop paths."""
    event_id = uuid.uuid4()
    cluster_id = uuid.uuid4()
    embedding_id = uuid.uuid4()
    event = SimpleNamespace(
        id=event_id,
        name="Demo Wedding",
        slug="demo-wedding",
    )
    clusters = [
        ClusterExport(
            cluster_id=cluster_id,
            cluster_size=1,
            faces=[
                FaceCropRecord(
                    embedding_id=embedding_id,
                    photo_id=uuid.uuid4(),
                    filename="guest.jpg",
                    quality_passed=True,
                    bbox_x=0.1,
                    bbox_y=0.1,
                    bbox_w=0.2,
                    bbox_h=0.2,
                )
            ],
        )
    ]
    document = render_cluster_html(event, clusters, skipped_faces=2)
    assert "Demo Wedding" in document
    assert str(cluster_id) in document
    assert f"0000_{embedding_id}.jpg" in document
    assert "skipped crops=2" in document


def test_visualize_clusters_parser_requires_event_identity() -> None:
    """Argparse requires either --event-id or --event-slug."""
    parser = build_parser()
    try:
        parser.parse_args([])
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert exc.code == 2

    args = parser.parse_args(
        ["--event-slug", "my-wedding", "--include-unclustered", "--max-faces", "8"]
    )
    assert args.event_slug == "my-wedding"
    assert args.include_unclustered is True
    assert args.max_faces == 8
    assert args.event_id is None
