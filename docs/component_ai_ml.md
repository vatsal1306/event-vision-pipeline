# Component Document: AI/ML Pipeline

> **Version:** 1.0  
> **Last Updated:** September 2026  
> **Scope:** Face Detection, Embedding Extraction, Clustering, Guest Selfie Matching, Liveness Detection  
> **Development Order:** This is Component 3 — built after the backend, integrating the existing PicSee clustering pipeline.  
> **Foundation:** Based on the PicSee clustering pipeline at `/Users/vatsal/Documents/picsee/clustering_pipeline`

---

## Table of Contents

1. [Overview & Relationship to PicSee Pipeline](#1-overview--relationship-to-picsee-pipeline)
2. [Architecture](#2-architecture)
3. [Project Structure](#3-project-structure)
4. [Face Detection Module](#4-face-detection-module)
5. [Face Embedding Extraction](#5-face-embedding-extraction)
6. [Quality Filtering](#6-quality-filtering)
7. [Clustering Pipeline](#7-clustering-pipeline)
8. [Guest Selfie Matching](#8-guest-selfie-matching)
9. [Liveness Detection](#9-liveness-detection)
10. [Integration with Backend](#10-integration-with-backend)
11. [Model Management](#11-model-management)
12. [Performance Optimization](#12-performance-optimization)
13. [Edge Cases & Failure Modes](#13-edge-cases--failure-modes)
14. [Evaluation & Quality Metrics](#14-evaluation--quality-metrics)
15. [Testing Strategy](#15-testing-strategy)

---

## 1. Overview & Relationship to PicSee Pipeline

### 1.1 What We're Building

The AI/ML pipeline is the core differentiator of the platform. It takes a photographer's uploaded event photos and:

1. **Detects** every face in every photo
2. **Extracts** a 512-dimensional embedding (numerical fingerprint) for each detected face
3. **Filters** out low-quality face crops (blurry, extreme angles)
4. **Clusters** embeddings into person-groups (all photos of Person A, all photos of Person B, etc.)
5. **Matches** a guest's selfie against these clusters to deliver their personalized gallery

All of this happens asynchronously during the photographer's upload phase, so by the time a guest scans the link, the heavy computation is already done.

### 1.2 PicSee Pipeline — What Exists

The PicSee clustering pipeline (`/Users/vatsal/Documents/picsee/clustering_pipeline`) is a research/evaluation pipeline that provides the core ML logic:

| PicSee Component | Status | Production Adaptation Needed |
|---|---|---|
| **SCRFD face detection** (ONNX, `det_10g`) | Working, tested | Wrap in service class; add batch support |
| **InsightFace R100 embeddings** (PyTorch) | Working, tested | Wrap in service class; optimize for GPU batch inference |
| **AdaFace embeddings** (PyTorch) | Working, tested (alt model) | Available as fallback/experiment |
| **MobileFaceNet embeddings** (TFLite/PyTorch) | Working, tested (alt model) | Available as lightweight alternative |
| **Blur classifier** (TFLite) | Working, tested | Integrate as quality gate |
| **YPR head pose estimator** (TFLite) | Working, tested | Integrate as quality gate |
| **DBSCAN + Agglomerative clustering** | Working, tested | Adapt for pgvector storage; batch-incremental processing |
| **EmbeddingDatabase** (pandas in-memory) | Working, research-only | Replace with PostgreSQL + pgvector |
| **Evaluation framework** | Working | Retain for model quality monitoring |

### 1.3 What We're Adapting vs. Building New

**Adapting from PicSee:**
- SCRFD detection with multi-scale autodetect
- InsightFace R100 embedding extraction
- Blur and YPR quality filters
- Incremental DBSCAN + agglomerative clustering algorithm
- Centroid-injection merge strategy

**Building New:**
- Service layer wrapping PicSee models for production use
- pgvector integration (replacing pandas EmbeddingDatabase)
- Celery task integration for async processing
- Guest selfie matching via cosine similarity against cluster centroids
- Basic liveness detection for selfie capture
- Batch processing orchestration
- Model loading and GPU management
- Health monitoring and quality metrics

---

## 2. Architecture

### 2.1 Pipeline Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     UPLOAD-TIME PIPELINE                        │
│                (runs during photographer upload)                │
│                                                                │
│  Photo uploaded ──► Celery Task Queue                          │
│                          │                                     │
│                ┌─────────▼──────────┐                          │
│                │   Face Detection    │                          │
│                │   (SCRFD det_10g)   │                          │
│                │                     │                          │
│                │  Input: Image       │                          │
│                │  Output: [bbox,     │                          │
│                │   landmarks, score] │                          │
│                └─────────┬──────────┘                          │
│                          │ per detected face                   │
│                ┌─────────▼──────────┐                          │
│                │   Alignment &      │                          │
│                │   Cropping         │                          │
│                │                    │                          │
│                │  ArcFace 5-point   │                          │
│                │  alignment → 112×112│                          │
│                └─────────┬──────────┘                          │
│                          │                                     │
│                ┌─────────▼──────────┐                          │
│                │   Quality Filter    │                          │
│                │                     │                          │
│                │  Blur: TFLite model │                          │
│                │  YPR: TFLite model  │                          │
│                │                     │                          │
│                │  Reject if:         │                          │
│                │  blur > threshold   │                          │
│                │  yaw/pitch > thresh │                          │
│                └─────────┬──────────┘                          │
│                          │ passes quality                      │
│                ┌─────────▼──────────┐                          │
│                │   Embedding         │                          │
│                │   Extraction        │                          │
│                │                     │                          │
│                │  InsightFace R100   │                          │
│                │  → 512-d L2-norm    │                          │
│                └─────────┬──────────┘                          │
│                          │                                     │
│                ┌─────────▼──────────┐                          │
│                │   Store in         │                          │
│                │   pgvector          │                          │
│                │                     │                          │
│                │  face_embeddings    │                          │
│                │  table with HNSW    │                          │
│                │  index              │                          │
│                └─────────┬──────────┘                          │
│                          │                                     │
│                          ▼                                     │
│                ┌─────────────────────┐                         │
│                │  Incremental         │                         │
│                │  Clustering          │                         │
│                │                      │                         │
│                │  DBSCAN → Agglo     │                         │
│                │  with centroid       │                         │
│                │  injection           │                         │
│                │                      │                         │
│                │  Updates             │                         │
│                │  face_clusters       │                         │
│                │  table               │                         │
│                └──────────────────────┘                         │
└────────────────────────────────────────────────────────────────┘


┌────────────────────────────────────────────────────────────────┐
│                    MATCH-TIME PIPELINE                          │
│                 (runs when guest takes selfie)                  │
│                                                                │
│  Guest selfie ──► API endpoint                                 │
│                       │                                        │
│             ┌─────────▼──────────┐                             │
│             │  Liveness Check     │                             │
│             │  (basic, client     │                             │
│             │   + server side)    │                             │
│             └─────────┬──────────┘                             │
│                       │                                        │
│             ┌─────────▼──────────┐                             │
│             │  Face Detection     │                             │
│             │  + Quality Check    │                             │
│             │  (single face       │                             │
│             │   expected)         │                             │
│             └─────────┬──────────┘                             │
│                       │                                        │
│             ┌─────────▼──────────┐                             │
│             │  Embedding          │                             │
│             │  Extraction         │                             │
│             │  (same R100 model)  │                             │
│             └─────────┬──────────┘                             │
│                       │                                        │
│             ┌─────────▼──────────┐                             │
│             │  Cluster Matching   │                             │
│             │                     │                             │
│             │  Cosine similarity  │                             │
│             │  selfie embedding   │                             │
│             │  vs. cluster        │                             │
│             │  centroids          │                             │
│             │                     │                             │
│             │  threshold: 0.55    │                             │
│             └─────────┬──────────┘                             │
│                       │                                        │
│                       ▼                                        │
│             Return matched cluster_ids                         │
│             → lookup photo_ids from face_embeddings            │
│             → return personalized gallery                      │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 Model Inventory

| Model | File | Format | Size | GPU Required | Purpose |
|---|---|---|---|---|---|
| **SCRFD det_10g** | `det_10g.onnx` | ONNX | ~16MB | Recommended (CUDA EP) | Face detection |
| **InsightFace R100** | `model_v1_scratch_training_epoch_20_r100.pt` | PyTorch | ~250MB | Yes (inference) | Primary embedding extraction |
| **AdaFace IR101** | `adaface_ir101.pt` + `model.yaml` | PyTorch | ~250MB | Yes (inference) | Alternative embedding model |
| **MobileFaceNet** | via `backbones.get_model("mbf_onnx")` | PyTorch/TFLite | ~5MB | No (CPU-viable) | Lightweight fallback |
| **Blur classifier** | `blur_model_tflite_may6_ckpt49.tflite` | TFLite | ~2MB | No (CPU) | Quality filtering |
| **YPR estimator** | `ypr_model_float32.tflite` | TFLite | ~3MB | No (CPU) | Head pose filtering |

---

## 3. Project Structure

The AI/ML pipeline is a Python package within the backend, importable by Celery workers:

```
backend/
├── app/
│   ├── ml/                               # AI/ML pipeline package
│   │   ├── __init__.py
│   │   ├── config.py                     # ML-specific configuration
│   │   │
│   │   ├── detection/                    # Face detection
│   │   │   ├── __init__.py
│   │   │   ├── scrfd.py                  # SCRFD detector (from PicSee)
│   │   │   └── face_cropper.py           # Alignment + cropping
│   │   │
│   │   ├── embedding/                    # Embedding extraction
│   │   │   ├── __init__.py
│   │   │   ├── insightface_r100.py       # R100 model wrapper
│   │   │   ├── adaface.py               # AdaFace model wrapper (alt)
│   │   │   ├── mobilefacenet.py          # MBF model wrapper (lightweight)
│   │   │   └── base.py                  # Abstract embedding interface
│   │   │
│   │   ├── quality/                      # Quality filtering
│   │   │   ├── __init__.py
│   │   │   ├── blur_detector.py          # Blur TFLite model
│   │   │   └── pose_estimator.py         # YPR TFLite model
│   │   │
│   │   ├── clustering/                   # Face clustering
│   │   │   ├── __init__.py
│   │   │   ├── incremental_clusterer.py  # DBSCAN + Agglo (from PicSee)
│   │   │   └── cluster_manager.py        # pgvector-backed cluster ops
│   │   │
│   │   ├── matching/                     # Guest selfie matching
│   │   │   ├── __init__.py
│   │   │   └── selfie_matcher.py         # Centroid-based matching
│   │   │
│   │   ├── liveness/                     # Liveness detection
│   │   │   ├── __init__.py
│   │   │   └── basic_liveness.py         # Basic liveness checks
│   │   │
│   │   ├── pipeline.py                   # High-level pipeline orchestrator
│   │   └── model_registry.py             # Singleton model loader + cache
│   │
│   ├── services/
│   │   └── face_service.py              # Backend service → ML pipeline bridge
│   │
│   └── tasks/
│       └── face_tasks.py                # Celery tasks for face processing
│
├── models/                              # Model weight files
│   ├── det_10g.onnx
│   ├── model_v1_scratch_training_epoch_20_r100.pt
│   ├── blur_model_tflite_may6_ckpt49.tflite
│   ├── ypr_model_float32.tflite
│   └── adaface_insightface/             # Copied from PicSee
│       ├── backbones.py
│       ├── EmbeddingNet.py
│       ├── face_preprocess.py
│       └── models_adaface/
│
└── tests/
    └── ml/
        ├── test_detection.py
        ├── test_embedding.py
        ├── test_clustering.py
        ├── test_matching.py
        └── fixtures/                    # Test images with known faces
```

---

## 4. Face Detection Module

### 4.1 SCRFD Detector (Adapted from PicSee)

```python
class SCRFDDetector:
    """SCRFD face detector using ONNX Runtime.
    
    Adapted from PicSee clustering pipeline. Uses multi-scale detection
    to handle both close-up and distant faces in event photos.
    """

    DEFAULT_DET_THRESH = 0.5
    DEFAULT_NMS_THRESH = 0.4
    DETECTION_SIZES = [640, 128]  # multi-scale

    def __init__(self, model_path: str, device: str = "cuda"):
        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if device == "cuda"
            else ["CPUExecutionProvider"]
        )
        self.session = ort.InferenceSession(model_path, providers=providers)
        self._input_name = self.session.get_inputs()[0].name

    def detect(
        self,
        image: np.ndarray,
        det_thresh: float = DEFAULT_DET_THRESH,
        nms_thresh: float = DEFAULT_NMS_THRESH,
    ) -> list[DetectedFace]:
        """Detect all faces in an image.

        Args:
            image: BGR image as numpy array (from cv2.imread).
            det_thresh: Minimum detection confidence.
            nms_thresh: Non-maximum suppression threshold.

        Returns:
            List of DetectedFace objects with bbox, landmarks, and score.
        """
        all_detections = []
        for size in self.DETECTION_SIZES:
            detections = self._detect_at_scale(image, size, det_thresh)
            all_detections.extend(detections)

        if not all_detections:
            return []

        # NMS across scales
        return self._nms(all_detections, nms_thresh)

    def _detect_at_scale(
        self, image: np.ndarray, size: int, thresh: float
    ) -> list[DetectedFace]:
        """Run detection at a specific input resolution."""
        blob, scale_factor = self._preprocess(image, size)
        outputs = self.session.run(None, {self._input_name: blob})
        return self._postprocess(outputs, scale_factor, thresh)

    def _preprocess(self, image: np.ndarray, size: int) -> tuple:
        """Resize and normalize image for ONNX input."""
        # ... (standard SCRFD preprocessing from PicSee)

    def _postprocess(self, outputs, scale, thresh) -> list[DetectedFace]:
        """Parse ONNX outputs into DetectedFace objects."""
        # ... (standard SCRFD postprocessing from PicSee)

    def _nms(self, detections: list, thresh: float) -> list[DetectedFace]:
        """Non-maximum suppression across multi-scale detections."""
        # ... (standard NMS from PicSee)


@dataclass
class DetectedFace:
    """A single detected face with bounding box and landmarks."""
    bbox: tuple[float, float, float, float]  # x, y, w, h (normalized 0-1)
    landmarks: np.ndarray                      # 5-point landmarks (eyes, nose, mouth)
    score: float                               # detection confidence
```

### 4.2 Face Cropper & Alignment

```python
class FaceCropper:
    """Crop and align detected faces using ArcFace 5-point alignment.
    
    Produces standardized 112x112 face crops suitable for embedding extraction.
    """

    OUTPUT_SIZE = (112, 112)

    # Standard ArcFace alignment template
    ARCFACE_TEMPLATE = np.array([
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ], dtype=np.float32)

    def crop_and_align(
        self, image: np.ndarray, face: DetectedFace
    ) -> np.ndarray | None:
        """Crop and align a single face using landmark-based affine transform.

        Returns 112x112 aligned face crop, or None if alignment fails.
        """
        if face.landmarks is None or len(face.landmarks) < 5:
            return self._fallback_crop(image, face.bbox)

        src_pts = face.landmarks[:5].astype(np.float32)
        tform = SimilarityTransform()
        tform.estimate(src_pts, self.ARCFACE_TEMPLATE)
        aligned = cv2.warpAffine(
            image, tform.params[:2], self.OUTPUT_SIZE, borderValue=0
        )
        return aligned

    def crop_all_faces(
        self, image: np.ndarray, faces: list[DetectedFace]
    ) -> list[FaceCrop]:
        """Crop and align all detected faces in an image."""
        crops = []
        for face in faces:
            crop = self.crop_and_align(image, face)
            if crop is not None:
                crops.append(FaceCrop(image=crop, face=face))
        return crops

    def _fallback_crop(self, image: np.ndarray, bbox: tuple) -> np.ndarray:
        """Simple bbox crop when landmarks are unavailable."""
        x, y, w, h = bbox
        h_img, w_img = image.shape[:2]
        x1, y1 = max(0, int(x * w_img)), max(0, int(y * h_img))
        x2, y2 = min(w_img, int((x + w) * w_img)), min(h_img, int((y + h) * h_img))
        crop = image[y1:y2, x1:x2]
        return cv2.resize(crop, self.OUTPUT_SIZE)


@dataclass
class FaceCrop:
    """An aligned face crop with its source detection metadata."""
    image: np.ndarray            # 112x112 aligned crop
    face: DetectedFace           # original detection info
```

---

## 5. Face Embedding Extraction

### 5.1 Embedding Interface

```python
class BaseEmbeddingModel(ABC):
    """Abstract interface for face embedding models."""

    EMBEDDING_DIM = 512

    @abstractmethod
    def extract(self, face_crop: np.ndarray) -> np.ndarray:
        """Extract embedding from a single 112x112 face crop.

        Returns L2-normalized 512-d float32 vector.
        """
        ...

    @abstractmethod
    def extract_batch(self, face_crops: list[np.ndarray]) -> np.ndarray:
        """Extract embeddings from a batch of face crops.

        Returns (N, 512) L2-normalized float32 array.
        """
        ...
```

### 5.2 InsightFace R100 (Primary Model)

```python
class InsightFaceR100(BaseEmbeddingModel):
    """InsightFace IR-ResNet-100 embedding model.
    
    Primary model for production use. ~250MB, requires GPU for 
    efficient batch processing.
    
    Adapted from PicSee: model_v1_scratch_training_epoch_20_r100.pt
    """

    def __init__(self, model_path: str, device: str = "cuda"):
        self.device = torch.device(device)
        self.model = self._load_model(model_path)
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
        ])

    def _load_model(self, model_path: str) -> torch.nn.Module:
        """Load R100 backbone from PicSee checkpoint."""
        from adaface_insightface.backbones import get_model
        model = get_model("r100", fp16=False)
        state_dict = torch.load(model_path, map_location=self.device)
        model.load_state_dict(state_dict)
        model.to(self.device)
        return model

    def extract(self, face_crop: np.ndarray) -> np.ndarray:
        """Extract embedding from a single face crop."""
        return self.extract_batch([face_crop])[0]

    @torch.no_grad()
    def extract_batch(
        self, face_crops: list[np.ndarray], batch_size: int = 64
    ) -> np.ndarray:
        """Extract embeddings from a batch with GPU batching.

        Processes in sub-batches of `batch_size` to manage GPU memory.
        """
        all_embeddings = []

        for i in range(0, len(face_crops), batch_size):
            batch = face_crops[i : i + batch_size]
            tensors = torch.stack([
                self.transform(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
                for crop in batch
            ]).to(self.device)

            embeddings = self.model(tensors).cpu().numpy()

            # L2 normalize
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms = np.maximum(norms, 1e-10)
            embeddings = embeddings / norms

            all_embeddings.append(embeddings)

        return np.concatenate(all_embeddings, axis=0)
```

### 5.3 MobileFaceNet (Lightweight Fallback)

```python
class MobileFaceNet(BaseEmbeddingModel):
    """MobileFaceNet lightweight embedding model.
    
    ~5MB, runs efficiently on CPU. Used as fallback when GPU is unavailable
    or for real-time selfie processing where latency matters more than accuracy.
    """

    def __init__(self, model_path: str):
        self.interpreter = tf.lite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        self._input_details = self.interpreter.get_input_details()
        self._output_details = self.interpreter.get_output_details()

    def extract(self, face_crop: np.ndarray) -> np.ndarray:
        """Extract embedding using TFLite on CPU."""
        input_data = self._preprocess(face_crop)
        self.interpreter.set_tensor(self._input_details[0]["index"], input_data)
        self.interpreter.invoke()
        embedding = self.interpreter.get_tensor(self._output_details[0]["index"])[0]
        return embedding / np.linalg.norm(embedding)

    def extract_batch(self, face_crops: list[np.ndarray]) -> np.ndarray:
        """Sequential extraction (TFLite doesn't support batching natively)."""
        return np.array([self.extract(crop) for crop in face_crops])
```

---

## 6. Quality Filtering

### 6.1 Blur Detection

```python
class BlurDetector:
    """TFLite-based blur classifier for face crops.
    
    Rejects face crops that are too blurry for reliable embedding extraction.
    Blurry faces degrade clustering quality.
    """

    DEFAULT_THRESHOLD = 0.5  # scores below this are considered blurry

    def __init__(self, model_path: str, threshold: float = DEFAULT_THRESHOLD):
        self.interpreter = tf.lite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        self.threshold = threshold

    def is_blurry(self, face_crop: np.ndarray) -> tuple[bool, float]:
        """Check if a face crop is too blurry.

        Returns:
            (is_blurry, blur_score) where blur_score is 0-1
            (lower = blurrier).
        """
        input_data = self._preprocess(face_crop)
        self.interpreter.set_tensor(
            self.interpreter.get_input_details()[0]["index"], input_data
        )
        self.interpreter.invoke()
        score = self.interpreter.get_tensor(
            self.interpreter.get_output_details()[0]["index"]
        )[0][0]
        return score < self.threshold, float(score)
```

### 6.2 Head Pose Estimation

```python
class PoseEstimator:
    """TFLite-based head pose estimator (Yaw, Pitch, Roll).
    
    Rejects face crops with extreme head angles where facial features
    are partially occluded, degrading embedding quality.
    """

    DEFAULT_YAW_THRESHOLD = 45.0    # degrees
    DEFAULT_PITCH_THRESHOLD = 35.0
    DEFAULT_ROLL_THRESHOLD = 45.0

    def __init__(
        self,
        model_path: str,
        yaw_thresh: float = DEFAULT_YAW_THRESHOLD,
        pitch_thresh: float = DEFAULT_PITCH_THRESHOLD,
        roll_thresh: float = DEFAULT_ROLL_THRESHOLD,
    ):
        self.interpreter = tf.lite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        self.yaw_thresh = yaw_thresh
        self.pitch_thresh = pitch_thresh
        self.roll_thresh = roll_thresh

    def is_extreme_pose(
        self, face_crop: np.ndarray
    ) -> tuple[bool, tuple[float, float, float]]:
        """Check if head pose is too extreme for reliable embedding.

        Returns:
            (is_extreme, (yaw, pitch, roll)) in degrees.
        """
        input_data = self._preprocess(face_crop)
        self.interpreter.set_tensor(
            self.interpreter.get_input_details()[0]["index"], input_data
        )
        self.interpreter.invoke()
        ypr = self.interpreter.get_tensor(
            self.interpreter.get_output_details()[0]["index"]
        )[0]

        yaw, pitch, roll = float(ypr[0]), float(ypr[1]), float(ypr[2])
        is_extreme = (
            abs(yaw) > self.yaw_thresh
            or abs(pitch) > self.pitch_thresh
            or abs(roll) > self.roll_thresh
        )
        return is_extreme, (yaw, pitch, roll)
```

### 6.3 Combined Quality Filter

```python
class QualityFilter:
    """Combined quality filtering pipeline for face crops."""

    def __init__(self, blur_detector: BlurDetector, pose_estimator: PoseEstimator):
        self.blur_detector = blur_detector
        self.pose_estimator = pose_estimator

    def filter(self, face_crop: FaceCrop) -> QualityResult:
        """Run all quality checks on a face crop.

        A face can fail quality checks but still be recorded in the database
        with its quality scores. The embedding is only extracted for 
        faces that pass all checks.
        """
        is_blurry, blur_score = self.blur_detector.is_blurry(face_crop.image)
        is_extreme, ypr = self.pose_estimator.is_extreme_pose(face_crop.image)

        passed = not is_blurry and not is_extreme

        return QualityResult(
            passed=passed,
            blur_score=blur_score,
            yaw=ypr[0],
            pitch=ypr[1],
            roll=ypr[2],
            rejection_reason=(
                "blur" if is_blurry else "pose" if is_extreme else None
            ),
        )

@dataclass
class QualityResult:
    passed: bool
    blur_score: float
    yaw: float
    pitch: float
    roll: float
    rejection_reason: str | None
```

---

## 7. Clustering Pipeline

### 7.1 Incremental Clustering (Adapted from PicSee)

The clustering algorithm is the heart of the PicSee pipeline. It uses a two-stage approach:

1. **DBSCAN** on new embeddings + previous cluster centroids → forms local groups
2. **Agglomerative clustering** on group centroids → merges groups that belong to the same person

The key innovation is **centroid injection** — previous cluster centroids are injected as pseudo-embeddings so new photos can be assigned to existing person-clusters without reprocessing all historical data.

```python
class IncrementalClusterer:
    """Incremental face clustering using DBSCAN + Agglomerative.
    
    Adapted from PicSee clustering pipeline.
    Designed to work with pgvector for persistent storage.
    """

    DEFAULT_DBSCAN_EPS = 0.45
    DEFAULT_AGGLO_THRESHOLD = 0.45
    DEFAULT_BATCH_SIZE = 5000

    def __init__(
        self,
        dbscan_eps: float = DEFAULT_DBSCAN_EPS,
        agglo_threshold: float = DEFAULT_AGGLO_THRESHOLD,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self.dbscan_eps = dbscan_eps
        self.agglo_threshold = agglo_threshold
        self.batch_size = batch_size

    def cluster_incremental(
        self,
        new_embeddings: list[EmbeddingRecord],
        existing_clusters: list[ClusterRecord],
    ) -> ClusteringResult:
        """Run incremental clustering on new embeddings against existing clusters.

        Args:
            new_embeddings: New face embeddings to cluster.
            existing_clusters: Current cluster state (centroids + sizes).

        Returns:
            ClusteringResult with new, expanded, and merged clusters.
        """
        if not new_embeddings:
            return ClusteringResult.empty()

        # Build combined embedding matrix: new embeddings + existing centroids
        all_vectors = []
        all_ids = []
        centroid_indices = set()

        for emb in new_embeddings:
            all_vectors.append(emb.embedding)
            all_ids.append(emb.id)

        for cluster in existing_clusters:
            all_vectors.append(cluster.centroid)
            all_ids.append(f"centroid_{cluster.id}")
            centroid_indices.add(len(all_ids) - 1)

        vectors = np.array(all_vectors, dtype=np.float32)

        # Stage 1: DBSCAN
        dbscan = DBSCAN(
            metric="cosine",
            eps=self.dbscan_eps,
            min_samples=1,
        )
        dbscan_labels = dbscan.fit_predict(vectors)

        # Compute per-group centroids
        group_centroids = self._compute_group_centroids(vectors, dbscan_labels)

        # Stage 2: Agglomerative on group centroids
        if len(group_centroids) > 1:
            agglo = AgglomerativeClustering(
                metric="cosine",
                linkage="average",
                distance_threshold=self.agglo_threshold,
                n_clusters=None,
            )
            agglo_labels = agglo.fit_predict(
                np.array([c.centroid for c in group_centroids])
            )
        else:
            agglo_labels = np.array([0]) if group_centroids else np.array([])

        # Map final labels back to embeddings and determine cluster changes
        return self._build_result(
            vectors, all_ids, dbscan_labels, agglo_labels,
            group_centroids, centroid_indices, existing_clusters,
        )

    def _compute_group_centroids(
        self, vectors: np.ndarray, labels: np.ndarray
    ) -> list:
        """Compute centroid for each DBSCAN group."""
        centroids = []
        for label in set(labels):
            if label == -1:
                continue
            mask = labels == label
            group_vectors = vectors[mask]
            centroid = group_vectors.mean(axis=0)
            centroid = centroid / np.linalg.norm(centroid)  # re-normalize
            centroids.append(GroupCentroid(
                label=label, centroid=centroid, size=mask.sum()
            ))
        return centroids

    def _build_result(
        self, vectors, ids, dbscan_labels, agglo_labels,
        group_centroids, centroid_indices, existing_clusters,
    ) -> ClusteringResult:
        """Categorize clustering results into new/expanded/merged clusters."""
        new_clusters = []
        expanded_clusters = []
        merged_clusters = []

        existing_cluster_map = {
            f"centroid_{c.id}": c for c in existing_clusters
        }

        # Map agglomerative labels to final cluster assignments
        for agglo_label in set(agglo_labels):
            # Get all DBSCAN groups in this agglomerative cluster
            dbscan_groups = [
                group_centroids[i]
                for i, al in enumerate(agglo_labels) if al == agglo_label
            ]

            # Get all embedding IDs in these groups
            member_ids = []
            member_vectors = []
            involved_existing = []

            for group in dbscan_groups:
                for idx, (db_label, emb_id) in enumerate(
                    zip(dbscan_labels, ids)
                ):
                    if db_label == group.label:
                        if idx in centroid_indices:
                            if emb_id in existing_cluster_map:
                                involved_existing.append(
                                    existing_cluster_map[emb_id]
                                )
                        else:
                            member_ids.append(emb_id)
                            member_vectors.append(vectors[idx])

            if not member_ids:
                continue

            # Compute final centroid (weighted by cluster sizes)
            centroid = self._compute_weighted_centroid(
                member_vectors, involved_existing
            )

            if not involved_existing:
                new_clusters.append(NewCluster(
                    embedding_ids=member_ids,
                    centroid=centroid,
                    size=len(member_ids),
                ))
            elif len(involved_existing) == 1:
                expanded_clusters.append(ExpandedCluster(
                    cluster_id=involved_existing[0].id,
                    new_embedding_ids=member_ids,
                    updated_centroid=centroid,
                    new_size=involved_existing[0].size + len(member_ids),
                ))
            else:
                merged_clusters.append(MergedCluster(
                    source_cluster_ids=[c.id for c in involved_existing],
                    new_embedding_ids=member_ids,
                    merged_centroid=centroid,
                    merged_size=sum(c.size for c in involved_existing) + len(member_ids),
                ))

        return ClusteringResult(
            new_clusters=new_clusters,
            expanded_clusters=expanded_clusters,
            merged_clusters=merged_clusters,
        )

    def _compute_weighted_centroid(
        self, new_vectors: list, existing_clusters: list
    ) -> np.ndarray:
        """Compute centroid weighted by cluster size."""
        weighted_sum = np.zeros(512, dtype=np.float32)
        total_weight = 0

        for v in new_vectors:
            weighted_sum += v
            total_weight += 1

        for cluster in existing_clusters:
            weighted_sum += cluster.centroid * cluster.size
            total_weight += cluster.size

        centroid = weighted_sum / total_weight
        return centroid / np.linalg.norm(centroid)
```

### 7.2 Cluster Manager (pgvector Integration)

```python
class ClusterManager:
    """Manages face clusters in PostgreSQL + pgvector.
    
    Bridges the IncrementalClusterer algorithm with persistent storage.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_event_clusters(self, event_id: UUID) -> list[ClusterRecord]:
        """Load all clusters for an event from the database."""
        results = await self.db.execute(
            select(FaceCluster).where(FaceCluster.event_id == event_id)
        )
        return [
            ClusterRecord(
                id=c.id, centroid=np.array(c.centroid),
                size=c.cluster_size,
            )
            for c in results.scalars()
        ]

    async def get_unprocessed_embeddings(
        self, event_id: UUID, batch_size: int = 5000
    ) -> list[EmbeddingRecord]:
        """Get embeddings not yet assigned to a cluster."""
        results = await self.db.execute(
            select(FaceEmbedding)
            .where(
                FaceEmbedding.event_id == event_id,
                FaceEmbedding.cluster_id.is_(None),
            )
            .limit(batch_size)
        )
        return [
            EmbeddingRecord(
                id=e.id, embedding=np.array(e.embedding),
            )
            for e in results.scalars()
        ]

    async def apply_clustering_result(
        self, event_id: UUID, result: ClusteringResult
    ) -> None:
        """Apply clustering results to the database."""
        # New clusters
        for nc in result.new_clusters:
            cluster = FaceCluster(
                event_id=event_id,
                centroid=nc.centroid.tolist(),
                cluster_size=nc.size,
            )
            self.db.add(cluster)
            await self.db.flush()

            await self.db.execute(
                update(FaceEmbedding)
                .where(FaceEmbedding.id.in_(nc.embedding_ids))
                .values(cluster_id=cluster.id)
            )

        # Expanded clusters
        for ec in result.expanded_clusters:
            await self.db.execute(
                update(FaceCluster)
                .where(FaceCluster.id == ec.cluster_id)
                .values(
                    centroid=ec.updated_centroid.tolist(),
                    cluster_size=ec.new_size,
                )
            )
            await self.db.execute(
                update(FaceEmbedding)
                .where(FaceEmbedding.id.in_(ec.new_embedding_ids))
                .values(cluster_id=ec.cluster_id)
            )

        # Merged clusters
        for mc in result.merged_clusters:
            # Create new merged cluster
            merged = FaceCluster(
                event_id=event_id,
                centroid=mc.merged_centroid.tolist(),
                cluster_size=mc.merged_size,
            )
            self.db.add(merged)
            await self.db.flush()

            # Reassign all embeddings from source clusters to merged
            await self.db.execute(
                update(FaceEmbedding)
                .where(FaceEmbedding.cluster_id.in_(mc.source_cluster_ids))
                .values(cluster_id=merged.id)
            )
            await self.db.execute(
                update(FaceEmbedding)
                .where(FaceEmbedding.id.in_(mc.new_embedding_ids))
                .values(cluster_id=merged.id)
            )

            # Delete old source clusters
            await self.db.execute(
                delete(FaceCluster)
                .where(FaceCluster.id.in_(mc.source_cluster_ids))
            )

        await self.db.commit()
```

---

## 8. Guest Selfie Matching

### 8.1 Selfie Match Pipeline

When a guest takes a selfie, the match pipeline runs synchronously (it's fast because event photos are pre-indexed):

```python
class SelfieMatcher:
    """Matches a guest selfie against pre-clustered event faces.
    
    Uses cosine similarity between the selfie embedding and cluster centroids.
    Since clusters are pre-computed during upload, matching is near-instant.
    """

    DEFAULT_MATCH_THRESHOLD = 0.55  # cosine similarity (1 = identical)
    MAX_MATCHES = 5                  # max clusters a single person can match

    def __init__(
        self,
        detector: SCRFDDetector,
        embedder: BaseEmbeddingModel,
        quality_filter: QualityFilter,
        match_threshold: float = DEFAULT_MATCH_THRESHOLD,
    ):
        self.detector = detector
        self.embedder = embedder
        self.quality_filter = quality_filter
        self.match_threshold = match_threshold

    async def match_selfie(
        self, selfie_image: np.ndarray, event_id: UUID, db: AsyncSession
    ) -> MatchResult:
        """Match a guest selfie against event clusters.

        Args:
            selfie_image: BGR image from guest's selfie.
            event_id: Event to search within.
            db: Database session for cluster lookup.

        Returns:
            MatchResult with matched cluster IDs and photo IDs.
        """
        # Step 1: Detect face in selfie (expect exactly 1)
        faces = self.detector.detect(selfie_image)
        if not faces:
            return MatchResult(status="no_face_detected", clusters=[], photo_ids=[])

        # Use the highest-confidence face
        best_face = max(faces, key=lambda f: f.score)

        # Step 2: Crop and align
        cropper = FaceCropper()
        crop = cropper.crop_and_align(selfie_image, best_face)
        if crop is None:
            return MatchResult(status="crop_failed", clusters=[], photo_ids=[])

        # Step 3: Quality check (lenient for selfies — we want the embedding)
        quality = self.quality_filter.filter(FaceCrop(image=crop, face=best_face))
        if not quality.passed:
            return MatchResult(
                status="low_quality",
                quality_issue=quality.rejection_reason,
                clusters=[], photo_ids=[],
            )

        # Step 4: Extract embedding
        embedding = self.embedder.extract(crop)

        # Step 5: Compare against event cluster centroids
        clusters = await db.execute(
            select(FaceCluster).where(FaceCluster.event_id == event_id)
        )
        clusters = clusters.scalars().all()

        if not clusters:
            return MatchResult(status="no_clusters", clusters=[], photo_ids=[])

        # Compute cosine similarities
        centroids = np.array([np.array(c.centroid) for c in clusters])
        similarities = centroids @ embedding  # dot product (vectors are L2-normalized)

        # Find matches above threshold
        matched_indices = np.where(similarities >= self.match_threshold)[0]

        # Sort by similarity (best first), limit matches
        matched_indices = matched_indices[
            np.argsort(similarities[matched_indices])[::-1]
        ][:self.MAX_MATCHES]

        matched_cluster_ids = [clusters[i].id for i in matched_indices]

        if not matched_cluster_ids:
            return MatchResult(status="no_match", clusters=[], photo_ids=[])

        # Step 6: Get photo IDs from matched clusters
        photo_results = await db.execute(
            select(FaceEmbedding.photo_id)
            .where(FaceEmbedding.cluster_id.in_(matched_cluster_ids))
            .distinct()
        )
        photo_ids = [r[0] for r in photo_results]

        return MatchResult(
            status="matched",
            clusters=matched_cluster_ids,
            photo_ids=photo_ids,
            match_count=len(photo_ids),
            similarity_scores={
                str(clusters[i].id): float(similarities[i])
                for i in matched_indices
            },
        )


@dataclass
class MatchResult:
    status: str  # "matched", "no_match", "no_face_detected", "low_quality", etc.
    clusters: list[UUID]
    photo_ids: list[UUID]
    match_count: int = 0
    quality_issue: str | None = None
    similarity_scores: dict[str, float] | None = None
```

### 8.2 pgvector Alternative: Direct Vector Search

For events with very many clusters (hundreds), a direct pgvector cosine similarity search can be more efficient:

```python
async def match_selfie_pgvector(
    self, embedding: np.ndarray, event_id: UUID, db: AsyncSession,
    threshold: float = 0.55, limit: int = 5,
) -> list[UUID]:
    """Use pgvector's HNSW index for direct nearest-neighbor search."""
    result = await db.execute(
        text("""
            SELECT id, 1 - (centroid <=> :embedding) as similarity
            FROM face_clusters
            WHERE event_id = :event_id
            AND 1 - (centroid <=> :embedding) >= :threshold
            ORDER BY centroid <=> :embedding
            LIMIT :limit
        """),
        {
            "embedding": embedding.tolist(),
            "event_id": str(event_id),
            "threshold": threshold,
            "limit": limit,
        },
    )
    return [row.id for row in result]
```

---

## 9. Liveness Detection

### 9.1 Basic Server-Side Checks

The goal is to ensure the selfie is a real face captured live, not a photo of a photo. Phase 1 implements basic checks; advanced liveness (depth, head-turn challenges) is Phase 2.

```python
class BasicLivenessDetector:
    """Basic liveness detection to prevent photo-of-photo attacks.
    
    Phase 1 implementation focuses on simple heuristics rather than 
    deep learning liveness models. The primary goal is ensuring a 
    good-quality face capture for accurate matching.
    """

    MIN_FACE_SIZE_RATIO = 0.15    # face must be at least 15% of image
    MAX_FACE_SIZE_RATIO = 0.85    # face must not be more than 85% of image
    MIN_DETECTION_SCORE = 0.7     # high confidence face detection required
    MIN_FACE_SHARPNESS = 50.0     # Laplacian variance threshold

    def check(
        self, image: np.ndarray, detected_face: DetectedFace
    ) -> LivenessResult:
        """Run basic liveness checks on the selfie image.

        These checks aren't foolproof against sophisticated attacks,
        but they ensure the selfie is of sufficient quality for face matching.
        """
        checks = {}

        # Check 1: Face size relative to image
        img_h, img_w = image.shape[:2]
        face_area = detected_face.bbox[2] * detected_face.bbox[3]  # w * h (normalized)
        checks["face_size"] = (
            self.MIN_FACE_SIZE_RATIO <= face_area <= self.MAX_FACE_SIZE_RATIO
        )

        # Check 2: Detection confidence
        checks["detection_confidence"] = (
            detected_face.score >= self.MIN_DETECTION_SCORE
        )

        # Check 3: Image sharpness (Laplacian variance)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        checks["sharpness"] = sharpness >= self.MIN_FACE_SHARPNESS

        # Check 4: Not a grayscale/B&W image (screens sometimes show desaturated)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1].mean()
        checks["color_present"] = saturation > 20

        passed = all(checks.values())
        failed_checks = [k for k, v in checks.items() if not v]

        return LivenessResult(
            passed=passed,
            checks=checks,
            failed_checks=failed_checks,
            face_size_ratio=face_area,
            sharpness=sharpness,
        )


@dataclass
class LivenessResult:
    passed: bool
    checks: dict[str, bool]
    failed_checks: list[str]
    face_size_ratio: float
    sharpness: float
```

### 9.2 Client-Side Checks (Frontend Complement)

The frontend selfie capture component (documented in the Frontend Component Doc) performs real-time face detection using MediaPipe/face-api.js to:
- Ensure a face is visible before allowing capture
- Guide positioning via the face outline overlay
- Check basic focus/sharpness before sending to server

These client-side checks are UX-focused; the server-side checks above are the authoritative validation.

---

## 10. Integration with Backend

### 10.1 Face Service (Backend → ML Bridge)

```python
class FaceService:
    """Backend service that orchestrates the ML pipeline.
    
    Used by Celery tasks and API endpoints to interact with the ML models.
    """

    def __init__(
        self,
        detector: SCRFDDetector,
        embedder: BaseEmbeddingModel,
        quality_filter: QualityFilter,
        clusterer: IncrementalClusterer,
        matcher: SelfieMatcher,
        liveness: BasicLivenessDetector,
    ):
        self.detector = detector
        self.embedder = embedder
        self.quality_filter = quality_filter
        self.clusterer = clusterer
        self.matcher = matcher
        self.liveness = liveness

    def process_photo(self, image_bytes: bytes) -> PhotoProcessingResult:
        """Full face processing pipeline for a single uploaded photo.

        Called by Celery worker for each uploaded photo.
        """
        image = cv2.imdecode(
            np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR
        )
        if image is None:
            return PhotoProcessingResult(faces=[], error="Failed to decode image")

        # Detect faces
        faces = self.detector.detect(image)
        if not faces:
            return PhotoProcessingResult(faces=[], face_count=0)

        # Crop and align
        cropper = FaceCropper()
        crops = cropper.crop_all_faces(image, faces)

        results = []
        for crop in crops:
            # Quality check
            quality = self.quality_filter.filter(crop)

            if quality.passed:
                # Extract embedding
                embedding = self.embedder.extract(crop.image)
                results.append(FaceResult(
                    embedding=embedding,
                    bbox=crop.face.bbox,
                    detection_score=crop.face.score,
                    blur_score=quality.blur_score,
                    quality_passed=True,
                ))
            else:
                results.append(FaceResult(
                    embedding=None,
                    bbox=crop.face.bbox,
                    detection_score=crop.face.score,
                    blur_score=quality.blur_score,
                    quality_passed=False,
                    rejection_reason=quality.rejection_reason,
                ))

        return PhotoProcessingResult(
            faces=results,
            face_count=len(faces),
            quality_passed_count=sum(1 for r in results if r.quality_passed),
        )

    async def run_clustering(self, event_id: UUID, db: AsyncSession) -> None:
        """Run incremental clustering for an event."""
        cluster_mgr = ClusterManager(db)
        existing = await cluster_mgr.get_event_clusters(event_id)
        new_embeddings = await cluster_mgr.get_unprocessed_embeddings(event_id)

        if not new_embeddings:
            return

        result = self.clusterer.cluster_incremental(new_embeddings, existing)
        await cluster_mgr.apply_clustering_result(event_id, result)

    async def match_guest_selfie(
        self, selfie_bytes: bytes, event_id: UUID, db: AsyncSession
    ) -> MatchResult:
        """Process a guest selfie and find their photos."""
        image = cv2.imdecode(
            np.frombuffer(selfie_bytes, np.uint8), cv2.IMREAD_COLOR
        )
        if image is None:
            return MatchResult(status="invalid_image", clusters=[], photo_ids=[])

        return await self.matcher.match_selfie(image, event_id, db)
```

### 10.2 Celery Tasks

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def detect_and_embed_faces(self, photo_id: str, event_id: str) -> dict:
    """Celery task: detect faces and extract embeddings for one photo."""
    face_service = get_face_service()  # singleton with loaded models
    storage = get_storage_service()
    db = get_sync_db_session()

    try:
        photo = db.get(Photo, photo_id)
        image_bytes = storage.download_sync(photo.original_s3_key)

        result = face_service.process_photo(image_bytes)

        for face in result.faces:
            if face.quality_passed and face.embedding is not None:
                embedding = FaceEmbedding(
                    photo_id=UUID(photo_id),
                    event_id=UUID(event_id),
                    embedding=face.embedding.tolist(),
                    bbox_x=face.bbox[0],
                    bbox_y=face.bbox[1],
                    bbox_w=face.bbox[2],
                    bbox_h=face.bbox[3],
                    detection_score=face.detection_score,
                    blur_score=face.blur_score,
                )
                db.add(embedding)

        photo.face_count = result.face_count
        db.commit()

        return {
            "photo_id": photo_id,
            "faces_detected": result.face_count,
            "embeddings_stored": result.quality_passed_count,
        }

    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2)
def update_event_clusters(self, event_id: str) -> dict:
    """Celery task: run incremental clustering for an event.
    
    Called after each batch of face detections completes.
    Uses a Redis lock to prevent concurrent clustering on the same event.
    """
    lock_key = f"clustering_lock:{event_id}"
    lock = redis_client.lock(lock_key, timeout=300)  # 5 min max

    if not lock.acquire(blocking=False):
        # Another clustering job is running; retry later
        raise self.retry(countdown=30)

    try:
        face_service = get_face_service()
        db = get_async_db_session()

        asyncio.run(face_service.run_clustering(UUID(event_id), db))

        return {"event_id": event_id, "status": "clustered"}
    finally:
        lock.release()
```

---

## 11. Model Management

### 11.1 Model Registry (Singleton Loader)

Models are expensive to load (GPU memory allocation). The `ModelRegistry` ensures each model is loaded exactly once and shared across all Celery workers on the same process.

```python
class ModelRegistry:
    """Singleton model loader and cache.
    
    Loads models lazily on first use and caches them in memory.
    Each Celery worker process gets its own model instances.
    """

    _instance: "ModelRegistry | None" = None
    _lock = threading.Lock()

    def __init__(self):
        self._models: dict[str, Any] = {}
        self._config = get_ml_config()

    @classmethod
    def get_instance(cls) -> "ModelRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_detector(self) -> SCRFDDetector:
        if "detector" not in self._models:
            self._models["detector"] = SCRFDDetector(
                model_path=self._config.scrfd_model_path,
                device=self._config.device,
            )
        return self._models["detector"]

    def get_embedder(self) -> BaseEmbeddingModel:
        if "embedder" not in self._models:
            model_class = {
                "r100": InsightFaceR100,
                "mbf": MobileFaceNet,
            }[self._config.embedding_model]
            self._models["embedder"] = model_class(
                model_path=self._config.embedding_model_path,
                **({"device": self._config.device}
                   if self._config.embedding_model == "r100" else {}),
            )
        return self._models["embedder"]

    def get_quality_filter(self) -> QualityFilter:
        if "quality_filter" not in self._models:
            blur = BlurDetector(
                model_path=self._config.blur_model_path,
                threshold=self._config.blur_threshold,
            )
            pose = PoseEstimator(
                model_path=self._config.ypr_model_path,
                yaw_thresh=self._config.yaw_threshold,
                pitch_thresh=self._config.pitch_threshold,
                roll_thresh=self._config.roll_threshold,
            )
            self._models["quality_filter"] = QualityFilter(blur, pose)
        return self._models["quality_filter"]

    def get_face_service(self) -> FaceService:
        """Get fully configured FaceService with all models loaded."""
        return FaceService(
            detector=self.get_detector(),
            embedder=self.get_embedder(),
            quality_filter=self.get_quality_filter(),
            clusterer=IncrementalClusterer(),
            matcher=SelfieMatcher(
                detector=self.get_detector(),
                embedder=self.get_embedder(),
                quality_filter=self.get_quality_filter(),
            ),
            liveness=BasicLivenessDetector(),
        )
```

### 11.2 ML Configuration

```python
class MLConfig(BaseModel):
    """ML pipeline configuration."""

    # Device
    device: str = "cuda"  # "cuda" or "cpu"

    # Model paths
    scrfd_model_path: str = "models/det_10g.onnx"
    embedding_model: str = "r100"  # "r100", "mbf"
    embedding_model_path: str = "models/model_v1_scratch_training_epoch_20_r100.pt"
    blur_model_path: str = "models/blur_model_tflite_may6_ckpt49.tflite"
    ypr_model_path: str = "models/ypr_model_float32.tflite"

    # Quality thresholds
    blur_threshold: float = 0.5
    yaw_threshold: float = 45.0
    pitch_threshold: float = 35.0
    roll_threshold: float = 45.0

    # Clustering
    dbscan_eps: float = 0.45
    agglo_threshold: float = 0.45
    clustering_batch_size: int = 5000

    # Matching
    selfie_match_threshold: float = 0.55
    max_cluster_matches: int = 5

    # Processing
    embedding_batch_size: int = 64  # GPU batch size for embedding extraction
```

---

## 12. Performance Optimization

### 12.1 GPU Batch Processing

The primary bottleneck is embedding extraction. Batch processing on GPU significantly improves throughput:

| Approach | Throughput (faces/sec) | Notes |
|---|---|---|
| CPU sequential (R100) | ~2 faces/sec | Impractical for production |
| GPU single (R100) | ~30 faces/sec | Baseline |
| GPU batch=32 (R100) | ~200 faces/sec | 6.7x improvement |
| GPU batch=64 (R100) | ~350 faces/sec | Optimal for ~8GB GPU |
| CPU sequential (MBF) | ~15 faces/sec | TFLite, viable for selfie matching |

**Processing time estimates for a 10,000-photo event** (assuming 1.5 faces per photo on average):

| Stage | Time | Can Parallel? |
|---|---|---|
| Face detection (SCRFD) | ~5 minutes | Yes (per-photo, multi-worker) |
| Quality filtering | ~1 minute | Yes (per-face, CPU) |
| Embedding extraction (R100, batch=64) | ~7 minutes | Partially (GPU-bound) |
| Clustering (DBSCAN + Agglo) | ~30 seconds | No (sequential per event) |
| **Total** | **~13 minutes** | |

### 12.2 Celery Worker Configuration

```python
# For face processing workers (GPU-capable)
celery_app.conf.worker_concurrency = 2  # limit concurrency to avoid GPU OOM
celery_app.conf.worker_prefetch_multiplier = 1  # don't prefetch extra tasks

# Separate queue for face tasks
celery_app.conf.task_routes = {
    "app.tasks.face_tasks.*": {"queue": "face_processing"},
    "app.tasks.photo_tasks.*": {"queue": "photo_processing"},
    "app.tasks.notification_tasks.*": {"queue": "notifications"},
}
```

### 12.3 Batch Processing Strategy

Instead of processing one photo at a time through the entire pipeline, batch photos for efficient GPU utilization:

```python
@celery_app.task
def process_photo_batch(photo_ids: list[str], event_id: str) -> dict:
    """Process a batch of photos together for efficient GPU batching.
    
    1. Download all images
    2. Detect all faces (can be per-image on GPU)
    3. Crop all faces
    4. Filter quality (CPU, fast)
    5. Batch-extract all embeddings (single GPU forward pass)
    6. Store all embeddings
    7. Run clustering once for the batch
    """
    registry = ModelRegistry.get_instance()
    detector = registry.get_detector()
    embedder = registry.get_embedder()
    quality_filter = registry.get_quality_filter()

    all_crops_with_meta = []

    for photo_id in photo_ids:
        image_bytes = download_photo(photo_id)
        image = decode_image(image_bytes)
        faces = detector.detect(image)

        cropper = FaceCropper()
        for face in faces:
            crop = cropper.crop_and_align(image, face)
            if crop is not None:
                quality = quality_filter.filter(FaceCrop(image=crop, face=face))
                if quality.passed:
                    all_crops_with_meta.append({
                        "crop": crop,
                        "photo_id": photo_id,
                        "face": face,
                        "blur_score": quality.blur_score,
                    })

    if all_crops_with_meta:
        # Single batched embedding extraction
        crops = [c["crop"] for c in all_crops_with_meta]
        embeddings = embedder.extract_batch(crops)

        # Store all embeddings
        for emb, meta in zip(embeddings, all_crops_with_meta):
            store_embedding(meta["photo_id"], event_id, emb, meta["face"], meta["blur_score"])

    # Run clustering for the batch
    run_clustering(event_id)

    return {"processed": len(photo_ids), "embeddings": len(all_crops_with_meta)}
```

---

## 13. Edge Cases & Failure Modes

| Scenario | Handling | Fallback |
|---|---|---|
| **No faces detected in photo** | Photo is stored but has `face_count=0`. It won't appear in any guest's matched gallery but is visible in the couple's full gallery and photographer's dashboard. | None needed — many event photos (food, décor, wide shots) have no faces. |
| **Blurry face crop** | Rejected by blur filter. Face is detected but no embedding is stored. Photo's `face_count` includes detected (not just embedded) faces. | If many faces in an event are blurry (bad lighting), consider lowering `blur_threshold` dynamically. |
| **Extreme head pose** | Rejected by YPR filter. Same handling as blur. | Side profiles are common at events. Thresholds are set to 45° yaw, which is generous. |
| **Same person, different appearance** (heavy makeup Mehndi vs. natural Wedding day) | Clustering may create two separate clusters for the same person. Guest selfie matching checks against all clusters, so they'll still see photos from both days. | If clusters are very close but not merged, lower `agglo_threshold`. Manual merge UI in Phase 2. |
| **Large group photos** (50+ people in one frame) | SCRFD detects all faces with multi-scale. Embedding extraction processes all. May produce many small, low-quality face crops from distant faces. | Quality filter rejects very small/blurry faces. Only clear faces are embedded. |
| **Children** (different appearance across multi-day event) | Children's faces change less dramatically than expected between event days, but small children can be harder to match. | Clustering handles this reasonably; selfie matching threshold can be slightly lowered. |
| **Selfie with glasses/sunglasses** | InsightFace R100 handles moderate occlusion. Sunglasses significantly reduce accuracy. | If no match, show "Try removing glasses and retaking your selfie" message. |
| **Selfie from photo of photo** (liveness attack) | Basic liveness checks (sharpness, color, face size) catch obvious cases. | Not foolproof in Phase 1. Advanced liveness in Phase 2. |
| **No match found for guest** | Return "no_match" status. Frontend shows helpful message with "Retake Selfie" option. | Could also show "Browse All Photos" option (configurable by photographer). |
| **GPU out of memory** | Reduce batch size or fall back to CPU inference via MobileFaceNet. | ModelRegistry can auto-detect available GPU memory and adjust batch size. |
| **HEIC/HEIF images** | Converted via `pillow-heif` in the upload pipeline before reaching the ML pipeline. ML pipeline always receives standard JPEG/PNG. | Conversion happens in the image processing step, not ML step. |
| **Corrupt/unreadable image** | `cv2.imdecode` returns None. Task logs error and marks photo as `processing_failed`. | Photographer sees failed status; can re-upload. |

---

## 14. Evaluation & Quality Metrics

### 14.1 Offline Evaluation (Pre-Deployment)

Using the PicSee evaluation framework with labeled test datasets:

| Metric | Target | Measurement |
|---|---|---|
| **Face detection recall** | > 95% | % of visible faces detected (at standard threshold) |
| **Face detection precision** | > 98% | % of detections that are actual faces (not false positives) |
| **Embedding quality (LFW accuracy)** | > 99% | Standard LFW benchmark for R100 |
| **Cluster purity** | > 90% | % of clusters containing only one identity |
| **Cluster completeness** | > 85% | % of identities captured in a single cluster (not split) |
| **Selfie match accuracy** | > 95% | % of selfies correctly matched to the right cluster |
| **Selfie false match rate** | < 2% | % of selfies matched to wrong cluster |

### 14.2 Production Monitoring

```python
# Metrics to track per event
class EventProcessingMetrics:
    event_id: UUID
    total_photos: int
    total_faces_detected: int
    total_embeddings_stored: int
    quality_rejection_rate: float     # % of faces rejected by quality filter
    cluster_count: int                # number of person-clusters
    avg_cluster_size: float           # average photos per cluster
    processing_time_seconds: float
    selfie_match_rate: float          # % of guest selfies that find matches
    avg_match_count: float            # average photos matched per guest
```

These metrics are logged per event and can be reviewed to detect model degradation or unusual patterns (e.g., very high rejection rate suggests lighting issues; very low match rate suggests selfie quality issues).

---

## 15. Testing Strategy

### 15.1 Unit Tests

- **Detection:** Test with known images containing 0, 1, 5, and 50+ faces
- **Embedding:** Verify output is 512-d, L2-normalized, deterministic for same input
- **Quality Filter:** Test with known blurry and clear images; known frontal and profile poses
- **Clustering:** Test with synthetic embeddings (known clusters, known merges)
- **Matching:** Test with synthetic query embedding against known clusters

### 15.2 Integration Tests

- **Full pipeline:** Upload a set of test images → verify face detection → verify embedding storage in pgvector → verify clustering → verify selfie matching
- **Edge cases:** Zero-face images, corrupt images, very large images, HEIC images

### 15.3 Test Fixtures

Maintain a curated test dataset (stored in `tests/ml/fixtures/`):
- 50–100 event-style photos with known face identities
- 10–20 selfie images with known corresponding identities
- Photos with varying quality (blur, pose, lighting, occlusion)
- Expected clustering ground truth

---

*End of AI/ML Pipeline Component Document v1.0*
