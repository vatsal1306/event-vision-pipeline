# ML-004 — Dual-Model Face Embeddings: ArcFace R100 + AdaFace VIT-KPRPE

**Type:** Feature
**Depends on:** ML-001, ML-002
**Area:** `backend/app/ml/embedding/`

## Goal

Implement a **dual-model embedding system** that generates 512-dimensional
L2-normalized face embeddings using two complementary models:

1. **Primary: ArcFace R100** (ResNet-100) — battle-tested in PicSee production
2. **Secondary: AdaFace VIT-KPRPE** — newer Vision Transformer with keypoint-relative
   position encoding, used in pix-workers for higher accuracy on difficult faces

The dual-model approach (proven in pix-workers production) provides:
- Higher recall on challenging conditions (makeup, lighting, veils)
- Cross-validation: two independent embedding spaces reduce false matches
- Configurable: can run single-model for cost savings or dual for best accuracy

## Model Files

| Model | File | Size | Source | Format | Embedding Dim |
|-------|------|------|--------|--------|--------------|
| **ArcFace R100** | `model_v1_scratch_training_epoch_20_r100.pt` | 249 MB | PicSee `MODELS/` | PyTorch state_dict | 512 |
| **AdaFace VIT-KPRPE** | `cvlface_adaface_vit_base_kprpe_webface12m/pretrained_model/model.pt` | 439 MB | pix-workers | PyTorch (HuggingFace AutoModel) | 512 |
| **DFA Mobilenet Aligner** | `cvlface_DFA_mobilenet/pretrained_model/model.pt` | 2 MB | pix-workers | PyTorch (HuggingFace AutoModel) | N/A (aligner) |
| **MobileFaceNet** | `preprocessed_transformation_mbf_model_w12m_RE10.tflite` | 13 MB | PicSee `MODELS/` | TFLite | 512 |

## PicSee / pix-workers Source Files

| Source File | SpotMe Target | Notes |
|-------------|---------------|-------|
| PicSee `adaface_insightface/EmbeddingNet.py` | `vendor/adaface_insightface/EmbeddingNet.py` | R100 model loading + inference |
| PicSee `adaface_insightface/backbones.py` | `vendor/adaface_insightface/backbones.py` | `get_model("r100")` architecture |
| PicSee `adaface_insightface/models_adaface/iresnet/model.py` | `vendor/adaface_insightface/models_adaface/` | IResNet-100 backbone |
| pix-workers `embedding/ArcFace.py` | Reference for production R100 | Cleaned production code |
| pix-workers `embedding/AdaFace.py` | `embedding/adaface_vit_kprpe.py` | VIT-KPRPE inference |
| pix-workers `cvlface_adaface_vit_base_kprpe_webface12m/` | `vendor/cvlface_vit_kprpe/` | Full model code + weights |
| pix-workers `cvlface_DFA_mobilenet/` | `vendor/cvlface_dfa_mobilenet/` | Aligner model code + weights |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  DualEmbedder                                           │
│                                                         │
│  face_crop (112×112 BGR)                                │
│       │                                                 │
│       ├──→ ArcFace R100 ──→ 512-d primary embedding     │
│       │    (x/255 - 0.5) / 0.5                          │
│       │                                                 │
│       └──→ AdaFace VIT-KPRPE ──→ 512-d secondary emb    │
│            DFA Aligner → keypoints                      │
│            VIT + keypoints → embedding                  │
│                                                         │
│  Output: EmbeddingResult(primary, secondary)            │
└─────────────────────────────────────────────────────────┘
```

## Implementation Details

### ArcFace R100 (Primary)

```python
class ArcFaceR100(BaseEmbeddingModel):
    """ArcFace ResNet-100 embedding model from PicSee."""

    def __init__(self, model_path: str, device: str = "cuda"):
        self.net = backbones.get_model("r100", fp16=False)
        self.net.load_state_dict(torch.load(model_path, map_location=device))
        self.net.to(device).eval()

    def preprocess(self, face_bgr: np.ndarray) -> torch.Tensor:
        """CRITICAL: Must match PicSee normalization exactly.
        (pixel / 255.0 - 0.5) / 0.5 = pixel / 127.5 - 1.0
        """
        img = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        img = np.transpose(img, (2, 0, 1)).astype(np.float32)
        img = (img / 255.0 - 0.5) / 0.5
        return torch.from_numpy(img).unsqueeze(0)

    def extract_batch(self, faces: list[np.ndarray], batch_size: int = 64) -> np.ndarray:
        """Batch inference with GPU OOM retry at half batch size."""
