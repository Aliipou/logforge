resource "azurerm_container_registry" "main" {
  name                = "${var.project}${var.environment}acr${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = var.container_registry_sku
  admin_enabled       = false
  tags                = local.common_tags
}
