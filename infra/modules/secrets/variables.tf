variable "env" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

# NOTE: the two manually-seeded secrets (aavaas/{env}/rds-master-password and
# aavaas/{env}/jwt-signing-key) are intentionally NOT managed by this module.
# They must exist in Secrets Manager *before* the first `terraform apply`
# (created out-of-band per infra/README.md) so that other modules (rds) can
# consume the master password without this module creating a circular
# dependency on the rds module's own outputs. The environment root reads them
# directly via `data "aws_secretsmanager_secret_version"` and threads the
# values into module.rds / the ecs-service secrets blocks itself.

# --- Terraform-managed / computed secrets ---------------------------------------
# Values Terraform itself derives from other module outputs (RDS endpoint, S3
# bucket name, SQS queue URLs) once those resources exist. No manual seeding
# required for these.
variable "db_url" {
  description = "Fully-composed SQLAlchemy async DSN, built by the environment root module from the rds module's outputs and the manually-seeded master password."
  type        = string
  sensitive   = true
}

variable "s3_bucket_name" {
  description = "aavaas-{env}-files bucket name, from the s3 module output."
  type        = string
}

variable "sqs_queue_urls" {
  description = "Map of job-type -> SQS queue URL, from the sqs module output."
  type        = map(string)
}

variable "tags" {
  type    = map(string)
  default = {}
}
