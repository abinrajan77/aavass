locals {
  common_tags = merge(var.tags, {
    Environment = var.env
    ManagedBy   = "terraform"
    Project     = "aavaas"
  })

  name = "aavaas-${var.env}-${var.service_name}"
}

resource "aws_security_group" "task" {
  name        = "${local.name}-sg"
  description = "ECS task SG for ${local.name}"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, {
    Name = "${local.name}-sg"
  })
}

resource "aws_vpc_security_group_ingress_rule" "from_allowed" {
  for_each                     = var.container_port != null ? toset(var.ingress_security_group_ids) : []
  security_group_id            = aws_security_group.task.id
  referenced_security_group_id = each.value
  from_port                    = var.container_port
  to_port                      = var.container_port
  ip_protocol                  = "tcp"
  description                  = "Container port from ${each.value}"
}

resource "aws_vpc_security_group_egress_rule" "all_out" {
  security_group_id = aws_security_group.task.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Allow all egress"
}

# --- IAM: least-privilege task execution role + task role ------------------------
# Per specs/06-cloud-devops.md §9: no wildcard s3:*/sqs:*, scoped per service.

data "aws_iam_policy_document" "assume_ecs_tasks" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name}-execution-role"
  assume_role_policy = data.aws_iam_policy_document.assume_ecs_tasks.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets" {
  count = length(var.secret_arns_for_execution_role) > 0 ? 1 : 0

  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = var.secret_arns_for_execution_role
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  count  = length(var.secret_arns_for_execution_role) > 0 ? 1 : 0
  name   = "${local.name}-execution-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_secrets[0].json
}

resource "aws_iam_role" "task" {
  name               = "${local.name}-task-role"
  assume_role_policy = data.aws_iam_policy_document.assume_ecs_tasks.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "task_s3" {
  count = var.s3_bucket_arn != "" ? 1 : 0

  statement {
    sid       = "ObjectReadWrite"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${var.s3_bucket_arn}/*"]
  }

  statement {
    sid       = "ListBucket"
    actions   = ["s3:ListBucket"]
    resources = [var.s3_bucket_arn]
  }
}

resource "aws_iam_role_policy" "task_s3" {
  count  = var.s3_bucket_arn != "" ? 1 : 0
  name   = "${local.name}-s3"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task_s3[0].json
}

data "aws_iam_policy_document" "task_sqs" {
  count = length(var.sqs_queue_arns) > 0 ? 1 : 0

  statement {
    sid = "QueueSendReceiveDelete"
    actions = [
      "sqs:SendMessage",
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
    ]
    resources = var.sqs_queue_arns
  }
}

resource "aws_iam_role_policy" "task_sqs" {
  count  = length(var.sqs_queue_arns) > 0 ? 1 : 0
  name   = "${local.name}-sqs"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task_sqs[0].json
}

# --- Task definition ---------------------------------------------------------

locals {
  container_def = {
    name      = var.service_name
    image     = var.image
    essential = true
    portMappings = var.container_port != null ? [
      {
        containerPort = var.container_port
        protocol      = "tcp"
      }
    ] : []
    environment = [for e in var.environment_variables : { name = e.name, value = e.value }]
    secrets     = [for s in var.secrets : { name = s.name, valueFrom = s.value_from }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = var.log_group_name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = var.service_name
      }
    }
  }
}

data "aws_region" "current" {}

resource "aws_ecs_task_definition" "this" {
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([local.container_def])

  tags = merge(local.common_tags, {
    Name = local.name
  })
}

# --- Service ------------------------------------------------------------------

resource "aws_ecs_service" "this" {
  name            = local.name
  cluster         = var.cluster_id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [aws_security_group.task.id]
    # Tasks live in private subnets per specs/06-cloud-devops.md §1 — no public IP.
    assign_public_ip = false
  }

  dynamic "load_balancer" {
    for_each = var.enable_alb ? [1] : []
    content {
      target_group_arn = var.target_group_arn
      container_name   = var.service_name
      container_port   = var.container_port
    }
  }

  deployment_minimum_healthy_percent = var.deployment_minimum_healthy_percent
  deployment_maximum_percent         = var.deployment_maximum_percent

  # Rolling deploy is the ECS native default (ECS deployment controller).

  tags = merge(local.common_tags, {
    Name = local.name
  })
}

# --- Autoscaling: target-tracking on CPU 60% (+ ALB request count for the API) ---

resource "aws_appautoscaling_target" "this" {
  service_namespace  = "ecs"
  resource_id        = "service/${var.cluster_name}/${aws_ecs_service.this.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = var.min_capacity
  max_capacity       = var.max_capacity
}

resource "aws_appautoscaling_policy" "cpu" {
  name               = "${local.name}-cpu-target-tracking"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.this.service_namespace
  resource_id        = aws_appautoscaling_target.this.resource_id
  scalable_dimension = aws_appautoscaling_target.this.scalable_dimension

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = var.cpu_target_value
  }
}

resource "aws_appautoscaling_policy" "alb_request_count" {
  count              = var.enable_alb ? 1 : 0
  name               = "${local.name}-alb-request-count"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.this.service_namespace
  resource_id        = aws_appautoscaling_target.this.resource_id
  scalable_dimension = aws_appautoscaling_target.this.scalable_dimension

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
      resource_label         = "${var.alb_arn_suffix}/${var.target_group_arn_suffix}"
    }
    target_value = var.requests_per_target_value
  }
}

# --- Alternate frontend path (NOT built out) -------------------------------------
# specs/06-cloud-devops.md §6: "Alternative (if Amplify's SSR runtime proves
# limiting): containerize Next.js and run it as its own ECS/Fargate service
# behind the same ALB pattern as the API, with CloudFront in front for static
# asset caching." Default is Amplify Hosting for v1.0 (see environments/*/main.tf
# amplify note) — this module can host that alternate frontend service later by
# instantiating it a third time with enable_alb=true and a separate target
# group/listener rule, plus a CloudFront distribution in front. Not implemented:
#
# module "frontend_ecs" {
#   source         = "../../modules/ecs-service"
#   service_name   = "frontend"
#   container_port = 3000
#   enable_alb     = true
#   # ...same pattern as the api service module call below...
# }
#
# and a CloudFront distribution module would sit in front of that ALB listener.
