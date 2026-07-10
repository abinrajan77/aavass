variable "env" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to connect to RDS on 5432 — the private subnet CIDRs, since only ECS tasks (and RDS itself) live there. Using CIDR-based ingress rather than a security-group reference to the ecs-service module's task SGs avoids a module dependency cycle (rds -> ecs-service -> secrets -> rds via the DB URL secret)."
  type        = list(string)
}

variable "instance_class" {
  description = "e.g. db.t4g.micro (dev), db.t4g.small (staging), db.r6g.large (prod)"
  type        = string
}

variable "allocated_storage" {
  type    = number
  default = 20
}

variable "max_allocated_storage" {
  description = "Upper bound for RDS storage autoscaling."
  type        = number
  default     = 100
}

variable "multi_az" {
  type = bool
}

variable "backup_retention_days" {
  description = "7 for dev/staging, 35 for prod per specs/06-cloud-devops.md §2."
  type        = number
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "enable_slow_query_logging" {
  description = "Sets log_min_duration_statement=500ms. Required true in prod per specs/06-cloud-devops.md §2."
  type        = bool
  default     = false
}

variable "master_username" {
  type    = string
  default = "aavaas_admin"
}

variable "master_password" {
  description = "Manually-seeded master password, sourced from the secrets module (Secrets Manager) — never a plain tfvars value."
  type        = string
  sensitive   = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
