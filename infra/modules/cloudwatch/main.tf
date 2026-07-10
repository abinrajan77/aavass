# CloudWatch module — log groups + alarms per specs/06-cloud-devops.md §8 and
# alarm thresholds informed by the latency budget table in
# specs/00-architecture-and-standards.md §4.

locals {
  common_tags = merge(var.tags, {
    Environment = var.env
    ManagedBy   = "terraform"
    Project     = "aavaas"
  })

  alarm_actions = var.sns_alarm_topic_arn != null ? [var.sns_alarm_topic_arn] : (
    length(aws_sns_topic.alarms) > 0 ? [aws_sns_topic.alarms[0].arn] : []
  )
}

resource "aws_sns_topic" "alarms" {
  count = var.sns_alarm_topic_arn == null ? 1 : 0
  name  = "aavaas-${var.env}-alarms"
  tags  = local.common_tags
}

# --- Log groups: API, worker, frontend -------------------------------------------
# Frontend is hosted on Amplify (specs/06-cloud-devops.md §6), which manages its
# own build/SSR logs natively. This log group is a placeholder/aggregation
# target only, for if custom log forwarding from Amplify is added later — it is
# not wired to anything yet (deliberate stub).

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aavaas/${var.env}/api"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags, { Name = "aavaas-${var.env}-api-logs" })
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aavaas/${var.env}/worker"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags, { Name = "aavaas-${var.env}-worker-logs" })
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/aavaas/${var.env}/frontend"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags, { Name = "aavaas-${var.env}-frontend-logs" })
}

# --- ALB p95 latency --------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "alb_p95_latency" {
  alarm_name          = "aavaas-${var.env}-alb-p95-latency"
  alarm_description   = "ALB p95 TargetResponseTime exceeds the dashboard-aggregate latency budget (500ms) from 00-architecture-and-standards.md §4. Tightest per-route budgets (auth 300ms, CRUD 200ms) will alarm here too since this is ALB-wide; bulk/report endpoints are allowed up to 10s and are NOT well represented by this single alarm — see variable description."
  namespace           = "AWS/ApplicationELB"
  metric_name         = "TargetResponseTime"
  extended_statistic  = "p95"
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.alb_p95_latency_threshold_seconds
  period              = 60
  evaluation_periods  = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
  tags          = local.common_tags
}

# --- ECS CPU/memory saturation per service ----------------------------------------

resource "aws_cloudwatch_metric_alarm" "ecs_cpu" {
  for_each            = toset(var.ecs_services)
  alarm_name          = "aavaas-${var.env}-ecs-${each.value}-cpu-high"
  alarm_description   = "ECS service ${each.value} CPU utilization saturation."
  namespace           = "AWS/ECS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.ecs_cpu_threshold_percent
  period              = 60
  evaluation_periods  = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = each.value
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
  tags          = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "ecs_memory" {
  for_each            = toset(var.ecs_services)
  alarm_name          = "aavaas-${var.env}-ecs-${each.value}-memory-high"
  alarm_description   = "ECS service ${each.value} memory utilization saturation."
  namespace           = "AWS/ECS"
  metric_name         = "MemoryUtilization"
  statistic           = "Average"
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.ecs_memory_threshold_percent
  period              = 60
  evaluation_periods  = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = each.value
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
  tags          = local.common_tags
}

# --- RDS CPU / connections / free storage -----------------------------------------

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "aavaas-${var.env}-rds-cpu-high"
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.rds_cpu_threshold_percent
  period              = 60
  evaluation_periods  = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = var.rds_instance_id
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
  tags          = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  alarm_name          = "aavaas-${var.env}-rds-connections-high"
  namespace           = "AWS/RDS"
  metric_name         = "DatabaseConnections"
  statistic           = "Average"
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.rds_connections_threshold
  period              = 60
  evaluation_periods  = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = var.rds_instance_id
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
  tags          = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  alarm_name          = "aavaas-${var.env}-rds-free-storage-low"
  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  statistic           = "Average"
  comparison_operator = "LessThanThreshold"
  threshold           = var.rds_free_storage_threshold_bytes
  period              = 300
  evaluation_periods  = 2
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = var.rds_instance_id
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
  tags          = local.common_tags
}

# --- SQS queue depth / age of oldest message (signals a stuck worker) -------------

resource "aws_cloudwatch_metric_alarm" "sqs_depth" {
  for_each            = var.sqs_queue_names
  alarm_name          = "aavaas-${var.env}-sqs-${each.key}-depth-high"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Average"
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.sqs_queue_depth_threshold
  period              = 60
  evaluation_periods  = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = each.value
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
  tags          = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "sqs_oldest_message_age" {
  for_each            = var.sqs_queue_names
  alarm_name          = "aavaas-${var.env}-sqs-${each.key}-oldest-message-age-high"
  alarm_description   = "Age of oldest SQS message exceeds threshold — signals a stuck worker."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  statistic           = "Maximum"
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.sqs_oldest_message_age_threshold_seconds
  period              = 60
  evaluation_periods  = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = each.value
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions
  tags          = local.common_tags
}
