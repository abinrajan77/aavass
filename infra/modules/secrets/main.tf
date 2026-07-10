# Secrets Manager module — per specs/06-cloud-devops.md §2/§3/§9 ("Credentials:
# stored in AWS Secrets Manager, injected into ECS task definitions as secrets,
# never as plain env vars, never committed") and specs/01-auth-rbac-tower-setup/
# cloud.md (JWT signing key path, quarterly rotation with a 24h dual-key grace
# window).

locals {
  common_tags = merge(var.tags, {
    Environment = var.env
    ManagedBy   = "terraform"
    Project     = "aavaas"
  })
}

# --- Terraform-managed / computed secrets ----------------------------------------
# Populated automatically from other modules' outputs — no manual seeding.

resource "aws_secretsmanager_secret" "db_url" {
  name        = "aavaas/${var.env}/db-url"
  description = "Full SQLAlchemy async DSN for the ${var.env} RDS instance. Composed by Terraform from the rds module output + the manually-seeded master password; not manually edited."

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-db-url"
  })
}

resource "aws_secretsmanager_secret_version" "db_url" {
  secret_id     = aws_secretsmanager_secret.db_url.id
  secret_string = var.db_url
}

resource "aws_secretsmanager_secret" "s3_bucket_name" {
  name        = "aavaas/${var.env}/s3-bucket-name"
  description = "Name of the aavaas-${var.env}-files S3 bucket, referenced by ECS task definitions."

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-s3-bucket-name"
  })
}

resource "aws_secretsmanager_secret_version" "s3_bucket_name" {
  secret_id     = aws_secretsmanager_secret.s3_bucket_name.id
  secret_string = var.s3_bucket_name
}

resource "aws_secretsmanager_secret" "sqs_queue_urls" {
  name        = "aavaas/${var.env}/sqs-queue-urls"
  description = "JSON map of job_type -> SQS queue URL (billing_cycle, report_export), referenced by ECS task definitions."

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-sqs-queue-urls"
  })
}

resource "aws_secretsmanager_secret_version" "sqs_queue_urls" {
  secret_id     = aws_secretsmanager_secret.sqs_queue_urls.id
  secret_string = jsonencode(var.sqs_queue_urls)
}
