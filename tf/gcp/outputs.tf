output "project_id" {
  value       = var.project_id
  description = "GCP Project ID"
}

output "cluster_name" {
  value       = google_container_cluster.gke.name
  description = "GKE Cluster name"
}

output "cluster_endpoint" {
  value       = google_container_cluster.gke.endpoint
  description = "GKE Cluster API server endpoint"
}

output "kubeconfig_command" {
  value       = "gcloud container clusters get-credentials ${google_container_cluster.gke.name} --region ${var.region} --project ${var.project_id}"
  description = "gcloud CLI command to configure local kubectl context"
}
