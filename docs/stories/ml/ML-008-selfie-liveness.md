# ML-008 — Selfie Matching and Basic Liveness Detection

**Type:** Feature
**Depends on:** ML-002, ML-003, ML-004, ML-006
**Area:** `backend/app/ml/matching/`

## Goal

Implement the guest selfie → personalized gallery matching pipeline:
1. **Liveness check** — basic quality-based anti-spoof (Phase 1, not full deep learning)
2. **Face detection + quality filter** — reuse ML-002 + ML-003 on the selfie
3. **Embedding generation** — generate 512-d embedding(s) from the selfie
4. **Cosine matching** — compare selfie embedding against event cluster centroids
5. **Return matched cluster IDs** → guest sees only photos containing their face

This is a **synchronous API call** (not Celery) — must complete within ~2 seconds.

## PicSee Context

PicSee does NOT have selfie matching — this is **SpotMe-specific**. However:
- Detection, quality filtering, and embedding use the same PicSee models
- The matching algorithm is a straightforward cosine similarity search
- The liveness detector is a simple heuristic-based check (not from PicSee)

## Matching Pipeline

```
┌──────────────────────────────────────────────────────────┐
│  Guest Selfie (from camera)                              │
│       │                                                  │
│       ▼                                                  │
│  1. BasicLivenessDetector.check(image)                   │
│     → Face size ratio, detection score, sharpness, HSV   │
│       │                                                  │
│       ▼                                                  │
│  2. SCRFDDetector.detect(image, get_faces=1)             │
│     → Single face detection (largest/center)             │
│       │                                                  │
│       ▼                                                  │
│  3. FaceCropper.crop(image, detection)                   │
│     → 112×112 aligned crop                               │
│       │                                                  │
│       ▼                                                  │
│  4. QualityFilter.filter(crop)                           │
│     → Must pass blur + YPR (stricter: 0–30° for selfie) │
│       │                                                  │
│       ▼                                                  │
│  5. DualEmbedder.embed_single(crop)                      │
│     → 512-d primary + secondary embeddings               │
│       │                                                  │
│       ▼                                                  │
│  6. SelfieMatcher.match(embedding, event_id)             │
│     → Cosine similarity vs cluster centroids             │
│     → Top matches above threshold 0.55                   │
│       │                                                  │
│       ▼                                                  │
│  Output: MatchResult(status, matched_cluster_ids)        │
└──────────────────────────────────────────────────────────┘
```

## BasicLivenessDetector (Phase 1)

Phase 1 liveness is **quality-focused, not anti-spoof**. It catches obvious non-selfie
submissions (screenshots, printed photos, blank images) but does NOT detect
sophisticated presentation attacks. Full deep-learning liveness is Phase 2.

```python
class BasicLivenessDetector:
    """Phase 1 liveness: quality heuristics only."""

    def check(self, image_bgr: np.ndarray) -> LivenessResult:
        """
        Checks:
        1. Face size ratio: face bbox area / image area
           → Must be 15%–85% (too small = distant, too large = partial face)
        2. Detection score: SCRFD confidence ≥ 0.7
        3. Sharpness: Laplacian variance ≥ 50 (catches blurry/printed photos)
        4. Saturation: mean HSV saturation > 20 (catches grayscale/B&W printouts)

        Returns LivenessResult(passed, checks_detail)
        """
```

### Liveness Thresholds (from `MLConfig`)

| Check | Threshold | Rationale |
|-------|-----------|-----------|
| Face size ratio min | 0.15 | Face must be at least 15% of selfie |
| Face size ratio max | 0.85 | Face can't be more than 85% (too cropped) |
| Detection score | ≥ 0.7 | Higher than upload threshold (0.5) |
| Laplacian sharpness | ≥ 50 | Reject blurry / screen photos |
| HSV saturation | > 20 | Reject grayscale printouts |

## SelfieMatcher

```python
class SelfieMatcher:
    """Matches a selfie embedding against event cluster centroids."""

    async def match(
        self, selfie_embedding: np.ndarray, event_id: UUID,
        secondary_embedding: np.ndarray | None = None,
    ) -> MatchResult:
        """
        Strategy 1 (default): Load centroids, compute cosine similarities in memory.
        Strategy 2 (large events): Use pgvector HNSW <=> operator for ANN search.

        Matching logic:
        1. Compute cosine similarity: selfie_embedding @ centroids.T
        2. Filter clusters with similarity ≥ selfie_match_threshold (0.55)
        3. Sort by similarity descending
        4. Take top max_cluster_matches (5)
        5. If dual-model: cross-validate with secondary embedding
        """
```

