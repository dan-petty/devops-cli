variable "resource_group_name" {
  type        = string
  description = "Name of the Azure resource group"
  default     = "rg-devops-cli-k8s"
}

variable "location" {
  type        = string
  description = "Azure region for resource deployment"
  default     = "eastus"
}

variable "cluster_name" {
  type        = string
  description = "Name of the Azure Kubernetes Service (AKS) managed cluster"
  default     = "devops-cli-aks"
}

variable "dns_prefix" {
  type        = string
  description = "DNS prefix for the AKS cluster"
  default     = "devops-cli-k8s"
}

variable "kubernetes_version" {
  type        = string
  description = "Kubernetes version for AKS cluster"
  default     = "1.30"
}

variable "node_vm_size" {
  type        = string
  description = "Azure VM size for the default system node pool"
  default     = "Standard_D4s_v5"
}

variable "node_count" {
  type        = number
  description = "Desired number of worker nodes in default pool"
  default     = 3
}

variable "min_node_count" {
  type        = number
  description = "Minimum number of nodes for autoscaling"
  default     = 2
}

variable "max_node_count" {
  type        = number
  description = "Maximum number of nodes for autoscaling"
  default     = 5
}

variable "vnet_address_space" {
  type        = list(string)
  description = "Address space for Azure Virtual Network"
  default     = ["10.200.0.0/16"]
}

variable "subnet_address_prefix" {
  type        = string
  description = "Subnet address prefix for AKS cluster pods and nodes"
  default     = "10.200.1.0/24"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all Azure resources"
  default = {
    Environment = "production"
    ManagedBy   = "devops-cli-opentofu"
    Project     = "devops-cli"
  }
}
