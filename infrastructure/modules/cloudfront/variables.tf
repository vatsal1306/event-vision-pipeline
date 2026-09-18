variable "name_prefix" {
  description = "Prefix for named resources (distribution comment, key group, response headers policy)."
  type        = string
  default     = "platform"
}

variable "proxies_bucket_name" {
  description = "Name of the S3 bucket holding gallery WebP renditions (thumb/micro-thumb/proxy)."
  type        = string
}

variable "proxies_bucket_arn" {
  description = "ARN of the proxies bucket, for the OAC bucket policy."
  type        = string
}

variable "proxies_bucket_regional_domain_name" {
  description = "Regional domain name of the proxies bucket, used as the CloudFront origin."
  type        = string
}

variable "cloudfront_public_key_pem" {
  description = <<-EOT
    PEM-encoded RSA public key matching the private key the backend signs
    URLs with (CLOUDFRONT_PRIVATE_KEY). Generate with:
      openssl genrsa -out cloudfront-signer.pem 2048
      openssl rsa -pubout -in cloudfront-signer.pem -out cloudfront-signer-public.pem
    Only the public key goes into Terraform state; keep the private key out of
    version control and load it into the backend as a secret.
  EOT
  type        = string
}

variable "price_class" {
  description = "CloudFront price class. PriceClass_100 covers North America and Europe only; use PriceClass_200 to include Asia (India) edge locations."
  type        = string
  default     = "PriceClass_200"
}

variable "tags" {
  description = "Tags applied to all resources in this module."
  type        = map(string)
  default     = {}
}
