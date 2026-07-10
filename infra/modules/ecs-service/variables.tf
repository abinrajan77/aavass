# Generic ECS/Fargate service module — used for both the FastAPI API service
# (behind the ALB) and the SQS worker service (no ALB attachment) per
# specs/06-cloud-devops.md §3/§4.

variable "env" {
  type = string
}

variable "service_name" {
  description = "e.g. \"api\" or \"worker\" — used in resource names and log group paths."
  type        = string
}

variable "cluster_id" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "ingress_security_group_ids" {
  description = "Security groups allowed to reach this service's container_port (typically the ALB SG for the API service; empty for the worker, which has no inbound listener)."
  type        = list(string)
  default     = []
}

variable "image" {
  description = "Full ECR image URI:tag. Placeholder at scaffold time — set by CI on deploy."
  type        = string
}

variable "container_port" {
  description = "Set to null for services with no inbound listener (e.g. the SQS worker)."
  type        = number
  default     = null
}

variable "cpu" {
  type    = number
  default = 512
}

variable "memory" {
  type    = number
  default = 1024
}

variable "desired_count" {
  description = "min 2 in prod (zero-downtime deploys), min 1 in dev/staging per specs/06-cloud-devops.md §3."
  type        = number
}

variable "min_capacity" {
  type = number
}

variable "max_capacity" {
  type = number
}

variable "cpu_target_value" {
  description = "Target-tracking CPU % per specs/06-cloud-devops.md §3."
  type        = number
  default     = 60
}

variable "enable_alb" {
  description = "Attach this service to an ALB target group and enable ALB-request-count-based autoscaling. True for the api service, false for the worker."
  type        = bool
  default     = false
}

variable "target_group_arn" {
  type    = string
  default = null
}

variable "alb_arn_suffix" {
  description = "Required only when enable_alb=true, for the ALBRequestCountPerTarget predefined autoscaling metric."
  type        = string
  default     = ""
}

variable "target_group_arn_suffix" {
  type    = string
  default = ""
}

variable "requests_per_target_value" {
  description = "Target requests-per-target for ALB request-count-based autoscaling."
  type        = number
  default     = 1000
}

variable "deployment_minimum_healthy_percent" {
  description = "100 in prod, 100 (default OK) in dev/staging per specs/06-cloud-devops.md §3."
  type        = number
  default     = 100
}

variable "deployment_maximum_percent" {
  description = "200 in prod per specs/06-cloud-devops.md §3."
  type        = number
  default     = 200
}

variable "environment_variables" {
  description = "Plain (non-sensitive) env vars, e.g. ENVIRONMENT, AWS_REGION, LOG_LEVEL."
  type        = list(object({ name = string, value = string }))
  default     = []
}

variable "secrets" {
  description = "ECS task-def secrets blocks: [{ name = \"DATABASE_URL\", value_from = secretArn }, ...]. Never pass sensitive values as plain environment_variables."
  type        = list(object({ name = string, value_from = string }))
  default     = []
}

variable "secret_arns_for_execution_role" {
  description = "ARNs the task execution role needs secretsmanager:GetSecretValue on (usually the same ARNs referenced in var.secrets, deduplicated)."
  type        = list(string)
  default     = []
}

variable "s3_bucket_arn" {
  description = "Bucket ARN this service's task role may read/write its prefixes on. Empty string to grant none."
  type        = string
  default     = ""
}

variable "sqs_queue_arns" {
  description = "SQS queue ARNs this service's task role may send/receive/delete on. Empty list to grant none."
  type        = list(string)
  default     = []
}

variable "log_group_name" {
  description = "CloudWatch log group name created by the cloudwatch module (e.g. /aavaas/{env}/api) — ecs-service does not create its own log groups so all log-group lifecycle/retention lives in one place."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
