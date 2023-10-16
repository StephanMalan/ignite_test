variable "REGION" {
  description = "AWS region for all resources."
  type        = string
}

variable "SECRET_MANAGER_ID" {
  description = "ID of secret manager that contains the secrets of the system."
  type        = string
}

variable "DATA_MYSQL_ID" {
  description = "ID of the MySQL RDS instance that stores the Iot data."
  type        = string
}
variable "DATA_MYSQL_PORT" {
  description = "Port of the MySQL RDS instance that stores the Iot data."
  type        = number
}

variable "DATA_MYSQL_DATABASE" {
  description = "Database name within the MySQL RDS instance that stores the Iot data."
  type        = string
}

variable "DATA_MYSQL_TABLE" {
  description = "Table name within the MySQL RDS instance that stores the Iot data."
  type        = string
}
