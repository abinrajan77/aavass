output "queue_urls" {
  description = "Map of job_type (billing_cycle, report_export, special_collection) -> queue URL."
  value = {
    billing_cycle      = aws_sqs_queue.this["billing-cycle-jobs"].url
    report_export      = aws_sqs_queue.this["report-export-jobs"].url
    special_collection = aws_sqs_queue.this["special-collection-jobs"].url
  }
}

output "queue_arns" {
  description = "Map of job_type -> queue ARN, for IAM policy scoping in ecs-service task roles."
  value = {
    billing_cycle      = aws_sqs_queue.this["billing-cycle-jobs"].arn
    report_export      = aws_sqs_queue.this["report-export-jobs"].arn
    special_collection = aws_sqs_queue.this["special-collection-jobs"].arn
  }
}
