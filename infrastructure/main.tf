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

module "cloudfront" {
  count  = var.cloudfront_public_key_pem == "" ? 0 : 1
  source = "./modules/cloudfront"

  name_prefix                         = var.name_prefix
  proxies_bucket_name                 = module.s3_media.bucket_names["proxies"]
  proxies_bucket_arn                  = module.s3_media.bucket_arns["proxies"]
  proxies_bucket_regional_domain_name = module.s3_media.bucket_regional_domain_names["proxies"]
  cloudfront_public_key_pem           = var.cloudfront_public_key_pem

  tags = merge(var.tags, {
    Environment = "shared"
    Component   = "gallery-cdn"
  })
}
