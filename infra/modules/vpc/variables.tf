variable "env" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "cidr_block" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "az_count" {
  description = "Number of availability zones to spread subnets across"
  type        = number
  default     = 2
}

variable "single_nat_gateway" {
  description = "Use a single shared NAT gateway (cheaper, less HA) instead of one per AZ. Recommended true for dev/staging, false for prod."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Common tags applied to all resources in this module"
  type        = map(string)
  default     = {}
}
