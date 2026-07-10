output "alb_arn" {
  value = aws_lb.this.arn
}

output "alb_arn_suffix" {
  description = "Short form (app/name/id) used as the LoadBalancer dimension in CloudWatch alarms and as half of the ALBRequestCountPerTarget resource_label."
  value       = aws_lb.this.arn_suffix
}

output "alb_dns_name" {
  value = aws_lb.this.dns_name
}

output "alb_zone_id" {
  value = aws_lb.this.zone_id
}

output "api_target_group_arn" {
  value = aws_lb_target_group.api.arn
}

output "api_target_group_arn_suffix" {
  description = "Short form (targetgroup/name/id) used as the TargetGroup dimension in CloudWatch alarms and as half of the ALBRequestCountPerTarget resource_label."
  value       = aws_lb_target_group.api.arn_suffix
}

output "security_group_id" {
  value = aws_security_group.alb.id
}

output "https_listener_arn" {
  value = aws_lb_listener.https.arn
}
