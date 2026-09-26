data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

locals {
  resource_group_name = "rg-${var.project_name}-${random_string.suffix.result}"
  account_name        = "oai-${var.project_name}-${random_string.suffix.result}"
  foundry_name        = "foundry-${var.project_name}-${random_string.suffix.result}"
  foundry_project     = "tools"
  registry_name       = "acr${replace(var.project_name, "-", "")}${random_string.suffix.result}"
  storage_name        = "st${replace(var.project_name, "-", "")}${random_string.suffix.result}"
  principal_object_id = coalesce(var.principal_object_id, data.azurerm_client_config.current.object_id)
}

resource "azurerm_resource_group" "this" {
  name     = local.resource_group_name
  location = var.location
  tags     = var.tags
}

resource "azurerm_cognitive_account" "openai" {
  name                          = local.account_name
  location                      = azurerm_resource_group.this.location
  resource_group_name           = azurerm_resource_group.this.name
  kind                          = "OpenAI"
  sku_name                      = "S0"
  custom_subdomain_name         = local.account_name
  local_auth_enabled            = false
  public_network_access_enabled = true
  tags                          = var.tags
}

resource "azurerm_cognitive_deployment" "model" {
  name                 = var.deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.model_name
    version = var.model_version
  }

  sku {
    name     = var.deployment_sku_name
    capacity = var.deployment_capacity
  }
}

resource "azurerm_cognitive_deployment" "fast_model" {
  name                 = var.fast_deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.fast_model_name
    version = var.fast_model_version
  }

  sku {
    name     = var.deployment_sku_name
    capacity = var.fast_deployment_capacity
  }
}

resource "azurerm_cognitive_deployment" "priority_model" {
  name                 = var.priority_deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.priority_model_name
    version = var.priority_model_version
  }

  sku {
    name     = var.deployment_sku_name
    capacity = var.priority_deployment_capacity
  }
}

resource "azurerm_cognitive_account" "foundry" {
  name                       = local.foundry_name
  location                   = azurerm_resource_group.this.location
  resource_group_name        = azurerm_resource_group.this.name
  kind                       = "AIServices"
  sku_name                   = "S0"
  custom_subdomain_name      = local.foundry_name
  local_auth_enabled         = false
  project_management_enabled = true
  tags                       = var.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_cognitive_account_project" "toolbox" {
  name                 = local.foundry_project
  cognitive_account_id = azurerm_cognitive_account.foundry.id
  location             = azurerm_resource_group.this.location
  tags                 = var.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "openai_user" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = local.principal_object_id
}

resource "azurerm_role_assignment" "deployer_foundry_user" {
  scope                = azurerm_cognitive_account_project.toolbox.id
  role_definition_name = "Foundry User"
  principal_id         = local.principal_object_id
}

resource "azurerm_container_registry" "this" {
  name                = local.registry_name
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}

resource "azurerm_storage_account" "results" {
  name                            = local.storage_name
  resource_group_name             = azurerm_resource_group.this.name
  location                        = azurerm_resource_group.this.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  shared_access_key_enabled       = false
  public_network_access_enabled   = false
  allow_nested_items_to_be_public = false
  tags                            = var.tags
}

resource "azurerm_role_assignment" "deployer_blob_data" {
  scope                = azurerm_storage_account.results.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = local.principal_object_id
}

resource "azurerm_role_assignment" "deployer_queue_data" {
  scope                = azurerm_storage_account.results.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = local.principal_object_id
}

resource "time_sleep" "storage_rbac_propagation" {
  depends_on = [
    azurerm_role_assignment.deployer_blob_data,
    azurerm_role_assignment.deployer_queue_data,
  ]

  create_duration = "30s"
}

resource "azurerm_storage_container" "results" {
  name                  = "benchmark-results"
  storage_account_id    = azurerm_storage_account.results.id
  container_access_type = "private"

  depends_on = [time_sleep.storage_rbac_propagation]
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${var.project_name}-${random_string.suffix.result}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_virtual_network" "this" {
  name                = "vnet-${var.project_name}-${random_string.suffix.result}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  address_space       = ["10.42.0.0/16"]
  tags                = var.tags
}

resource "azurerm_subnet" "container_apps" {
  name                 = "snet-container-apps"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = ["10.42.0.0/23"]

  delegation {
    name = "container-apps"

    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_subnet" "private_endpoints" {
  name                              = "snet-private-endpoints"
  resource_group_name               = azurerm_resource_group.this.name
  virtual_network_name              = azurerm_virtual_network.this.name
  address_prefixes                  = ["10.42.2.0/24"]
  private_endpoint_network_policies = "Disabled"
}

resource "azurerm_private_dns_zone" "blob" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = azurerm_resource_group.this.name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "blob" {
  name                  = "blob-${var.project_name}-${random_string.suffix.result}"
  resource_group_name   = azurerm_resource_group.this.name
  private_dns_zone_name = azurerm_private_dns_zone.blob.name
  virtual_network_id    = azurerm_virtual_network.this.id
  registration_enabled  = false
  tags                  = var.tags
}

resource "azurerm_private_endpoint" "results_blob" {
  name                = "pe-results-blob-${random_string.suffix.result}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = var.tags

  private_service_connection {
    name                           = "results-blob"
    private_connection_resource_id = azurerm_storage_account.results.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "blob"
    private_dns_zone_ids = [azurerm_private_dns_zone.blob.id]
  }
}

resource "azurerm_container_app_environment" "this" {
  name                       = "cae-${var.project_name}-${random_string.suffix.result}"
  location                   = azurerm_resource_group.this.location
  resource_group_name        = azurerm_resource_group.this.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  infrastructure_subnet_id   = azurerm_subnet.container_apps.id
  tags                       = var.tags

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
    minimum_count         = 0
    maximum_count         = 0
  }
}

