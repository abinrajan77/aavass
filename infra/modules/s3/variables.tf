variable "env" {
  type = string
}

variable "ia_transition_days" {
  description = "Days before transitioning to Infrequent Access. Per specs/06-cloud-devops.md §5: 90 days, no deletion."
  type        = number
  default     = 90
}

variable "tags" {
  type    = map(string)
  default = {}
}
