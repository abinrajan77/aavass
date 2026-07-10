variable "env" {
  type    = string
  default = "dev"
}

variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

# --- VPC ---
variable "vpc_cidr_block" {
  type = string
}

variable "az_count" {
  type    = number
  default = 2
}

variable "single_nat_gateway" {
  type    = bool
  default = true
}

# --- RDS ---
variable "rds_instance_class" {
  type = string
}

variable "rds_allocated_storage" {
  type    = number
  default = 20
}

variable "rds_multi_az" {
  type = bool
}

variable "rds_backup_retention_days" {
  type = number
}

variable "rds_deletion_protection" {
  type = bool
}

variable "rds_enable_slow_query_logging" {
  type = bool
}

variable "rds_master_username" {
  type    = string
  default = "aavaas_admin"
}

# --- ECS: API service ---
variable "ecs_api_image" {
  description = "Placeholder ECR image URI at scaffold time; CI updates this via a new task definition revision on deploy."
  type        = string
}

variable "ecs_api_cpu" {
  type    = number
  default = 512
}

variable "ecs_api_memory" {
  type    = number
  default = 1024
}

variable "ecs_api_desired_count" {
  type = number
}

variable "ecs_api_min_capacity" {
  type = number
}

variable "ecs_api_max_capacity" {
  type = number
}

# --- ECS: worker service ---
variable "ecs_worker_image" {
  type = string
}

variable "ecs_worker_cpu" {
  type    = number
  default = 512
}

variable "ecs_worker_memory" {
  type    = number
  default = 1024
}

variable "ecs_worker_desired_count" {
  type = number
}

variable "ecs_worker_min_capacity" {
  type = number
}

variable "ecs_worker_max_capacity" {
  type = number
}

variable "deployment_minimum_healthy_percent" {
  type = number
}

variable "deployment_maximum_percent" {
  type = number
}

# --- ALB / WAF ---
variable "certificate_arn" {
  description = "PLACEHOLDER — replace with a real, validated ACM certificate ARN before any real apply."
  type        = string
}

variable "waf_rate_limit_per_5min" {
  type    = number
  default = 2000
}

# --- CloudWatch ---
variable "log_retention_days" {
  type    = number
  default = 30
}

variable "sns_alarm_email" {
  description = "Optional email to subscribe to the alarm SNS topic. Left unset (null) at scaffold time — subscribing requires manual confirmation anyway, so wire this out-of-band or via a follow-up apply."
  type        = string
  default     = null
}
