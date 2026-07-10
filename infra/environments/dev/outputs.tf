output "alb_dns_name" {
  value = module.alb.alb_dns_name
}

output "rds_endpoint" {
  value = module.rds.db_instance_endpoint
}

output "s3_bucket_name" {
  value = module.s3.bucket_name
}

output "sqs_queue_urls" {
  value = module.sqs.queue_urls
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}
