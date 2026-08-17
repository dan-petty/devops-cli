variable "project_id" {
  type        = string
  description = "GCP Project ID"
  default     = "devops-cli-gcp-project"
}

variable "region" {
  type        = string
  description = "GCP Region for GKE and networking"
  default     = "us-central1"
}

variable "zone" {
  type        = string
  description = "GCP Zone for zonal resources"
  default     = "us-central1-a"
}

variable "cluster_name" {
  type        = string
  description = "Name of the Google Kubernetes Engine (GKE) cluster"
  default     = "devops-cli-gke"
}

variable "network_name" {
  type        = string
  description = "Name of the dedicated VPC network"
  default     = "devops-cli-vpc"
}

variable "subnet_cidr" {
  type        = string
  description = "Primary IP CIDR range for the GKE subnet"
  default     = "10.10.0.0/20"
}

variable "pods_cidr" {
  type        = string
  description = "Secondary IP range for Kubernetes Pods"
  default     = "10.20.0.0/16"
}

variable "services_cidr" {
  type        = string
  description = "Secondary IP range for Kubernetes Services"
  default     = "10.30.0.0/20"
}

variable "machine_type" {
  type        = string
  description = "GCE machine type for GKE node pool"
  default     = "e2-standard-4"
}

variable "node_count" {
  type        = number
  description = "Desired number of worker nodes per zone"
  default     = 3
}

variable "min_node_count" {
  type        = number
  description = "Minimum number of worker nodes for autoscaling"
  default     = 2
}

variable "max_node_count" {
  type        = number
  description = "Maximum number of worker nodes for autoscaling"
  default     = 5
}
