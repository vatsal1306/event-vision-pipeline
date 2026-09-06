output "user_name" {
  description = "IAM user name."
  value       = aws_iam_user.app.name
}

output "user_arn" {
  description = "IAM user ARN."
  value       = aws_iam_user.app.arn
}

output "access_key_id" {
  description = "AWS access key ID for the app EC2."
  value       = aws_iam_access_key.app.id
  sensitive   = true
}

output "secret_access_key" {
  description = "AWS secret access key for the app EC2. Shown once via terraform output; also stored in Terraform state."
  value       = aws_iam_access_key.app.secret
  sensitive   = true
}
