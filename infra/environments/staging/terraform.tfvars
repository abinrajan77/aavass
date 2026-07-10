env        = "staging"
aws_region = "ap-south-1"

# --- VPC ---
vpc_cidr_block     = "10.20.0.0/16"
az_count           = 2
single_nat_gateway = true

# --- RDS: db.t4g.small, single-AZ by default (Multi-AZ optional/parameterized),
# 7-day backups per 06-cloud-devops.md §1/§2 ---
rds_instance_class            = "db.t4g.small"
rds_allocated_storage         = 20
rds_multi_az                  = false # optional in staging — flip to true to mirror prod more closely
rds_backup_retention_days     = 7
rds_deletion_protection       = false
rds_enable_slow_query_logging = false # not required in staging, only prod

# --- ECS: min 1 task in dev/staging per 06-cloud-devops.md §3 ---
ecs_api_image    = "PLACEHOLDER_ECR_IMAGE_URI/aavaas-api:latest"
ecs_worker_image = "PLACEHOLDER_ECR_IMAGE_URI/aavaas-worker:latest"

ecs_api_desired_count = 1
ecs_api_min_capacity  = 1
ecs_api_max_capacity  = 4

ecs_worker_desired_count = 1
ecs_worker_min_capacity  = 1
ecs_worker_max_capacity  = 3

deployment_minimum_healthy_percent = 100
deployment_maximum_percent         = 200

# --- ALB / WAF ---
# PLACEHOLDER — replace with a real, DNS-validated ACM certificate ARN for
# staging.aavaas.app before any real apply.
certificate_arn         = "arn:aws:acm:ap-south-1:000000000000:certificate/PLACEHOLDER"
waf_rate_limit_per_5min = 2000

# --- CloudWatch ---
log_retention_days = 30
