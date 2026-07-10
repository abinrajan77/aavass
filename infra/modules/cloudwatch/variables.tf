variable "env" {
  type = string
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "sns_alarm_topic_arn" {
  description = "SNS topic ARN alarms notify. Created in this module; pass subscriptions (email/Slack) out of band."
  type        = string
  default     = null
}

# --- ALB ---
variable "alb_arn_suffix" {
  type = string
}

variable "target_group_arn_suffix" {
  type = string
}

variable "alb_p95_latency_threshold_seconds" {
  description = <<-EOT
    ALB is a single ALB-wide TargetResponseTime metric, so it cannot be split
    per route class the way specs/00-architecture-and-standards.md §4 defines
    budgets (Auth 300ms / CRUD 200ms / List 400ms / Dashboard 500ms / bulk-sync
    5s / report export 10s p95). We alarm on the tightest common-case budget
    (dashboard aggregate class, 500ms) as the default operational signal. A
    follow-up (post v1.0) would split traffic across per-route-class target
    groups for precise per-class alarms.
  EOT
  type        = number
  default     = 0.5
}

# --- ECS ---
variable "ecs_cluster_name" {
  type = string
}

variable "ecs_services" {
  description = "List of ECS service names to alarm on CPU/memory saturation."
  type        = list(string)
}

variable "ecs_cpu_threshold_percent" {
  type    = number
  default = 80
}

variable "ecs_memory_threshold_percent" {
  type    = number
  default = 80
}

# --- RDS ---
variable "rds_instance_id" {
  type = string
}

variable "rds_cpu_threshold_percent" {
  type    = number
  default = 80
}

variable "rds_connections_threshold" {
  type    = number
  default = 80
}

variable "rds_free_storage_threshold_bytes" {
  type    = number
  default = 2147483648 # 2 GiB
}

# --- SQS ---
variable "sqs_queue_names" {
  description = "Map of job_type -> queue name (not URL/ARN — CloudWatch dimensions want the queue name)."
  type        = map(string)
}

variable "sqs_queue_depth_threshold" {
  type    = number
  default = 1000
}

variable "sqs_oldest_message_age_threshold_seconds" {
  type    = number
  default = 900 # 15 minutes — signals a stuck worker
}

variable "tags" {
  type    = map(string)
  default = {}
}
