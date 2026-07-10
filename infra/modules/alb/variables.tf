variable "env" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "certificate_arn" {
  description = "ACM certificate ARN for the HTTPS listener. PLACEHOLDER value in environments/*/terraform.tfvars — must be replaced with a real, validated ACM cert ARN before any real apply."
  type        = string
}

variable "health_check_path" {
  type    = string
  default = "/healthz"
}

variable "tags" {
  type    = map(string)
  default = {}
}
