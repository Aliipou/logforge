variable "project" {
  type        = string
  default     = "logforge"
  description = "Project name used as a prefix for all resources."
}

variable "environment" {
  type        = string
  description = "Deployment environment: dev, staging, or prod."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "location" {
  type        = string
  default     = "northeurope"
  description = "Azure region for all resources."
}

variable "postgres_sku" {
  type        = string
  default     = "B_Standard_B1ms"
  description = "SKU for Azure Database for PostgreSQL Flexible Server."
}

variable "postgres_admin_password" {
  type        = string
  sensitive   = true
  description = "Admin password for PostgreSQL. Store in Key Vault or CI secret."
}

variable "container_registry_sku" {
  type    = string
  default = "Basic"
}
