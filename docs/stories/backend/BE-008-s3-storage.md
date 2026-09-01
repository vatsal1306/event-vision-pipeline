# BE-008 — S3 storage service (presign, upload, download, storage class)

**Type:** Foundation  
**Depends on:** BE-002  
**Area:** `backend/app/services/storage_service.py`

## Goal

Single service for all object storage: put/get/delete bytes, presigned GET/PUT, change storage class (STANDARD, STANDARD_IA, GLACIER_IR). Local/dev: MinIO or moto; production: AWS S3 buckets from settings.

## References

- `docs/component_backend.md` §8.3 storage tiering key prefixes
- `docs/component_infrastructure.md` §3.1–3.3
- Prefixes: `originals/{event_id}/{uuid}.ext`, `proxies/{event_id}/{uuid}.webp`, `watermarks/`, `logos/`, `selfies/{event_id}/`

## Create / edit

- Protocol/ABC `StorageService` with async methods
- `S3StorageService` via aioboto3
- `LocalStorageService` writing under `backend/.data/s3` for tests without AWS
- Presign expiry from `s3_presigned_url_expiry`
- Content-Type required on upload
- Tests with moto or tmp local backend

## Requirements

- No public-read ACLs
- Bucket names from settings (`s3_bucket_originals`, `s3_bucket_proxies`, `s3_bucket_assets`)
- Fail with `ProcessingError` / explicit storage errors including key

## Acceptance

- [ ] Round-trip upload/download in tests
- [ ] Presigned URL generated (mocked AWS)
- [ ] Keys follow documented prefixes
