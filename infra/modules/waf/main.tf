# WAF module — rate-limiting rule + AWS managed rule sets (SQLi/XSS baseline)
# attached to the ALB, per specs/06-cloud-devops.md §9. REGIONAL scope since
# this attaches to an ALB (not CloudFront, which would need scope=CLOUDFRONT
# in us-east-1 — revisit if/when the alternate ECS+CloudFront frontend path
# from 06-cloud-devops.md §6 is ever built).

locals {
  common_tags = merge(var.tags, {
    Environment = var.env
    ManagedBy   = "terraform"
    Project     = "aavaas"
  })
}

resource "aws_wafv2_web_acl" "this" {
  name        = "aavaas-${var.env}-waf"
  description = "Rate limiting + AWS managed baseline (SQLi/XSS) for the ${var.env} ALB."
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "rate-limit-per-ip"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.rate_limit_per_5min
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "aavaas-${var.env}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "aws-managed-common-rule-set"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "aavaas-${var.env}-common-rule-set"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "aws-managed-sqli-rule-set"
    priority = 3

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "aavaas-${var.env}-sqli-rule-set"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "aavaas-${var.env}-waf"
    sampled_requests_enabled   = true
  }

  tags = merge(local.common_tags, {
    Name = "aavaas-${var.env}-waf"
  })
}

resource "aws_wafv2_web_acl_association" "alb" {
  resource_arn = var.alb_arn
  web_acl_arn  = aws_wafv2_web_acl.this.arn
}
