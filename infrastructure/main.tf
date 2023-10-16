provider "aws" {
  region = var.REGION
}

data "aws_caller_identity" "current" {}

################################################################################
# Secret manager
################################################################################
resource "aws_secretsmanager_secret" "acme_secrets" {
  name = var.SECRET_MANAGER_ID
}
data "aws_secretsmanager_secret_version" "acme_secrets_data" {
  secret_id = aws_secretsmanager_secret.acme_secrets.id
}
