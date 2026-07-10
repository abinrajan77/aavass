# S3 module — aavaas-{env}-files bucket per specs/06-cloud-devops.md §5.
# SSE-S3 (AES-256), versioning on, lifecycle -> IA after 90 days, no deletion
# (financial records retained indefinitely per PRD auditability requirement).
#
# Prefix conventions (documentation only — this bucket has a single flat
# namespace, no per-prefix Terraform resources/policies):
#   - receipts/{tower_id}/{receipt_id}.pdf                                (Module 3, reused as-is by Module 4
#                                                                          for special-collection due receipts —
#                                                                          same Receipt rows/path, differentiated
#                                                                          by the `due_type` field, not by path)
#   - expenditure-attachments/{tower_id}/{expenditure_id}/{filename}      (Module 4, per
#                                                                          specs/04-special-collections-expenditure/cloud.md)
# Both prefixes need zero bucket-level Terraform changes: same bucket, same
# encryption/versioning/lifecycle rules apply uniformly regardless of prefix.
# IAM access to the bucket is granted per ECS *service* (api, worker), not per
# prefix — see `modules/ecs-service/main.tf`'s `task_s3` policy, which grants
# `s3:GetObject`/`s3:PutObject` on `${bucket_arn}/*` (the whole bucket) and
# `s3:ListBucket` on the bucket itself. There is no existing pattern of
# per-module/per-prefix bucket-policy fragments or scoped IAM conditions
# (e.g. `s3:prefix` conditions) in this codebase to extend for Module 4 — the
# backend enforces which prefix a given pre-signed URL is issued for (per
# `06-cloud-devops.md` §5's pre-signed PUT/GET pattern), not bucket IAM.
# If per-prefix IAM scoping is ever desired, it would be added as a new
# `aws_iam_policy_document` statement (or `aws_s3_bucket_policy` resource) with
# an `s3:prefix` / resource-ARN-prefix condition in this module, consistently
# for every module's prefix at once, not just this one.

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
