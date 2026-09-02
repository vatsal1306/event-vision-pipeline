data "aws_caller_identity" "current" {}

locals {
  account_suffix = data.aws_caller_identity.current.account_id

  bucket_names = {
    originals = "${var.name_prefix}-originals-${local.account_suffix}"
    proxies   = "${var.name_prefix}-proxies-${local.account_suffix}"
    assets    = "${var.name_prefix}-assets-${local.account_suffix}"
  }

  # tusd uploads server-side (browser → EC2 → S3). CORS is still required when the
  # frontend fetch()s presigned proxy/original URLs (PWA service worker, download flows).
  cors_configuration = {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "HEAD", "POST", "DELETE"]
    allowed_origins = var.cors_allowed_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}

resource "aws_s3_bucket" "media" {
  for_each = local.bucket_names

  bucket = each.value

  tags = merge(var.tags, {
    Name    = each.value
    Purpose = each.key
  })
}

resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  for_each = aws_s3_bucket.media

  bucket = each.value.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "media" {
  for_each = aws_s3_bucket.media

  bucket = each.value.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_cors_configuration" "browser_facing" {
  for_each = {
    for name, bucket in aws_s3_bucket.media : name => bucket
    if contains(["originals", "proxies"], name)
  }

  bucket = each.value.id

  cors_rule {
    allowed_headers = local.cors_configuration.allowed_headers
    allowed_methods = local.cors_configuration.allowed_methods
    allowed_origins = local.cors_configuration.allowed_origins
    expose_headers  = local.cors_configuration.expose_headers
    max_age_seconds = local.cors_configuration.max_age_seconds
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "originals" {
  bucket = aws_s3_bucket.media["originals"].id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    filter {}

    transition {
      days          = var.originals_ia_transition_days
      storage_class = "STANDARD_IA"
    }
  }

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
