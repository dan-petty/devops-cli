# Knowledge Base: Minikube (Local Kubernetes Engine)

## 1. Overview & Purpose

Minikube is an open-source tool that implements a local single-node Kubernetes cluster on developer workstations. In the `devops-cli` ecosystem, Minikube is used to bootstrap local testing clusters, run automated CI smoke tests, deploy local GitOps stacks, test Helm charts, and execute GPU-accelerated local machine learning workloads.

---

## 2. Usage Information & Architecture

- **Driver Architecture**: Uses the Docker container driver (`--driver=docker`) inside development workstations, enabling seamless Kubernetes lifecycle management within DevContainers.
- **Automated Bootstrap**: `devops k8s bootstrap` automates cluster creation, driver configuration, resource allocation, and add-on enablement.
- **GPU Acceleration**: Automatically passes host NVIDIA GPUs into the Minikube cluster (`--gpus all`) when GPU drivers (`nvidia-smi`) are available.
- **Add-on Suite**: Automatically provisions essential add-ons including `ingress`, `metrics-server`, `dashboard`, and `default-storageclass`.

---

## 3. Common & Advanced Commands

### DevOps CLI Minikube Automation
```bash
# Bootstrap local Minikube cluster with defaults and GPU passthrough
devops k8s bootstrap

# Check status of local Minikube cluster and nodes
devops k8s status

# Delete local Minikube cluster and clean up volumes
devops k8s delete
```

### Standard & Advanced `minikube` Commands
```bash
# Start Minikube with explicit memory, CPU, and Docker driver
minikube start --driver=docker --cpus=4 --memory=8192 --disk-size=30g

# Start Minikube with NVIDIA GPU passthrough
minikube start --driver=docker --gpus=all

# Inspect cluster status and host components
minikube status

# List enabled add-ons
minikube addons list

# Enable ingress controller add-on
minikube addons enable ingress

# Open Kubernetes dashboard in browser
minikube dashboard

# Access Minikube Docker environment directly
eval $(minikube docker-env)

# Stop and delete Minikube cluster
minikube stop
minikube delete --all --purge
```

---

## 4. Best Practice Guidance

1. **Resource Sizing**: Allocate at least 4 CPUs and 8 GB RAM (`--cpus=4 --memory=8192`) when running Prometheus, Grafana, and ArgoCD concurrently.
2. **Persistent Profiles**: Use named profiles (`minikube start -p devops-cluster`) to manage multiple isolated clusters for separate testing domains.
3. **Driver Selection**: Prefer `--driver=docker` in containerized devcontainer environments and Linux workstations for optimal performance.
4. **Clean Deletions**: Always run `minikube delete --purge` when tearing down test clusters to release local disk space and bridge networks.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Host Network Isolation**: Avoid binding Minikube NodePorts or API server endpoints to `0.0.0.0` on shared corporate networks.
- **Certificate Renewal**: Minikube generates local self-signed TLS certificates; ensure kubeconfig contexts are rotated if local root CA certificates expire.
- **Container Sockets**: Restrict unprivileged processes inside Minikube containers from accessing the host's underlying Docker socket.

---

## 6. General Standards & Reference Guidelines

- **Environment Control**: Respect `DEVOPS_MINIKUBE_AUTOSTART=true` environment variable during container post-create hooks.
- **Kubernetes Version Alignment**: Track stable Kubernetes minor releases (`--kubernetes-version=v1.31.0`).

---

## 7. Official References & Published Artifacts

- **Project Homepage**: [minikube.sigs.k8s.io](https://minikube.sigs.k8s.io/)
- **Public Git Repository**: [github.com/kubernetes/minikube](https://github.com/kubernetes/minikube)
- **Official Minikube Releases**: [github.com/kubernetes/minikube/releases](https://github.com/kubernetes/minikube/releases)
- **DevOps CLI Minikube Bootstrap**: [src/devops_cli/commands/k8s.py](file:///workspaces/devops-cli/src/devops_cli/commands/k8s.py)