```

### AdaFace VIT-KPRPE (Secondary)

```python
class AdaFaceVitKprpe(BaseEmbeddingModel):
    """AdaFace VIT-KPRPE with DFA Mobilenet aligner from pix-workers."""

    def __init__(self, model_dir: str, aligner_dir: str, device: str = "cuda"):
        # Load via HuggingFace AutoModel with trust_remote_code
        self.model = AutoModel.from_pretrained(model_dir, local_files_only=True,
                                                trust_remote_code=True)
        self.aligner = AutoModel.from_pretrained(aligner_dir, local_files_only=True,
                                                  trust_remote_code=True)

    def extract_batch(self, faces: list[np.ndarray], batch_size: int = 64) -> np.ndarray:
        """Two-stage: aligner extracts keypoints → VIT generates embeddings."""
        # 1. Transform: RGB, ToTensor, Normalize(0.5, 0.5)
        # 2. self.aligner(input_tensor) → keypoints
        # 3. self.model(input_tensor, keypoints) → embeddings
```

### DualEmbedder (Orchestrator)

```python
class DualEmbedder:
    """Orchestrates primary + secondary embedding generation."""

    def __init__(self, primary: BaseEmbeddingModel, secondary: BaseEmbeddingModel | None):
        self.primary = primary
        self.secondary = secondary

    def embed_batch(self, faces: list[np.ndarray]) -> list[EmbeddingResult]:
        """Generate dual embeddings for a batch of face crops."""
        primary_embeddings = self.primary.extract_batch(faces)
        secondary_embeddings = (
            self.secondary.extract_batch(faces) if self.secondary else None
        )
        return [
            EmbeddingResult(
                primary=primary_embeddings[i],
                secondary=secondary_embeddings[i] if secondary_embeddings is not None else None,
            )
            for i in range(len(faces))
        ]
```

## Data Classes

```python
@dataclass
class EmbeddingResult:
    primary: np.ndarray      # shape (512,), L2-normalized
    secondary: np.ndarray | None  # shape (512,), L2-normalized, or None
    model_primary: str = "r100"
    model_secondary: str | None = "adaface_vit_kprpe"
```

## GPU OOM Handling

From pix-workers production learning:
1. Try `batch_size=64` (from `MLConfig.embedding_batch_size`)
2. If CUDA OOM: catch `torch.cuda.OutOfMemoryError`, halve batch size, retry
3. If still OOM at `batch_size=1`: fall back to MobileFaceNet TFLite on CPU
4. Log all fallback events as warnings

## MobileFaceNet CPU Fallback

```python
class MobileFaceNetTFLite(BaseEmbeddingModel):
    """Lightweight TFLite CPU fallback (~15 faces/sec)."""

    def extract_single(self, face: np.ndarray) -> np.ndarray:
        """Sequential inference — no batching in TFLite."""
```

## VRAM Budget Estimate

| Model | VRAM (loaded) | VRAM (batch=64) | Total |
|-------|--------------|-----------------|-------|
| ArcFace R100 | ~500 MB | ~1.5 GB | ~2 GB |
| AdaFace VIT-KPRPE | ~900 MB | ~2.5 GB | ~3.4 GB |
| DFA Aligner | ~50 MB | ~200 MB | ~250 MB |
| **Dual total** | | | **~5.7 GB** |

Fits comfortably on T4 (16 GB) or A10G (24 GB).

## Database Schema Impact

The existing `face_embeddings` table has a single `embedding vector(512)`. For dual-model:

| Column | Type | Purpose |
|--------|------|---------|
| `embedding` | `vector(512)` | Primary (R100) — used for clustering |
| `secondary_embedding` | `vector(512)` | Secondary (AdaFace) — used for match validation |

**Migration needed**: Add `secondary_embedding` column to `face_embeddings` table.

## Create / Edit

| File | Action |
|------|--------|
| `backend/app/ml/embedding/__init__.py` | Create |
| `backend/app/ml/embedding/base.py` | Create — `BaseEmbeddingModel` ABC |
| `backend/app/ml/embedding/arcface_r100.py` | Create — port from PicSee |
| `backend/app/ml/embedding/adaface_vit_kprpe.py` | Create — port from pix-workers |
| `backend/app/ml/embedding/mobilefacenet.py` | Create — port TFLite wrapper from PicSee |
| `backend/app/ml/embedding/dual_embedder.py` | Create — orchestrator |
| `backend/app/ml/vendor/adaface_insightface/` | Copy from PicSee `adaface_insightface/` |
| `backend/app/ml/vendor/cvlface_vit_kprpe/` | Copy from pix-workers |
| `backend/app/ml/vendor/cvlface_dfa_mobilenet/` | Copy from pix-workers |
| Alembic migration: add `secondary_embedding` | Create |
| Unit tests | Create |

## Acceptance

- [ ] Same crop embedded twice → cosine similarity ≈ 1.0 for both primary and secondary
- [ ] Output shape: `(N, 512)` for both models, L2-normalized (norm ≈ 1.0)
- [ ] `ML_EMBEDDING_MODEL=r100` → only primary embeddings generated
- [ ] `ML_EMBEDDING_MODEL=dual` → both primary and secondary generated
- [ ] GPU OOM with large batch → automatic batch halving + retry
- [ ] CPU MBF path runs without CUDA installed
- [ ] Normalization `(x/255 - 0.5) / 0.5` matches PicSee exactly
- [ ] AdaFace uses `ToTensor + Normalize(0.5, 0.5)` — matches pix-workers
