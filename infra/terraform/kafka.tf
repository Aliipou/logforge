# Azure Event Hubs used as managed Kafka-compatible broker.
# Kafka protocol is enabled at the namespace level.
resource "azurerm_eventhub_namespace" "kafka" {
  name                = "${var.project}-${var.environment}-eh-${random_string.suffix.result}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "Standard"
  capacity            = 1
  kafka_enabled       = true
  tags                = local.common_tags
}

resource "azurerm_eventhub" "logs" {
  name                = "logs"
  namespace_name      = azurerm_eventhub_namespace.kafka.name
  resource_group_name = azurerm_resource_group.main.name
  partition_count     = 4
  message_retention   = 1
}
