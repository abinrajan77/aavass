output "db_instance_id" {
  value = aws_db_instance.this.id
}

output "db_instance_endpoint" {
  value = aws_db_instance.this.endpoint
}

output "db_instance_address" {
  value = aws_db_instance.this.address
}

output "db_instance_port" {
  value = aws_db_instance.this.port
}

output "db_name" {
  value = aws_db_instance.this.db_name
}

output "security_group_id" {
  value = aws_security_group.rds.id
}
