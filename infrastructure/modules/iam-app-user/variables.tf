variable "user_name" {
  description = "IAM user name for the app EC2 to access S3 media buckets."
  type        = string
  default     = "platform-app-ec2"
}

variable "bucket_arns" {
  description = "ARNs of S3 media buckets this user may access."
  type        = list(string)

  validation {
    condition     = length(var.bucket_arns) > 0
    error_message = "bucket_arns must contain at least one bucket ARN."
  }
}

variable "tags" {
  description = "Tags applied to the IAM user."
  type        = map(string)
  default     = {}
}
