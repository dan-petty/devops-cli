output "resource_group_name" {
  value       = azurerm_resource_group.rg.name
  description = "Name of the Azure Resource Group"
}

output "cluster_name" {
  value       = azurerm_kubernetes_cluster.aks.name
  description = "Name of the AKS cluster"
}

output "cluster_endpoint" {
  value       = azurerm_kubernetes_cluster.aks.kube_config[0].host
  description = "AKS Kubernetes API server endpoint"
}

output "kubeconfig_command" {
  value       = "az aks get-credentials --resource-group ${azurerm_resource_group.rg.name} --name ${azurerm_kubernetes_cluster.aks.name} --overwrite-existing"
  description = "Azure CLI command to configure local kubectl context"
}
