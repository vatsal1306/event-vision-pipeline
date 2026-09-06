# Event Vision Pipeline - Backend

This is the FastAPI backend for the AI Photo Sharing Platform.

## Components

### 1. Upload Pipeline (`UploadService`)
Handles webhooks from `tusd` when an original photo upload is completed directly to S3. Validates MIME type, sizes, event/photographer authorization, and handles S3 storage quota tracking. Enqueues the processing tasks via Celery.

### 2. Dual-Resolution & Processing Engine (`ImageProcessingService` / `WatermarkService`)
A Celery task (`process_uploaded_photo`) downloads the original from S3 and:
- Applies EXIF transpose (rotation fixes).
- Converts HEIC/HEIF images seamlessly via `pillow-heif`.
- Generates a web-optimized WebP proxy image (max 2048px, target 500KB) and saves to the `platform-proxies` bucket.
- Applies a watermark (if the photographer has one configured) to the proxy image automatically using alpha compositing.
- Generates a `blurhash` string for ultra-fast frontend placeholder rendering.
- Converts the original image in S3 to the `STANDARD_IA` (Infrequent Access) storage class to save on storage costs.

### 3. Database
Uses PostgreSQL with `pgvector` for upcoming face recognition tasks. Interacts using `SQLAlchemy` async ORM (`asyncpg`).
