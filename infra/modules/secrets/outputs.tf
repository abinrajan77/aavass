output "db_url_arn" {
  value = aws_secretsmanager_secret.db_url.arn
}

output "s3_bucket_name_secret_arn" {
  value = aws_secretsmanager_secret.s3_bucket_name.arn
}

output "sqs_queue_urls_secret_arn" {
  value = aws_secretsmanager_secret.sqs_queue_urls.arn
}
