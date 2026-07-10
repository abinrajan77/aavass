variable "env" {
  type = string
}

variable "enable_dlq" {
  description = "Attach a dead-letter queue with a redrive policy to each queue."
  type        = bool
  default     = true
}

variable "max_receive_count" {
  description = "Number of deliveries before a message is sent to the DLQ."
  type        = number
  default     = 5
}

variable "visibility_timeout_seconds" {
  description = "Should exceed the worker's expected max processing time for a billing-cycle/report-export/special-collection job."
  type        = number
  default     = 300
}

variable "tags" {
  type    = map(string)
  default = {}
}
