env        = "prod"
aws_region = "ap-south-1"

# --- VPC --- prod uses one NAT gateway per AZ for HA (no single point of failure
# on egress) per the cost/scale baseline in 06-cloud-devops.md §10 being a
# "starting point, not a hard ceiling."
vpc_cidr_block     = "10.30.0.0/16"
az_count           = 2
single_nat_gateway = false

# --- RDS: db.r6g.large, Multi-AZ REQUIRED, 35-day backups + PITR, deletion
# protection on, slow-query logging on per 06-cloud-devops.md §1/§2 ---
rds_instance_class            = "db.r6g.large"
rds_allocated_storage         = 100
rds_multi_az                  = true
rds_backup_retention_days     = 35
rds_deletion_protection       = true
rds_enable_slow_query_logging = true

# --- ECS: min 2 tasks in prod for zero-downtime deploys per 06-cloud-devops.md §3 ---
ecs_api_image    = "PLACEHOLDER_ECR_IMAGE_URI/aavaas-api:latest"
ecs_worker_image = "PLACEHOLDER_ECR_IMAGE_URI/aavaas-worker:latest"

ecs_api_desired_count = 2
ecs_api_min_capacity  = 2
ecs_api_max_capacity  = 10

ecs_worker_desired_count = 2
ecs_worker_min_capacity  = 2
ecs_worker_max_capacity  = 6

# Rolling deploy, 100/200 min/max healthy percent in prod per 06-cloud-devops.md §3.
deployment_minimum_healthy_percent = 100
deployment_maximum_percent         = 200

# --- ALB / WAF ---
# PLACEHOLDER — replace with a real, DNS-validated ACM certificate ARN for
# app.aavaas.app before any real apply.
certificate_arn         = "arn:aws:acm:ap-south-1:000000000000:certificate/PLACEHOLDER"
waf_rate_limit_per_5min = 1000 # tighter than dev/staging for the production surface

# --- CloudWatch ---
log_retention_days = 90
