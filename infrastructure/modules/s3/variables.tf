variable "name_prefix" {
  description = "Prefix for S3 bucket names. Account ID is appended for global uniqueness."
  type        = string
  default     = "platform"
}

variable "cors_allowed_origins" {
  description = "Browser origins allowed for S3 CORS (tus is server-side; needed for presigned GET via fetch/service worker)."
  type        = list(string)
}

variable "originals_ia_transition_days" {
  description = "Days after upload before originals transition from STANDARD to STANDARD_IA."
  type        = number
  default     = 7

  validation {
    condition     = var.originals_ia_transition_days >= 1
    error_message = "originals_ia_transition_days must be at least 1."
  }
}

variable "tags" {
  description = "Tags applied to all S3 buckets."
  type        = map(string)
  default     = {}
}
