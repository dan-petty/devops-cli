# OpenTofu Multi-Cloud Infrastructure Modules — devops-cli

This directory provides production-grade [OpenTofu](https://opentofu.org/) (and Terraform) Infrastructure-as-Code modules for provisioning managed Kubernetes clusters and cloud networking across **AWS**, **Azure**, and **Google Cloud Platform (GCP)**.

These cloud resources are purpose-built to host the project's [`k8s/`](../k8s/) resources (ArgoCD, Prometheus, Grafana, OpenTelemetry, and LLM Inference engines).

---

## Directory Structure

```
tf/
├── README.md               # Infrastructure documentation and multi-cloud quickstart
├── aws/                    # AWS EKS & VPC Infrastructure
│   ├── versions.tf         # Provider requirements and OpenTofu version constraints
│   ├── variables.tf        # AWS configuration inputs
│   ├── main.tf             # VPC, subnets, NAT gateway, IAM, and EKS cluster definitions
│   └── outputs.tf          # Cluster endpoints, ARN, and kubeconfig connection commands
├── azure/                  # Azure AKS & VNet Infrastructure
│   ├── versions.tf         # AzureRM provider requirements
│   ├── variables.tf        # Azure configuration inputs
│   ├── main.tf             # Resource Group, VNet, Subnet, and AKS managed cluster
│   └── outputs.tf          # AKS endpoints, credentials, and connection commands
├── gcp/                    # GCP GKE & VPC Infrastructure
│   ├── versions.tf         # Google provider requirements
│   ├── variables.tf        # GCP project and region configuration inputs
│   ├── main.tf             # VPC network, subnets, service accounts, and GKE cluster
│   └── outputs.tf          # GKE endpoints and gcloud connect command
└── environments/           # Example environment variable definition files
    ├── aws.tfvars.example
    ├── azure.tfvars.example
    └── gcp.tfvars.example
```

---

## Target Kubernetes Stack Integration

Once a cluster is provisioned in any cloud provider, connect your local `kubectl` context and deploy the project's Kubernetes stack:

```bash
# 1. Connect kubectl (example for AWS EKS)
aws eks update-kubeconfig --region us-west-2 --name devops-cli-cluster

# 2. Deploy project namespaces & resources using devops-cli
devops k8s bootstrap
devops k8s deploy-stack --stack all
```

---

## Quickstart per Cloud Provider

### 1. AWS (EKS + VPC)
```bash
cd tf/aws
tofu init
tofu plan -var-file=../environments/aws.tfvars.example
tofu apply -var-file=../environments/aws.tfvars.example
```

### 2. Azure (AKS + VNet)
```bash
cd tf/azure
tofu init
tofu plan -var-file=../environments/azure.tfvars.example
tofu apply -var-file=../environments/azure.tfvars.example
```

### 3. Google Cloud (GKE + VPC)
```bash
cd tf/gcp
tofu init
tofu plan -var-file=../environments/gcp.tfvars.example
tofu apply -var-file=../environments/gcp.tfvars.example
```
