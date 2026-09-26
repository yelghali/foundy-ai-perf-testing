output "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint for AZURE_OPENAI_ENDPOINT."
  value       = azurerm_cognitive_account.openai.endpoint
}

output "azure_openai_deployment" {
  description = "Deployment name for AZURE_OPENAI_DEPLOYMENT."
  value       = azurerm_cognitive_deployment.model.name
}

output "azure_openai_fast_deployment" {
  description = "Smaller deployment used by model-selection experiments."
  value       = azurerm_cognitive_deployment.fast_model.name
}

output "azure_openai_priority_deployment" {
  description = "gpt-4.1 deployment used for Standard versus Priority bundle tests."
  value       = azurerm_cognitive_deployment.priority_model.name
}

output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "container_registry_login_server" {
  value = azurerm_container_registry.this.login_server
}

output "benchmark_job_name" {
  value = azurerm_container_app_job.benchmark.name
}

output "foundry_project_endpoint" {
  description = "Project endpoint used to create and manage the benchmark toolbox."
  value       = "https://${azurerm_cognitive_account.foundry.name}.services.ai.azure.com/api/projects/${azurerm_cognitive_account_project.toolbox.name}"
}

output "foundry_toolbox_endpoint" {
  description = "Consumer MCP endpoint for the default benchmark toolbox version."
  value       = "https://${azurerm_cognitive_account.foundry.name}.services.ai.azure.com/api/projects/${azurerm_cognitive_account_project.toolbox.name}/toolboxes/${var.foundry_toolbox_name}/mcp?api-version=v1"
}

output "remote_mcp_url" {
  description = "Public synthetic MCP endpoint wrapped by the Foundry toolbox."
  value       = "https://${azurerm_container_app.benchmark_mcp.ingress[0].fqdn}/mcp"
}

output "results_storage_account_name" {
  value = azurerm_storage_account.results.name
}

output "results_container_name" {
  value = azurerm_storage_container.results.name
}
