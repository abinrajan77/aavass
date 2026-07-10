# S3 module — aavaas-{env}-files bucket per specs/06-cloud-devops.md §5.
# SSE-S3 (AES-256), versioning on, lifecycle -> IA after 90 days, no deletion
# (financial records retained indefinitely per PRD auditability requirement).

locals {
  common_tags = merge(var.tags, {
    Environment = var.env
    ManagedBy   = "terraform"
    Project     = "aavaas"
  })
}

resource "aws_s3_bucket" "files" {
  bucket = "aavaas-${var.env}-files"

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-files"
  })
}

resource "aws_s3_bucket_versioning" "files" {
  bucket = aws_s3_bucket.files.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "files" {
  bucket = aws_s3_bucket.files.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "files" {
  bucket = aws_s3_bucket.files.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "files" {
  bucket = aws_s3_bucket.files.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    filter {}

    transition {
      days          = var.ia_transition_days
      storage_class = "STANDARD_IA"
    }

    noncurrent_version_transition {
      noncurrent_days = var.ia_transition_days
      storage_class   = "STANDARD_IA"
    }

    # No expiration/deletion action — financial records (receipts, expenditure
    # attachments) are retained indefinitely per PRD auditability requirement.
  }
}
