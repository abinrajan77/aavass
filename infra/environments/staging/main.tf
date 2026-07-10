terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # TODO: replace with S3+DynamoDB remote state backend before first real deploy.
  # This scaffold intentionally uses local state (no `backend` block = local).
  # Example of the intended future backend:
  # backend "s3" {
  #   bucket         = "aavaas-terraform-state"
  #   key            = "staging/terraform.tfstate"
  #   region         = "ap-south-1"
  #   dynamodb_table = "aavaas-terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "aavaas"
      Environment = var.env
      ManagedBy   = "terraform"
    }
  }
}

locals {
  tags = {
    Project     = "aavaas"
    Environment = var.env
  }
}

# --- Manually-seeded secrets (must exist before first apply — see README) --------

data "aws_secretsmanager_secret" "rds_master_password" {
  name = "aavaas/${var.env}/rds-master-password"
}

data "aws_secretsmanager_secret_version" "rds_master_password" {
  secret_id = data.aws_secretsmanager_secret.rds_master_password.id
}

data "aws_secretsmanager_secret" "jwt_signing_key" {
  name = "aavaas/${var.env}/jwt-signing-key"
}

# --- Networking -------------------------------------------------------------------

module "vpc" {
  source = "../../modules/vpc"

  env                = var.env
  cidr_block         = var.vpc_cidr_block
  az_count           = var.az_count
  single_nat_gateway = var.single_nat_gateway
  tags               = local.tags
}

# --- Storage / messaging -----------------------------------------------------------

module "s3" {
  source = "../../modules/s3"

  env  = var.env
  tags = local.tags
}

module "sqs" {
  source = "../../modules/sqs"

  env  = var.env
  tags = local.tags
}

# --- Database -----------------------------------------------------------------------

module "rds" {
  source = "../../modules/rds"

  env                       = var.env
  vpc_id                    = module.vpc.vpc_id
  private_subnet_ids        = module.vpc.private_subnet_ids
  allowed_cidr_blocks       = module.vpc.private_subnet_cidrs
  instance_class            = var.rds_instance_class
  allocated_storage         = var.rds_allocated_storage
  multi_az                  = var.rds_multi_az
  backup_retention_days     = var.rds_backup_retention_days
  deletion_protection       = var.rds_deletion_protection
  enable_slow_query_logging = var.rds_enable_slow_query_logging
  master_username           = var.rds_master_username
  master_password           = data.aws_secretsmanager_secret_version.rds_master_password.secret_string
  tags                      = local.tags
}

# --- Secrets Manager (computed secrets) ---------------------------------------------

module "secrets" {
  source = "../../modules/secrets"

  env            = var.env
  db_url         = "postgresql+asyncpg://${var.rds_master_username}:${urlencode(data.aws_secretsmanager_secret_version.rds_master_password.secret_string)}@${module.rds.db_instance_address}:${module.rds.db_instance_port}/${module.rds.db_name}"
  s3_bucket_name = module.s3.bucket_name
  sqs_queue_urls = module.sqs.queue_urls
  tags           = local.tags
}

# --- Load balancing / edge security -------------------------------------------------

module "alb" {
  source = "../../modules/alb"

  env               = var.env
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
  certificate_arn   = var.certificate_arn
  tags              = local.tags
}

module "waf" {
  source = "../../modules/waf"

  env                 = var.env
  alb_arn             = module.alb.alb_arn
  rate_limit_per_5min = var.waf_rate_limit_per_5min
  tags                = local.tags
}

# --- Compute --------------------------------------------------------------------------

resource "aws_ecs_cluster" "this" {
  name = "aavaas-${var.env}-cluster"
  tags = local.tags
}

module "cloudwatch" {
  source = "../../modules/cloudwatch"

  env                     = var.env
  log_retention_days      = var.log_retention_days
  alb_arn_suffix          = module.alb.alb_arn_suffix
  target_group_arn_suffix = module.alb.api_target_group_arn_suffix
  ecs_cluster_name        = aws_ecs_cluster.this.name
  ecs_services            = ["aavaas-${var.env}-api", "aavaas-${var.env}-worker"]
  rds_instance_id         = module.rds.db_instance_id
  sqs_queue_names         = { billing_cycle = "aavaas-${var.env}-billing-cycle-jobs", report_export = "aavaas-${var.env}-report-export-jobs", special_collection = "aavaas-${var.env}-special-collection-jobs" }
  tags                    = local.tags
}

