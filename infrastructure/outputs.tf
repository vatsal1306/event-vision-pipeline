output "bucket_names" {
  description = "Map of logical bucket role to bucket name."
  value       = module.s3_media.bucket_names
}

output "originals_bucket_name" {
  description = "S3 bucket for full-resolution uploads."
  value       = module.s3_media.originals_bucket_name
}

output "proxies_bucket_name" {
  description = "S3 bucket for watermarked WebP gallery images."
  value       = module.s3_media.proxies_bucket_name
}

output "assets_bucket_name" {
  description = "S3 bucket for logos, watermarks, and static assets."
  value       = module.s3_media.assets_bucket_name
}

output "postgres_backup_prefix" {
  description = "S3 key prefix for daily Postgres dumps (INF-007). Lives in the originals bucket."
  value       = "backups/pg/"
}

output "iam_app_user_name" {
  description = "IAM user that the app EC2 uses to access S3."
  value       = module.iam_app_user.user_name
}

output "app_env_file_snippet" {
  description = "Lines to paste into /opt/platform/.env on the app EC2. Contains secrets."
  sensitive   = true
  value       = <<-EOT
    AWS_ACCESS_KEY_ID=${module.iam_app_user.access_key_id}
    AWS_SECRET_ACCESS_KEY=${module.iam_app_user.secret_access_key}
    AWS_REGION=ap-south-1
    S3_BUCKET_ORIGINALS=${module.s3_media.originals_bucket_name}
    S3_BUCKET_PROXIES=${module.s3_media.proxies_bucket_name}
    S3_BUCKET_ASSETS=${module.s3_media.assets_bucket_name}
  EOT
}
