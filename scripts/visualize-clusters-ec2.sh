#!/usr/bin/env bash
# Export face-cluster HTML gallery on the app EC2 and copy it to the host.
#
# Run on the EC2 instance, from anywhere:
#   ~/event-vision-pipeline/scripts/visualize-clusters-ec2.sh \
#     --event-id <event_uuid> --include-unclustered
#
# Output on EC2: ~/cluster-viz-out/<event_uuid>/index.html
#
# On laptop, from project root:
#   rm -rf ./cluster-viz/* && rsync -ah --info=progress2 server:~/cluster-viz-out/ cluster-viz/
#
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/event-vision-pipeline}"
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_DIR/docker-compose.prod.yml}"
HOST_OUT_ROOT="${HOST_OUT_ROOT:-$HOME/cluster-viz-out}"

EVENT_ID=""
EVENT_SLUG=""
INCLUDE_UNCLUSTERED=false
USE_ORIGINALS=false
MAX_FACES=""

usage() {
  cat <<'EOF'
Usage: visualize-clusters-ec2.sh (--event-id UUID | --event-slug SLUG) [options]

Export cluster face crops from the backend container and copy the gallery to
~/cluster-viz-out/<event-id-or-slug>/ on this EC2 host.

Options:
  --event-id UUID           Event UUID (from dashboard URL)
  --event-slug SLUG         Event slug (from guest/master share link)
  --include-unclustered     Also export faces with no cluster assignment
  --max-faces N             Max face crops per cluster (default: 36)
  --originals               Use S3 originals instead of WebP proxies
  --host-out-root PATH      Host export root (default: ~/cluster-viz-out)
  -h, --help                Show this help

Examples:
  ./scripts/visualize-clusters-ec2.sh --event-id 0e1236c2-648a-4fd5-b9c4-729ccfdfb83d --include-unclustered
  ./scripts/visualize-clusters-ec2.sh --event-slug my-wedding-slug

Download to laptop:
  scp -r ubuntu@EC2_IP:~/cluster-viz-out/<folder-name> ./cluster-viz/
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --event-id)
      [ $# -ge 2 ] || die "Missing value for --event-id"
      EVENT_ID="$2"
      shift 2
      ;;
    --event-slug)
      [ $# -ge 2 ] || die "Missing value for --event-slug"
      EVENT_SLUG="$2"
      shift 2
      ;;
    --include-unclustered)
      INCLUDE_UNCLUSTERED=true
      shift
      ;;
    --originals)
      USE_ORIGINALS=true
      shift
      ;;
    --max-faces)
      [ $# -ge 2 ] || die "Missing value for --max-faces"
      MAX_FACES="$2"
      shift 2
      ;;
    --host-out-root)
      [ $# -ge 2 ] || die "Missing value for --host-out-root"
      HOST_OUT_ROOT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1 (try --help)"
      ;;
  esac
done

if [ -n "$EVENT_ID" ] && [ -n "$EVENT_SLUG" ]; then
  die "Pass only one of --event-id or --event-slug"
fi
if [ -z "$EVENT_ID" ] && [ -z "$EVENT_SLUG" ]; then
  usage >&2
  die "Provide --event-id or --event-slug"
fi

[ -f "$COMPOSE_FILE" ] || die "Compose file not found: $COMPOSE_FILE"

OUTPUT_KEY="${EVENT_ID:-$EVENT_SLUG}"
CONTAINER_OUT="/tmp/cluster-viz/${OUTPUT_KEY}"
HOST_OUT="${HOST_OUT_ROOT}/${OUTPUT_KEY}"

CLI_ARGS=()
if [ -n "$EVENT_ID" ]; then
  CLI_ARGS+=(--event-id "$EVENT_ID")
else
  CLI_ARGS+=(--event-slug "$EVENT_SLUG")
fi
CLI_ARGS+=(--output "$CONTAINER_OUT")
if [ "$INCLUDE_UNCLUSTERED" = true ]; then
  CLI_ARGS+=(--include-unclustered)
fi
if [ "$USE_ORIGINALS" = true ]; then
  CLI_ARGS+=(--originals)
fi
if [ -n "$MAX_FACES" ]; then
  CLI_ARGS+=(--max-faces "$MAX_FACES")
fi

cd "$REPO_DIR"

echo "==> Running cluster export in backend container..."
docker compose -f "$COMPOSE_FILE" exec -T backend \
  uv run python -m app.cli.visualize_clusters "${CLI_ARGS[@]}"

CONTAINER_ID="$(docker compose -f "$COMPOSE_FILE" ps -q backend)"
[ -n "$CONTAINER_ID" ] || die "Backend container is not running"

echo "==> Copying gallery to ${HOST_OUT} ..."
mkdir -p "$HOST_OUT_ROOT"
rm -rf "$HOST_OUT"
docker cp "${CONTAINER_ID}:${CONTAINER_OUT}" "$HOST_OUT"

INDEX_PATH="${HOST_OUT}/index.html"
[ -f "$INDEX_PATH" ] || die "Export finished but index.html is missing at ${INDEX_PATH}"

echo ""
echo "Done."
echo "  Gallery: ${INDEX_PATH}"
echo "  Faces:   $(find "$HOST_OUT" -name '*.jpg' | wc -l | tr -d ' ') crops"
echo ""
echo "Copy to your laptop:"
echo "  scp -r ubuntu@<EC2_IP>:${HOST_OUT} ./cluster-viz/"
