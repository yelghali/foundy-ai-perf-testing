variable "subscription_id" {
  description = "Azure subscription ID. ARM_SUBSCRIPTION_ID can be used instead."
  type        = string
  default     = null
}

variable "location" {
  description = "Azure region for the resource group and Azure OpenAI account."
  type        = string
  default     = "eastus2"
}

variable "project_name" {
  description = "Short lowercase name used in Azure resource names."
  type        = string
  default     = "aiperf"

  validation {
    condition     = can(regex("^[a-z0-9-]{2,20}$", var.project_name))
    error_message = "project_name must contain 2-20 lowercase letters, numbers, or hyphens."
  }
}

variable "model_name" {
  description = "Azure OpenAI model name."
  type        = string
  default     = "gpt-4.1-mini"
}

variable "model_version" {
  description = "Azure OpenAI model version available in the selected region."
  type        = string
  default     = "2025-04-14"
}

variable "deployment_name" {
  description = "Name used by API requests for the model deployment."
  type        = string
  default     = "gpt-4.1-mini"
}

variable "deployment_sku_name" {
  description = "Deployment SKU, such as GlobalStandard or DataZoneStandard."
  type        = string
  default     = "GlobalStandard"
}

variable "deployment_capacity" {
  description = "Deployment capacity in thousands of tokens per minute."
  type        = number
  default     = 100

  validation {
    condition     = var.deployment_capacity > 0
    error_message = "deployment_capacity must be greater than zero."
  }
}

variable "fast_model_name" {
  description = "Smaller Azure OpenAI model used for the model-selection experiment."
  type        = string
  default     = "gpt-4.1-nano"
}

variable "fast_model_version" {
  description = "Version of the smaller Azure OpenAI model."
  type        = string
  default     = "2025-04-14"
}

variable "fast_deployment_name" {
  description = "Deployment name for the smaller comparison model."
  type        = string
  default     = "gpt-4.1-nano"
}

variable "fast_deployment_capacity" {
  description = "Comparison deployment capacity in thousands of tokens per minute."
  type        = number
  default     = 100

  validation {
    condition     = var.fast_deployment_capacity > 0
    error_message = "fast_deployment_capacity must be greater than zero."
  }
}

variable "priority_model_name" {
  description = "Priority Processing-compatible Azure OpenAI model name."
  type        = string
  default     = "gpt-4.1"
}

variable "priority_model_version" {
  description = "Priority Processing-compatible model version."
  type        = string
  default     = "2025-04-14"
}

variable "priority_deployment_name" {
  description = "Deployment used for the controlled Standard versus Priority bundle."
  type        = string
  default     = "gpt-4.1-priority-benchmark"
}

variable "priority_deployment_capacity" {
  description = "Priority-compatible deployment capacity in thousands of tokens per minute."
  type        = number
  default     = 100

  validation {
    condition     = var.priority_deployment_capacity > 0
    error_message = "priority_deployment_capacity must be greater than zero."
  }
}

variable "benchmark_image_tag" {
  description = "Container image tag built in the provisioned Azure Container Registry."
  type        = string
  default     = "latest"
}

variable "foundry_toolbox_name" {
  description = "Name of the Foundry toolbox used by the tool-search comparison."
  type        = string
  default     = "ai-perf-tools"

  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$", var.foundry_toolbox_name))
    error_message = "foundry_toolbox_name must use 1-64 lowercase letters, numbers, or hyphens."
  }
}

variable "principal_object_id" {
  description = "Object ID granted Cognitive Services OpenAI User. Defaults to current identity."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags applied to Azure resources."
  type        = map(string)
  default = {
    project    = "ai-response-performance"
    managed-by = "terraform"
  }
}
