# CloudFront in front of the proxies bucket, replacing direct S3 presigned
# URLs for gallery images. The bucket stays private; only this distribution
# (via Origin Access Control) may read it. Guest/master gallery clients get a
# CloudFront edge close to them instead of a single `ap-south-1` round trip,
# and repeat views of the same photo across different guests can hit the edge
# cache instead of S3 origin.

resource "aws_cloudfront_origin_access_control" "proxies" {
  name                              = "${var.name_prefix}-proxies-oac"
  description                       = "Locks the proxies bucket to this CloudFront distribution."
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_public_key" "gallery_signer" {
  name        = "${var.name_prefix}-gallery-signer"
  comment     = "Public half of the RSA key the backend uses to sign gallery URLs (cloudfront_signer.py)."
  encoded_key = var.cloudfront_public_key_pem
}

resource "aws_cloudfront_key_group" "gallery_signer" {
  name    = "${var.name_prefix}-gallery-signer"
  comment = "Trusted key group for signed gallery URLs."
  items   = [aws_cloudfront_public_key.gallery_signer.id]
}

# S3-specific response overrides (ResponseContentType/ResponseCacheControl)
# used by direct S3 presigning have no CloudFront equivalent, so the
# equivalent headers are set once here at the distribution level instead.
resource "aws_cloudfront_response_headers_policy" "gallery_images" {
  name = "${var.name_prefix}-gallery-images"

  custom_headers_config {
    items {
      header   = "Cache-Control"
      value    = "private, max-age=3600, immutable"
      override = false
    }
  }
}

resource "aws_cloudfront_cache_policy" "gallery_images" {
  name        = "${var.name_prefix}-gallery-images"
  comment     = "Signed gallery image URLs; cache key is the full URL including query string."
  default_ttl = 3600
  max_ttl     = 7200
  min_ttl     = 0

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      # Signed-URL query params (Policy/Signature/Key-Pair-Id or
      # Expires/Signature/Key-Pair-Id) are part of what CloudFront verifies at
      # the edge; including them in the cache key means a URL re-signed with
      # the same bucketed expiry (see cloudfront_signer.py) reuses the cache.
      query_string_behavior = "all"
    }
    enable_accept_encoding_brotli = true
    enable_accept_encoding_gzip   = true
  }
}

resource "aws_cloudfront_distribution" "proxies" {
  comment         = "${var.name_prefix} gallery images (proxies bucket)"
  enabled         = true
  is_ipv6_enabled = true
  price_class     = var.price_class

  origin {
    domain_name              = var.proxies_bucket_regional_domain_name
    origin_id                = "proxies-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.proxies.id
  }

  default_cache_behavior {
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    target_origin_id           = "proxies-s3"
    viewer_protocol_policy     = "redirect-to-https"
    cache_policy_id            = aws_cloudfront_cache_policy.gallery_images.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.gallery_images.id
    compress                   = true

    trusted_key_groups = [aws_cloudfront_key_group.gallery_signer.id]
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = var.tags
}

# Only this distribution's OAC principal may read the bucket. The bucket is
# already fully public-access-blocked (modules/s3/main.tf), so this is
# additive — it does not loosen anything.
data "aws_iam_policy_document" "proxies_oac" {
  statement {
    sid     = "AllowCloudFrontServicePrincipalReadOnly"
    effect  = "Allow"
    actions = ["s3:GetObject"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    resources = ["${var.proxies_bucket_arn}/*"]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.proxies.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "proxies_oac" {
  bucket = var.proxies_bucket_name
  policy = data.aws_iam_policy_document.proxies_oac.json
}
