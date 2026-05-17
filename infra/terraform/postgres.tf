resource "azurerm_postgresql_flexible_server" "main" {
  name                   = "${var.project}-${var.environment}-pg-${random_string.suffix.result}"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = "16"
  administrator_login    = "pgadmin"
  administrator_password = var.postgres_admin_password
  sku_name               = var.postgres_sku
  storage_mb             = 32768
  backup_retention_days  = 7
  zone                   = "1"
  tags                   = local.common_tags
}

resource "azurerm_postgresql_flexible_server_database" "logforge" {
  name      = "logforge"
  server_id = azurerm_postgresql_flexible_server.main.id
  collation = "en_US.utf8"
  charset   = "utf8"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure" {
  name             = "allow-azure-services"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}
