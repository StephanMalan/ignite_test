################################################################################
# MySQL RDS instance that stores Iot data
################################################################################

resource "aws_db_instance" "data_mysql" {
  engine                 = "mysql"
  identifier             = var.DATA_MYSQL_ID
  port                   = var.DATA_MYSQL_PORT
  allocated_storage      = 20
  engine_version         = "5.7"
  instance_class         = "db.t2.micro"
  username               = jsondecode(data.aws_secretsmanager_secret_version.acme_secrets_data.secret_string)["mysql_user"]
  password               = jsondecode(data.aws_secretsmanager_secret_version.acme_secrets_data.secret_string)["mysql_password"]
  parameter_group_name   = "default.mysql5.7"
  vpc_security_group_ids = [aws_security_group.data_mysql_sec_group.id]
  skip_final_snapshot    = true
  publicly_accessible    = true
}


resource "aws_security_group" "data_mysql_sec_group" {
  description = "MySQL RDS instance to store device data"
  name        = "data_mysql_sec_group"

  # Only MySQL in
  ingress {
    from_port   = var.DATA_MYSQL_PORT
    to_port     = var.DATA_MYSQL_PORT
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow all outbound traffic.
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
