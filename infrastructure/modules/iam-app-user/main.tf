locals {
  object_arns = [for arn in var.bucket_arns : "${arn}/*"]
}

resource "aws_iam_user" "app" {
  name = var.user_name

  tags = merge(var.tags, {
    Name = var.user_name
  })
}

resource "aws_iam_user_policy" "s3_media" {
  name = "s3-media-access"
  user = aws_iam_user.app.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListMediaBuckets"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = var.bucket_arns
      },
      {
        Sid    = "MediaObjectAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:AbortMultipartUpload",
          "s3:ListMultipartUploadParts",
          "s3:UploadPart",
        ]
        Resource = local.object_arns
      },
    ]
  })
}

resource "aws_iam_access_key" "app" {
  user = aws_iam_user.app.name
}
