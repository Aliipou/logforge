output "resource_group_name" {
  value       = azurerm_resource_group.main.name
  description = "Name of the main resource group."
}

output "postgres_fqdn" {
  value       = azurerm_postgresql_flexible_server.main.fqdn
  description = "Fully-qualified domain name of the PostgreSQL server."
  sensitive   = true
}

output "container_registry_login_server" {
  value       = azurerm_container_registry.main.login_server
  description = "ACR login server URL (e.g., logforgedev.azurecr.io)."
}
