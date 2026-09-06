terraform {
  backend "s3" {
    # Values are supplied at init time:
    #   terraform init -backend-config=environments/<env>/backend.hcl
  }
}
