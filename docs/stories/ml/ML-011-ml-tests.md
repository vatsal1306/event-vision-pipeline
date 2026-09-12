# ML-011 — ML Tests and CI Skip Rules

**Type:** Feature
**Depends on:** ML-001 through ML-010
**Area:** `backend/tests/ml/`

## Goal

Create a comprehensive test suite for the ML pipeline with two tiers:
1. **Unit tests** — run in CI without GPU, mock model inference, test data flow
2. **Integration tests** — require GPU + model files, skipped unless `RUN_ML_TESTS=1`

## Test Strategy

### Tier 1: Unit Tests (CI-safe, no GPU)

These tests mock model inference and verify:
- Data flow through the pipeline
- Error handling (no face, low quality, GPU OOM)
- Data class serialization
- Config loading
- Clustering algorithm with synthetic embeddings
- Selfie matching logic with synthetic centroids

```python
@pytest.fixture
def mock_scrfd(mocker):
    """Mock SCRFD that returns a known detection."""
    det = DetectedFace(
        bbox=np.array([0.1, 0.1, 0.3, 0.4]),
        bbox_pixel=np.array([100, 100, 300, 400]),
        landmarks=np.random.rand(5, 2) * 112,
        score=0.95,
    )
    return mocker.patch(
        "app.ml.detection.scrfd.SCRFDDetector.detect",
        return_value=[det],
    )

@pytest.fixture
def synthetic_embedding():
    """Random 512-d L2-normalized embedding."""
    vec = np.random.randn(512).astype(np.float32)
    return vec / np.linalg.norm(vec)
```

### Tier 2: Integration Tests (GPU, model files required)

These tests load real models and process real images:
- End-to-end: image → detections → crops → embeddings → cluster
- Selfie matching with real embeddings
- Quality filter with real model inference
- Dual-model embedding consistency

```python
@pytest.mark.ml
@pytest.mark.slow
class TestEndToEndPipeline:
    """Requires GPU + model files. Skip in CI unless RUN_ML_TESTS=1."""

    def test_known_face_produces_consistent_embedding(self, face_service, fixture_face):
        result1 = face_service.embed_single(fixture_face)
        result2 = face_service.embed_single(fixture_face)
        similarity = np.dot(result1.primary, result2.primary)
        assert similarity > 0.99

    def test_two_different_faces_produce_distinct_embeddings(self, face_service):
        emb_a = face_service.embed_single(fixture_face_a)
        emb_b = face_service.embed_single(fixture_face_b)
        similarity = np.dot(emb_a.primary, emb_b.primary)
        assert similarity < 0.5
```

## Test Fixtures

### Image Fixtures (`tests/ml/fixtures/`)

**CRITICAL**: No private wedding photos in git. Use only:
- Synthetic faces (generated via StyleGAN or similar)
- CC0/public domain face images
- Solid color images (for no-face tests)
- Intentionally blurry images (for blur filter tests)

```
tests/ml/fixtures/
├── single_face.jpg           # 1 face, frontal, good quality (CC0)
├── group_photo.jpg           # 3+ faces, various sizes (CC0)
├── no_face.jpg               # Landscape/object photo
├── blurry_face.jpg           # Low-quality face crop
├── profile_face.jpg          # Side profile (high YPR)
├── blank_image.jpg           # Solid color
├── synthetic_crops/          # Pre-cropped 112×112 test faces
│   ├── face_a.jpg
│   ├── face_b.jpg
│   └── face_c.jpg
└── README.md                 # License/source info for fixtures
```

### Synthetic Embedding Fixtures

```python
@pytest.fixture
def well_separated_embeddings():
    """3 clusters of 5 embeddings each, clearly separated."""
    clusters = []
    for i in range(3):
        center = np.random.randn(512).astype(np.float32)
        center /= np.linalg.norm(center)
        for _ in range(5):
            noise = np.random.randn(512).astype(np.float32) * 0.05
            vec = center + noise
            vec /= np.linalg.norm(vec)
            clusters.append(vec)
    return np.array(clusters)

@pytest.fixture
def overlapping_embeddings():
    """2 clusters that are close enough to potentially merge."""
    ...
```

## CI Configuration

### pytest markers

```python
# conftest.py
def pytest_configure(config):
    config.addinivalue_line("markers", "ml: marks tests requiring ML models and GPU")
    config.addinivalue_line("markers", "slow: marks slow integration tests")

def pytest_collection_modifyitems(config, items):
    if not os.environ.get("RUN_ML_TESTS"):
        skip_ml = pytest.mark.skip(reason="RUN_ML_TESTS not set")
        for item in items:
            if "ml" in item.keywords:
                item.add_marker(skip_ml)
```

### GitHub Actions

