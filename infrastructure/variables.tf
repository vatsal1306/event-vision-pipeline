variable "name_prefix" {
  description = "Prefix for S3 bucket names. Account ID is appended for global uniqueness."
  type        = string
  default     = "platform"
}

variable "cors_allowed_origins" {
  description = <<-EOT
    Browser origins for S3 CORS on originals and proxies buckets.
    Include production domain, dev/staging domain, and localhost for local dev against real S3.
  EOT
  type        = list(string)
}

variable "originals_ia_transition_days" {
  description = "Days before originals transition to STANDARD_IA. Default 7 keeps originals on Standard during the active event window."
  type        = number
  default     = 7
}

variable "tags" {
  description = "Tags applied to all resources in this stack."
  type        = map(string)
  default = {
    Project   = "platform"
    ManagedBy = "terraform"
  }
}

variable "cloudfront_public_key_pem" {
  description = <<-EOT
    PEM-encoded RSA public key for signing gallery URLs through CloudFront.
    Leave blank (the default) to skip creating the CloudFront distribution
    entirely — e.g. before the key pair exists, or while still on direct S3
    presigning. Generate with:
      openssl genrsa -out cloudfront-signer.pem 2048
      openssl rsa -pubout -in cloudfront-signer.pem -out cloudfront-signer-public.pem
    Pass the *public* key's contents here; keep the private key out of
    Terraform and version control, and load it into the backend's
    CLOUDFRONT_PRIVATE_KEY instead.
  EOT
  type        = string
  default     = ""
  sensitive   = false
}
