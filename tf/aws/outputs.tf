output "cluster_name" {
  value       = aws_eks_cluster.eks.name
  description = "Name of the provisioned AWS EKS cluster"
}

output "cluster_endpoint" {
  value       = aws_eks_cluster.eks.endpoint
  description = "Kubernetes API server endpoint"
}

output "cluster_arn" {
  value       = aws_eks_cluster.eks.arn
  description = "ARN of the AWS EKS cluster"
}

output "cluster_certificate_authority_data" {
  value       = aws_eks_cluster.eks.certificate_authority[0].data
  description = "Base64 encoded certificate data required to communicate with the cluster"
  sensitive   = true
}

output "vpc_id" {
  value       = aws_vpc.eks_vpc.id
  description = "VPC ID where the cluster is deployed"
}

output "kubeconfig_command" {
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${aws_eks_cluster.eks.name}"
  description = "AWS CLI command to configure local kubectl context"
}