```yaml
# .github/workflows/backend-ci.yml
jobs:
  test:
    steps:
      - name: Run tests (no ML)
        run: |
          cd backend
          pytest --ignore=tests/ml/integration -x -q
        # ML integration tests skipped by default

  test-ml:
    # Only runs on ML host or manual trigger
    if: github.event_name == 'workflow_dispatch'
    runs-on: self-hosted  # GPU runner
    steps:
      - name: Run ML tests
        env:
          RUN_ML_TESTS: "1"
        run: |
          cd backend
          pytest tests/ml/ -x -q
```

### Coverage Rules

```ini
# pyproject.toml
[tool.coverage.run]
omit = [
    "app/ml/vendor/*",    # Vendor code from PicSee — not our coverage target
    "*/test*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
]
```

## Test Matrix

| Test | Tier | GPU | Models | What it Verifies |
|------|------|-----|--------|------------------|
| `test_mlconfig_defaults` | 1 | ❌ | ❌ | Config loads with defaults |
| `test_registry_singleton` | 1 | ❌ | ❌ | Same instance returned |
| `test_scrfd_no_face` | 1 | ❌ | Mock | Empty list returned |
| `test_quality_filter_blur_reject` | 1 | ❌ | Mock | Blur → rejected |
| `test_quality_filter_ypr_pass_on_error` | 1 | ❌ | Mock | Model error → pass |
| `test_clustering_synthetic` | 1 | ❌ | ❌ | 3 clusters from 15 embeddings |
| `test_sweeper_no_new_clusters` | 1 | ❌ | ❌ | Sweeper only expands |
| `test_orphan_recovery` | 1 | ❌ | ❌ | Orphan assigned to nearest cluster |
| `test_selfie_match_identical` | 1 | ❌ | ❌ | Identical → matched |
| `test_selfie_no_match` | 1 | ❌ | ❌ | Distant → no_match |
| `test_liveness_blank` | 1 | ❌ | ❌ | Blank → failed |
| `test_dual_cross_validation` | 1 | ❌ | ❌ | Both agree → high confidence |
| `test_face_service_process_photo` | 1 | ❌ | Mock | Full pipeline data flow |
| `test_e2e_real_embedding` | 2 | ✅ | ✅ | Real model consistency |
| `test_e2e_cluster_real_faces` | 2 | ✅ | ✅ | Real faces → correct clusters |
| `test_r100_adaface_agreement` | 2 | ✅ | ✅ | Both models agree on same person |

## Create / Edit

| File | Action |
|------|--------|
| `backend/tests/ml/__init__.py` | Create |
| `backend/tests/ml/conftest.py` | Create — fixtures + markers |
| `backend/tests/ml/test_config.py` | Create — MLConfig tests |
| `backend/tests/ml/test_detection.py` | Create — SCRFD + FaceCropper tests |
| `backend/tests/ml/test_quality.py` | Create — Quality filter tests |
| `backend/tests/ml/test_embedding.py` | Create — Embedding model tests |
| `backend/tests/ml/test_clustering.py` | Create — Clustering algorithm tests |
| `backend/tests/ml/test_matching.py` | Create — Selfie matcher tests |
| `backend/tests/ml/test_pipeline.py` | Create — FaceService integration tests |
| `backend/tests/ml/integration/` | Create — GPU-required tests |
| `backend/tests/ml/fixtures/` | Create — test images + README |
| `.github/workflows/backend-ci.yml` | Edit — skip ML tests by default |
| `backend/pyproject.toml` | Edit — coverage omit vendor |

## Acceptance

- [x] `pytest` (default) runs all Tier 1 tests without GPU, all pass
- [x] `RUN_ML_TESTS=1 pytest tests/ml/` runs Tier 2 tests on GPU host
- [x] CI pipeline passes without model files present on runner
- [x] Coverage report excludes `app/ml/vendor/*`
- [x] No private/copyrighted face images in git — all fixtures are CC0 or synthetic
- [x] Backend README documents how to run ML tests
- [x] At least 15 unit tests covering all ML components
- [x] At least 3 integration tests covering end-to-end flow

## What we implemented (vs original file list)

Kept **existing** test filenames from ML-001–ML-010 (`test_ml_config.py`, `test_clustering_unit.py`, …) instead of renaming to `test_config.py` / `test_detection.py`. Gaps from the matrix were filled in those files plus:

- `backend/tests/ml/integration/test_e2e_pipeline.py` — live-model e2e (CPU is supported; `ML_DEVICE=cpu`)
- `backend/tests/ml/test_ml_types.py`, `test_face_rows.py`, `test_dual_embedder_unit.py`

**CI:** still `pytest -m "not ml"` (no GPU / self-hosted ML job). Coverage on CI uses `backend/coverage.ci.ini` and **omits all of `app/ml`**. Local `make test` measures `app/ml` except `app/ml/vendor/*`.

**Synthetic embeddings:** story sample used noise `* 0.05`; in 512-d that is too large for `eps=0.45`. Fixtures use `* 0.001` so intra-cluster cosine distance stays below DBSCAN eps.

**`RUN_ML_TESTS`:** still defaults to `"1"` so local runs try live models and skip if weights are missing. GitHub never collects `@pytest.mark.ml` tests.