module "ecs_api" {
  source = "../../modules/ecs-service"

  env                                = var.env
  service_name                       = "api"
  cluster_id                         = aws_ecs_cluster.this.id
  cluster_name                       = aws_ecs_cluster.this.name
  vpc_id                             = module.vpc.vpc_id
  private_subnet_ids                 = module.vpc.private_subnet_ids
  ingress_security_group_ids         = [module.alb.security_group_id]
  image                              = var.ecs_api_image
  container_port                     = 8000
  cpu                                = var.ecs_api_cpu
  memory                             = var.ecs_api_memory
  desired_count                      = var.ecs_api_desired_count
  min_capacity                       = var.ecs_api_min_capacity
  max_capacity                       = var.ecs_api_max_capacity
  enable_alb                         = true
  target_group_arn                   = module.alb.api_target_group_arn
  alb_arn_suffix                     = module.alb.alb_arn_suffix
  target_group_arn_suffix            = module.alb.api_target_group_arn_suffix
  deployment_minimum_healthy_percent = var.deployment_minimum_healthy_percent
  deployment_maximum_percent         = var.deployment_maximum_percent
  log_group_name                     = module.cloudwatch.api_log_group_name

  environment_variables = [
    { name = "ENVIRONMENT", value = var.env },
    { name = "AWS_REGION", value = var.aws_region },
  ]

  secrets = [
    { name = "DATABASE_URL", value_from = module.secrets.db_url_arn },
    { name = "JWT_SIGNING_KEY", value_from = data.aws_secretsmanager_secret.jwt_signing_key.arn },
    { name = "S3_BUCKET_NAME", value_from = module.secrets.s3_bucket_name_secret_arn },
    { name = "SQS_QUEUE_URLS", value_from = module.secrets.sqs_queue_urls_secret_arn },
  ]

  secret_arns_for_execution_role = [
    module.secrets.db_url_arn,
    data.aws_secretsmanager_secret.jwt_signing_key.arn,
    module.secrets.s3_bucket_name_secret_arn,
    module.secrets.sqs_queue_urls_secret_arn,
  ]

  s3_bucket_arn  = module.s3.bucket_arn
  sqs_queue_arns = values(module.sqs.queue_arns)
  tags           = local.tags
}

module "ecs_worker" {
  source = "../../modules/ecs-service"

  env                                = var.env
  service_name                       = "worker"
  cluster_id                         = aws_ecs_cluster.this.id
  cluster_name                       = aws_ecs_cluster.this.name
  vpc_id                             = module.vpc.vpc_id
  private_subnet_ids                 = module.vpc.private_subnet_ids
  ingress_security_group_ids         = []
  image                              = var.ecs_worker_image
  container_port                     = null
  cpu                                = var.ecs_worker_cpu
  memory                             = var.ecs_worker_memory
  desired_count                      = var.ecs_worker_desired_count
  min_capacity                       = var.ecs_worker_min_capacity
  max_capacity                       = var.ecs_worker_max_capacity
  enable_alb                         = false
  deployment_minimum_healthy_percent = var.deployment_minimum_healthy_percent
  deployment_maximum_percent         = var.deployment_maximum_percent
  log_group_name                     = module.cloudwatch.worker_log_group_name

  environment_variables = [
    { name = "ENVIRONMENT", value = var.env },
    { name = "AWS_REGION", value = var.aws_region },
  ]

  secrets = [
    { name = "DATABASE_URL", value_from = module.secrets.db_url_arn },
    { name = "S3_BUCKET_NAME", value_from = module.secrets.s3_bucket_name_secret_arn },
    { name = "SQS_QUEUE_URLS", value_from = module.secrets.sqs_queue_urls_secret_arn },
  ]

  secret_arns_for_execution_role = [
    module.secrets.db_url_arn,
    module.secrets.s3_bucket_name_secret_arn,
    module.secrets.sqs_queue_urls_secret_arn,
  ]

  s3_bucket_arn  = module.s3.bucket_arn
  sqs_queue_arns = values(module.sqs.queue_arns)
  tags           = local.tags
}
