# SQS module — background job queues per specs/06-cloud-devops.md §4.
#
# NOTE: these queues are shared infra required by the cloud/devops spec now, but
# are NOT consumed by Module 1 (Auth/RBAC/Tower setup, the only module whose
# backend exists at the time this infra was scaffolded). They exist so Modules 3
# (Maintenance Billing -> billing_cycle jobs) and 4 (Special Collections/
# Expenditure -> report_export jobs) need zero infra changes when they land.
# Left intentionally idle/unconsumed until then.
#
# `special-collection-jobs` (added per
# specs/04-special-collections-expenditure/cloud.md "SQS / async jobs") backs
# the `special_collection` job type: async due-generation for special
# collections on towers whose active-flat count exceeds the sync threshold
# (>300 flats, same async-threshold logic as billing cycles). Module 4's
# backend is explicitly scoping that async path OUT of this round (it depends
# on Module 3 landing first) — this queue is provisioned now, ready and idle,
# so no infra change is needed when that worker logic is built.

locals {
  common_tags = merge(var.tags, {
    Environment = var.env
    ManagedBy   = "terraform"
    Project     = "aavaas"
  })

  queue_names = ["billing-cycle-jobs", "report-export-jobs", "special-collection-jobs"]
}

resource "aws_sqs_queue" "dlq" {
  for_each                  = var.enable_dlq ? toset(local.queue_names) : []
  name                      = "aavaas-${var.env}-${each.value}-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-${each.value}-dlq"
  })
}

resource "aws_sqs_queue" "this" {
  for_each                   = toset(local.queue_names)
  name                       = "aavaas-${var.env}-${each.value}"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = 345600 # 4 days

  redrive_policy = var.enable_dlq ? jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.value].arn
    maxReceiveCount     = var.max_receive_count
  }) : null

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-${each.value}"
  })
}
