module "s3_media" {
  source = "./modules/s3"

  name_prefix                  = var.name_prefix
  cors_allowed_origins         = var.cors_allowed_origins
  originals_ia_transition_days = var.originals_ia_transition_days

  tags = merge(var.tags, {
    Environment = "shared"
    Component   = "media-storage"
  })
}

module "iam_app_user" {
  source = "./modules/iam-app-user"

  bucket_arns = values(module.s3_media.bucket_arns)

  tags = merge(var.tags, {
    Environment = "shared"
    Component   = "app-s3-access"
  })
}