resource "azurerm_user_assigned_identity" "benchmark" {
  name                = "id-${var.project_name}-${random_string.suffix.result}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = var.tags
}

resource "azurerm_role_assignment" "benchmark_openai_user" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.benchmark.principal_id
}

resource "azurerm_role_assignment" "benchmark_acr_pull" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.benchmark.principal_id
}

resource "azurerm_role_assignment" "benchmark_blob_writer" {
  scope                = azurerm_storage_account.results.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.benchmark.principal_id
}

resource "azurerm_role_assignment" "benchmark_foundry_user" {
  scope                = azurerm_cognitive_account_project.toolbox.id
  role_definition_name = "Foundry User"
  principal_id         = azurerm_user_assigned_identity.benchmark.principal_id
}

resource "azurerm_container_app" "benchmark_mcp" {
  name                         = "mcp-${var.project_name}-${random_string.suffix.result}"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.benchmark.id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = azurerm_user_assigned_identity.benchmark.id
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name    = "benchmark-mcp"
      image   = "${azurerm_container_registry.this.login_server}/ai-perf:${var.benchmark_image_tag}"
      cpu     = 0.5
      memory  = "1Gi"
      command = ["ai-perf-mcp"]
      args = [
        "--tool-count",
        "50",
        "--description-style",
        "concise",
        "--transport",
        "streamable-http",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
      ]
    }
  }

  depends_on = [azurerm_role_assignment.benchmark_acr_pull]
}

resource "azurerm_container_app_job" "benchmark" {
  name                         = "job-${var.project_name}-${random_string.suffix.result}"
  location                     = azurerm_resource_group.this.location
  resource_group_name          = azurerm_resource_group.this.name
  container_app_environment_id = azurerm_container_app_environment.this.id
  replica_timeout_in_seconds   = 3600
  replica_retry_limit          = 0
  workload_profile_name        = "Consumption"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.benchmark.id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = azurerm_user_assigned_identity.benchmark.id
  }

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name    = "benchmark"
      image   = "${azurerm_container_registry.this.login_server}/ai-perf:${var.benchmark_image_tag}"
      cpu     = 1
      memory  = "2Gi"
      command = ["ai-perf"]
      args = [
        "run-suite",
        "--profile",
        "screen",
        "--warmups",
        "1",
        "--repetitions",
        "2",
        "--upload",
        "--continue-on-case-error",
      ]

      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.benchmark.client_id
      }
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = azurerm_cognitive_account.openai.endpoint
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT"
        value = azurerm_cognitive_deployment.model.name
      }
      env {
        name  = "AZURE_OPENAI_FAST_DEPLOYMENT"
        value = azurerm_cognitive_deployment.fast_model.name
      }
      env {
        name  = "AZURE_OPENAI_PRIORITY_DEPLOYMENT"
        value = azurerm_cognitive_deployment.priority_model.name
      }
      env {
        name  = "AZURE_STORAGE_ACCOUNT_URL"
        value = azurerm_storage_account.results.primary_blob_endpoint
      }
      env {
        name  = "AI_PERF_STORAGE_CONTAINER"
        value = azurerm_storage_container.results.name
      }
      env {
        name  = "AI_PERF_RESULTS_DIR"
        value = "/tmp/results/raw"
      }
      env {
        name  = "AI_PERF_AZURE_REGION"
        value = azurerm_resource_group.this.location
      }
      env {
        name  = "AI_PERF_BENCHMARK_IMAGE"
        value = "${azurerm_container_registry.this.login_server}/ai-perf:${var.benchmark_image_tag}"
      }
      env {
        name  = "FOUNDRY_PROJECT_ENDPOINT"
        value = "https://${azurerm_cognitive_account.foundry.name}.services.ai.azure.com/api/projects/${azurerm_cognitive_account_project.toolbox.name}"
      }
      env {
        name  = "AI_PERF_TOOLBOX_NAME"
        value = var.foundry_toolbox_name
      }
      env {
        name  = "AI_PERF_TOOLBOX_ENDPOINT"
        value = "https://${azurerm_cognitive_account.foundry.name}.services.ai.azure.com/api/projects/${azurerm_cognitive_account_project.toolbox.name}/toolboxes/${var.foundry_toolbox_name}/mcp?api-version=v1"
      }
      env {
        name  = "AI_PERF_REMOTE_MCP_URL"
        value = "https://${azurerm_container_app.benchmark_mcp.ingress[0].fqdn}/mcp"
      }
    }
  }

  depends_on = [
    azurerm_role_assignment.benchmark_acr_pull,
    azurerm_role_assignment.benchmark_blob_writer,
    azurerm_role_assignment.benchmark_foundry_user,
    azurerm_role_assignment.benchmark_openai_user,
    azurerm_private_endpoint.results_blob,
  ]
}
