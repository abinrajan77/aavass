# RDS module — PostgreSQL 16 per specs/06-cloud-devops.md §2.
# Sizing/Multi-AZ/backup-retention/slow-query-logging are all passed in per
# environment from infra/environments/{env}/terraform.tfvars.

locals {
  common_tags = merge(var.tags, {
    Environment = var.env
    ManagedBy   = "terraform"
    Project     = "aavaas"
  })
}

resource "aws_db_subnet_group" "this" {
  name       = "aavaas-${var.env}-db-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-db-subnet-group"
  })
}

resource "aws_security_group" "rds" {
  name        = "aavaas-${var.env}-rds-sg"
  description = "Allow Postgres from ECS task security groups only"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-rds-sg"
  })
}

resource "aws_vpc_security_group_ingress_rule" "postgres_from_private_subnets" {
  for_each          = toset(var.allowed_cidr_blocks)
  security_group_id = aws_security_group.rds.id
  cidr_ipv4         = each.value
  from_port         = 5432
  to_port           = 5432
  ip_protocol       = "tcp"
  description       = "Postgres from private subnet ${each.value}"
}

resource "aws_vpc_security_group_egress_rule" "all_out" {
  security_group_id = aws_security_group.rds.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Allow all egress"
}

# Parameter group — log_min_duration_statement=500ms in prod to catch slow
# queries against the latency budgets in 00-architecture-and-standards.md §4.
resource "aws_db_parameter_group" "this" {
  name   = "aavaas-${var.env}-pg16"
  family = "postgres16"

  dynamic "parameter" {
    for_each = var.enable_slow_query_logging ? [1] : []
    content {
      name  = "log_min_duration_statement"
      value = "500"
    }
  }

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-pg16-params"
  })
}

resource "aws_db_instance" "this" {
  identifier     = "aavaas-${var.env}-db"
  engine         = "postgres"
  engine_version = "16"

  instance_class        = var.instance_class
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "aavaas"
  username = var.master_username
  password = var.master_password

  # Manually-seeded per infra/README.md — never plain env vars, never committed.

  multi_az                = var.multi_az
  backup_retention_period = var.backup_retention_days
  # PITR is automatic in RDS whenever automated backups (backup_retention_period > 0)
  # are enabled — no separate resource needed.
  deletion_protection = var.deletion_protection

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.this.name

  auto_minor_version_upgrade = true
  copy_tags_to_snapshot      = true
  skip_final_snapshot        = var.env != "prod"
  final_snapshot_identifier  = var.env == "prod" ? "aavaas-${var.env}-final-snapshot" : null

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-db"
  })
}
