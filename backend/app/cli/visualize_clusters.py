"""Export a visual HTML gallery of face clusters for an event.

Run from ``backend/`` (so ``.env`` and local S3 data resolve):

    uv run python -m app.cli.visualize_clusters --event-slug my-wedding
    uv run python -m app.cli.visualize_clusters --event-id <uuid> --include-unclustered
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import webbrowser
from pathlib import Path
from uuid import UUID

from app.core.database import async_session_factory
from app.core.exceptions import NotFoundError
from app.services.cluster_visualization_service import (
    DEFAULT_MAX_FACES_PER_CLUSTER,
    ClusterVisualizationService,
)


def build_parser() -> argparse.ArgumentParser:
    """Create the argparse parser for cluster visualization."""
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.visualize_clusters",
        description=(
            "Write an HTML gallery of face crops grouped by cluster so you can "
            "inspect what the matching algorithm grouped together."
        ),
    )
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument("--event-id", type=UUID, help="Event UUID.")
    identity.add_argument("--event-slug", help="Event slug from the photographer dashboard.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Destination directory (default: ./cluster-viz/<event-id>).",
    )
    parser.add_argument(
        "--max-faces",
        type=int,
        default=DEFAULT_MAX_FACES_PER_CLUSTER,
        help=f"Max face crops per cluster (default: {DEFAULT_MAX_FACES_PER_CLUSTER}).",
    )
    parser.add_argument(
        "--include-unclustered",
        action="store_true",
        help="Also export faces that were not assigned to a cluster.",
    )
    parser.add_argument(
        "--originals",
        action="store_true",
        help="Prefer original files instead of WebP proxies (slower, sharper).",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open index.html in the default browser when finished.",
    )
    return parser


async def _run(args: argparse.Namespace) -> Path:
    """Resolve the event and write the gallery."""
    if args.max_faces < 1:
        raise ValueError("--max-faces must be at least 1")

    async with async_session_factory() as db:
        service = ClusterVisualizationService(db)
        event = await service.resolve_event(event_id=args.event_id, event_slug=args.event_slug)
        output_dir = args.output or Path("cluster-viz") / str(event.id)
        index_path = await service.export_gallery(
            event,
            output_dir,
            include_unclustered=args.include_unclustered,
            max_faces_per_cluster=args.max_faces,
            prefer_proxy=not args.originals,
        )
        return index_path


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        index_path = asyncio.run(_run(args))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except NotFoundError:
        print("Event not found. Check --event-id / --event-slug.", file=sys.stderr)
        return 1
    print(f"Wrote {index_path.resolve()}")
    if args.open:
        webbrowser.open(index_path.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
