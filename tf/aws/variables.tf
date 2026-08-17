variable "aws_region" {
  type        = string
  description = "Target AWS region for infrastructure deployment"
  default     = "us-west-2"
}

variable "cluster_name" {
  type        = string
  description = "Name of the AWS EKS cluster"
  default     = "devops-cli-eks"
}

variable "kubernetes_version" {
  type        = string
  description = "Kubernetes control plane version"
  default     = "1.30"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the dedicated EKS VPC"
  default     = "10.100.0.0/16"
}

variable "availability_zones" {
  type        = list(string)
  description = "List of availability zones for multi-AZ subnet distribution"
  default     = ["us-west-2a", "us-west-2b", "us-west-2c"]
}

variable "node_instance_types" {
  type        = list(string)
  description = "EC2 instance types for EKS managed node group"
  default     = ["t3.xlarge"]
}

variable "node_desired_capacity" {
  type        = number
  description = "Desired number of worker nodes in node group"
  default     = 3
}

variable "node_min_capacity" {
  type        = number
  description = "Minimum number of worker nodes in node group"
  default     = 2
}

variable "node_max_capacity" {
  type        = number
  description = "Maximum number of worker nodes in node group"
  default     = 5
}

variable "tags" {
  type        = map(string)
  description = "Resource tags applied to all AWS resources"
  default = {
    Environment = "production"
    ManagedBy   = "devops-cli-opentofu"
    Project     = "devops-cli"
  }
}
