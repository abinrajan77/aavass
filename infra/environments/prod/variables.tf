variable "env" {
  type    = string
  default = "prod"
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
  validation {
    condition     = var.rds_multi_az == true
    error_message = "Multi-AZ is required (not optional) in prod per specs/06-cloud-devops.md §1/§2."
  }
}

variable "rds_backup_retention_days" {
  type = number
  validation {
    condition     = var.rds_backup_retention_days >= 35
    error_message = "prod requires 35-day+ backup retention (with PITR, automatic once backups are enabled) per specs/06-cloud-devops.md §2."
  }
}

variable "rds_deletion_protection" {
  type = bool
  validation {
    condition     = var.rds_deletion_protection == true
    error_message = "Deletion protection is required in prod per specs/06-cloud-devops.md §1."
  }
}

variable "rds_enable_slow_query_logging" {
  type = bool
  validation {
    condition     = var.rds_enable_slow_query_logging == true
    error_message = "log_min_duration_statement=500ms is required in prod per specs/06-cloud-devops.md §2."
  }
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
  validation {
    condition     = var.ecs_api_desired_count >= 2
    error_message = "min 2 tasks required in prod for zero-downtime deploys per specs/06-cloud-devops.md §3."
  }
}

variable "ecs_api_min_capacity" {
  type = number
  validation {
    condition     = var.ecs_api_min_capacity >= 2
    error_message = "min 2 tasks required in prod for zero-downtime deploys per specs/06-cloud-devops.md §3."
  }
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
  validation {
    condition     = var.deployment_minimum_healthy_percent == 100
    error_message = "prod requires 100% min healthy percent per specs/06-cloud-devops.md §3."
  }
}

variable "deployment_maximum_percent" {
  type = number
  validation {
    condition     = var.deployment_maximum_percent == 200
    error_message = "prod requires 200% max percent per specs/06-cloud-devops.md §3."
  }
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
