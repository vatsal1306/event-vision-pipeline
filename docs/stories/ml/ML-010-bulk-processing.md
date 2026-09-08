# ML-010 — Bulk Upload Processing Pipeline

**Type:** Feature
**Depends on:** ML-009
**Area:** `backend/app/ml/pipeline.py`, `backend/app/tasks/face_tasks.py`

## Goal

Implement the bulk photo processing pipeline optimized for the SpotMe workflow:
photographer uploads 5,000–20,000 photos, then the system processes them all at once.
This story focuses on **efficient GPU utilization** through batching strategies.

## Processing Mode: Bulk After Upload

SpotMe uses **bulk processing** (not streaming):
1. Photographer uploads all photos (tus chunked upload)
2. Upload completion triggers face processing task
3. All photos processed in optimized batches
4. Clustering runs once after all embeddings are generated
5. Event status → `ready`

## Bulk Processing Strategy

### Phase 1: Sequential Download, Batch Embed

The key insight from pix-workers production: **don't load all full-res images into
memory at once**. A 20,000-photo event with 30MB originals = 600GB of images.

```python
async def process_event_bulk(self, event_id: UUID) -> BulkResult:
    """
    Process all unprocessed photos for an event.

    Strategy: Stream photos → detect/crop → accumulate crops → batch embed
    """
    pending_photos = await self.load_pending_photos(event_id)
    total_faces = 0
    face_crops_buffer: list[FaceCropWithMeta] = []

    for photo in pending_photos:
        # 1. Download from S3 (one at a time — memory safe)
        image_bytes = await self.s3.download(photo.original_key)
        image_bgr = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)

        # 2. Detect all faces
        detections = self.detector.detect(image_bgr)

        # 3. Crop and align
        crops = self.cropper.crop_all(image_bgr, detections)

        # 4. Quality filter each crop
        for crop in crops:
            quality = self.quality_filter.filter(crop)
            if quality.passed:
                face_crops_buffer.append(FaceCropWithMeta(
                    crop=crop, photo_id=photo.id, quality=quality
                ))

        # 5. Store detection metadata (face_count, bbox, quality scores)
        await self.store_detection_results(photo, detections, crops)
        total_faces += len(detections)

        # Release image memory
        del image_bgr, image_bytes

        # 6. When buffer reaches embedding_batch_size, flush
        if len(face_crops_buffer) >= self.config.embedding_batch_size:
            await self._flush_embedding_batch(face_crops_buffer)
            face_crops_buffer.clear()

    # Flush remaining crops
    if face_crops_buffer:
        await self._flush_embedding_batch(face_crops_buffer)

    # 7. Run full clustering pipeline
    await self.run_clustering(event_id)

    return BulkResult(
        total_photos=len(pending_photos),
        total_faces=total_faces,
        total_embedded=embedded_count,
    )
```

### Embedding Batch Flush

```python
async def _flush_embedding_batch(self, crops: list[FaceCropWithMeta]):
    """
    Batch embed accumulated crops and store in DB.

    1. Stack crop arrays into batch tensor
    2. Dual embed (R100 + AdaFace)
    3. Bulk insert into face_embeddings table
    """
    face_arrays = [c.crop.aligned_face for c in crops]

    try:
        results = self.embedder.embed_batch(face_arrays, batch_size=self.config.embedding_batch_size)
    except torch.cuda.OutOfMemoryError:
        # Retry with smaller batch
        results = self._embed_with_retry(face_arrays)

    # Bulk insert
    await self.bulk_insert_embeddings(crops, results)
```

## Memory Budget

| Component | Memory Usage | Notes |
|-----------|-------------|-------|
| 1 full-res image (30MB JPEG) | ~100–200 MB decoded | Released after cropping |
| 64 face crops (112×112×3) | ~2.4 MB | Tiny |
| R100 model | ~500 MB VRAM | Loaded once |
| AdaFace model | ~900 MB VRAM | Loaded once |
| Embedding batch (64 faces) | ~1.5 GB VRAM | Peak during forward pass |
| **Total peak VRAM** | **~3–4 GB** | Well within T4 (16GB) / A10G (24GB) |
| **Total peak RAM** | **~2–3 GB** | Plus model files |

## Performance Estimates

### Processing Speed (GPU batch=64)

| Stage | Per-Photo | 10K Photos | 20K Photos |
|-------|-----------|------------|------------|
| S3 download | ~200ms | ~33 min | ~67 min |
| SCRFD detection | ~30ms | ~5 min | ~10 min |
| Quality filter | ~5ms | ~1 min | ~2 min |
| R100 embed (batch=64) | ~1ms/face | ~4 min | ~8 min |
| AdaFace embed (batch=64) | ~2ms/face | ~7 min | ~14 min |
| DB insert (bulk) | ~0.1ms/face | ~15 sec | ~30 sec |
| Clustering | — | ~30 sec | ~1 min |
| **Total** | | **~50 min** | **~100 min** |

### Optimization: Parallel S3 Download

S3 download is the bottleneck. Use `asyncio.Semaphore` to download N photos ahead:

```python
DOWNLOAD_AHEAD = 4  # Pre-fetch 4 images while processing current

async def download_with_prefetch(self, photos):
    semaphore = asyncio.Semaphore(DOWNLOAD_AHEAD)
    async def fetch_one(photo):
        async with semaphore:
            return await self.s3.download(photo.original_key)

    tasks = [fetch_one(p) for p in photos]
    # Process as they complete
    for coro in asyncio.as_completed(tasks):
        image_bytes = await coro
        yield image_bytes
```

This can reduce total time by ~30% by overlapping download with GPU inference.

## Progress Tracking

For 20K-photo events that take ~100 minutes, the photographer needs progress feedback:

```python
# Update Redis with processing progress
await redis.hset(f"spotme:processing:{event_id}", mapping={
    "total_photos": total,
    "processed_photos": current,
    "total_faces": faces_found,
    "status": "processing",
    "started_at": started_at.isoformat(),
    "eta_seconds": estimated_remaining,
})
```

Frontend polls this for the processing status page (FE story handles display).

## Create / Edit

| File | Action |
|------|--------|
| `backend/app/ml/pipeline.py` | Edit — add `process_event_bulk()` method |
| `backend/app/tasks/face_tasks.py` | Edit — implement `process_event_photos` task body |
| `backend/app/services/s3_service.py` | Edit — add async download with prefetch |
| Integration tests | Create |

## Acceptance

- [ ] 10-photo test event processes end-to-end without crash
- [ ] Memory usage stays under 4 GB RAM during processing
- [ ] VRAM usage stays under 6 GB during batch embedding
- [ ] GPU OOM at batch=64 → automatic retry at batch=32, then batch=16
- [ ] Processing progress visible via Redis hash
- [ ] Event status transitions: uploaded → processing → ready
- [ ] Single photo failure does not abort entire event processing
- [ ] Clustering runs exactly once after all embeddings are generated
- [ ] Total processing time for 1K photos < 15 minutes (PRD target)
