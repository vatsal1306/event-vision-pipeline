variable "aws_region" {
  description = "AWS region for the Terraform state bucket and lock table."
  type        = string
  default     = "ap-south-1"
}

variable "bucket_name_prefix" {
  description = "Prefix for the S3 state bucket. Account ID is appended for global uniqueness."
  type        = string
  default     = "platform-terraform-state"
}

variable "dynamodb_table_name" {
  description = "DynamoDB table name used for Terraform state locking."
  type        = string
  default     = "terraform-locks"
}

variable "tags" {
  description = "Tags applied to bootstrap resources."
  type        = map(string)
  default = {
    Project   = "platform"
    ManagedBy = "terraform-bootstrap"
  }
}
