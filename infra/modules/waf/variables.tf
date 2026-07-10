variable "env" {
  type = string
}

variable "alb_arn" {
  description = "ARN of the ALB to associate this Web ACL with (REGIONAL scope)."
  type        = string
}

variable "rate_limit_per_5min" {
  description = "Rate-limiting rule threshold: requests per 5-minute window per client IP."
  type        = number
  default     = 2000
}

variable "tags" {
  type    = map(string)
  default = {}
}
