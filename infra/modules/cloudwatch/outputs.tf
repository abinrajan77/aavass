output "api_log_group_name" {
  value = aws_cloudwatch_log_group.api.name
}

output "worker_log_group_name" {
  value = aws_cloudwatch_log_group.worker.name
}

output "frontend_log_group_name" {
  value = aws_cloudwatch_log_group.frontend.name
}

output "sns_alarm_topic_arn" {
  value = local.alarm_actions
}