### Dual-Model Cross-Validation

When `dual_model_enabled=True`:
1. Match primary embedding against primary centroids
2. Match secondary embedding against secondary centroids
3. A cluster is a **confirmed match** if BOTH models agree (similarity ≥ threshold)
4. If only one model matches, include the cluster but flag it as `low_confidence`

This dramatically reduces false positives — the two independent embedding spaces
rarely agree on wrong matches.

```python
def cross_validate(
    primary_matches: list[ClusterMatch],
    secondary_matches: list[ClusterMatch],
) -> list[ValidatedMatch]:
    primary_ids = {m.cluster_id for m in primary_matches}
    secondary_ids = {m.cluster_id for m in secondary_matches}

    confirmed = primary_ids & secondary_ids  # Both models agree
    primary_only = primary_ids - secondary_ids  # Possible false positive

    return [
        ValidatedMatch(cluster_id=cid, confidence="high")
        for cid in confirmed
    ] + [
        ValidatedMatch(cluster_id=cid, confidence="low")
        for cid in primary_only
    ]
```

### pgvector HNSW for Large Events

For events with 500+ clusters, in-memory cosine becomes slower. Use pgvector:
```sql
SELECT id, centroid <=> $1::vector AS distance
FROM face_clusters
WHERE event_id = $2
ORDER BY centroid <=> $1::vector
LIMIT 5;
```
The HNSW index (already created in BE-003 migration) makes this ~1ms for any event size.

## Data Structures

```python
@dataclass
class MatchResult:
    status: MatchStatus
    matched_cluster_ids: list[UUID]
    selfie_embedding: np.ndarray | None
    match_details: list[ClusterMatch]

class MatchStatus(str, Enum):
    MATCHED = "matched"
    NO_MATCH = "no_match"
    NO_FACE_DETECTED = "no_face_detected"
    LOW_QUALITY = "low_quality"
    NO_CLUSTERS = "no_clusters"
    LIVENESS_FAILED = "liveness_failed"
    CROP_FAILED = "crop_failed"
    INVALID_IMAGE = "invalid_image"

@dataclass
class ClusterMatch:
    cluster_id: UUID
    similarity: float
    confidence: str  # "high" | "low"
```

## API Integration

This wires into `BE-013 — Guest selfie ingest`:

```python
# POST /api/v1/event/{slug}/selfie
async def submit_selfie(
    slug: str,
    file: UploadFile,
    guest_session: GuestSession = Depends(get_guest_session),
):
    # 1. Decode image
    image_bgr = cv2.imdecode(np.frombuffer(await file.read(), np.uint8), cv2.IMREAD_COLOR)

    # 2. Match
    result = await face_service.match_selfie(image_bgr, event_id)

    # 3. Store results
    guest_session.selfie_embedding = result.selfie_embedding
    guest_session.matched_cluster_ids = result.matched_cluster_ids
    guest_session.match_status = result.status

    return SelfieResponse(status=result.status, photo_count=len(matched_photo_ids))
```

## Performance Target

| Step | Target |
|------|--------|
| Liveness check | < 50ms |
| SCRFD detection (1 face) | < 100ms |
| Quality filter | < 50ms |
| R100 embedding (1 face) | < 200ms |
| AdaFace embedding (1 face) | < 300ms |
| Cosine match (500 clusters) | < 10ms |
| **Total (sync API)** | **< 1.5s** |

If ML host is separate from API server, add network round-trip (~100ms).

## Create / Edit

| File | Action |
|------|--------|
| `backend/app/ml/matching/__init__.py` | Create |
| `backend/app/ml/matching/selfie_matcher.py` | Create |
| `backend/app/ml/matching/liveness.py` | Create |
| Unit tests with synthetic centroids + embeddings | Create |

## Acceptance

- [ ] Synthetic centroid identical to query → `MATCHED` with similarity ~1.0
- [ ] Far vector from all centroids → `NO_MATCH`
- [ ] Blank/solid-color image → `NO_FACE_DETECTED`
- [ ] Blurry selfie → `LOW_QUALITY`
- [ ] Event with no clusters → `NO_CLUSTERS`
- [ ] Screenshot/printout selfie → `LIVENESS_FAILED` (low sharpness/saturation)
- [ ] Dual-model: both agree → `confidence="high"`
- [ ] Dual-model: only primary matches → `confidence="low"`
- [ ] max_cluster_matches=5 → never returns more than 5 clusters
- [ ] Full pipeline completes in < 2s on CPU (< 1.5s on GPU)
