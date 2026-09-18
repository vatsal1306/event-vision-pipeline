output "distribution_domain_name" {
  description = "CloudFront domain (e.g. d111111abcdef8.cloudfront.net). Set as CLOUDFRONT_DOMAIN in the backend .env."
  value       = aws_cloudfront_distribution.proxies.domain_name
}

output "distribution_id" {
  description = "CloudFront distribution id, for cache invalidations and console lookup."
  value       = aws_cloudfront_distribution.proxies.id
}

output "key_pair_id" {
  description = "CloudFront public key id. Set as CLOUDFRONT_KEY_PAIR_ID in the backend .env."
  value       = aws_cloudfront_public_key.gallery_signer.id
}
