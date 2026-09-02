output "bucket_names" {
  description = "Map of logical bucket role to bucket name."
  value       = { for name, bucket in aws_s3_bucket.media : name => bucket.id }
}

output "bucket_arns" {
  description = "Map of logical bucket role to bucket ARN."
  value       = { for name, bucket in aws_s3_bucket.media : name => bucket.arn }
}

output "originals_bucket_name" {
  description = "S3 bucket for full-resolution photo uploads (originals/{event_id}/...)."
  value       = aws_s3_bucket.media["originals"].id
}

output "proxies_bucket_name" {
  description = "S3 bucket for watermarked WebP gallery images (proxies/{event_id}/...)."
  value       = aws_s3_bucket.media["proxies"].id
}

output "assets_bucket_name" {
  description = "S3 bucket for logos, watermarks, and other static assets."
  value       = aws_s3_bucket.media["assets"].id
}
