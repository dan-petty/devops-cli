# k8s/ — Local Kubernetes Infrastructure Stack

Kustomize + Helm-based configurations for deploying ArgoCD, Prometheus, Grafana,
and OpenTelemetry Collector to the devcontainer's minikube cluster.

## Prerequisites

- minikube running (`minikube status` or auto-started by postStart.sh)
- kubectl and helm on PATH (installed by devcontainer features)

## DevContainer Auto-Deployment

When running inside the devcontainer environment, minikube autostart and infrastructure stack auto-deployment are enabled by default (`DEVOPS_MINIKUBE_AUTOSTART=true` and `DEVOPS_K8S_AUTO_DEPLOY=true`). On container startup, `.devcontainer/postStart.sh` automatically starts minikube and executes `devops k8s deploy-stack` to provision ArgoCD, Prometheus, Grafana, and OpenTelemetry Collector.


## Quick Start

```bash
# Deploy everything in one command
devops k8s deploy-stack

# Or deploy manually with kustomize
kubectl apply -k k8s/

# Then install Helm releases
helm repo add argo https://argoproj.github.io/argo-helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update

helm install argocd argo/argo-cd -n argocd -f k8s/argocd/values.yaml
helm install kube-prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring -f k8s/monitoring/prometheus-values.yaml
helm install otel-collector open-telemetry/opentelemetry-collector \
  -n otel -f k8s/otel/values.yaml
```

## Accessing Services

```bash
# ArgoCD UI
minikube service argocd-server -n argocd --url

# ArgoCD admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo

# Grafana UI (admin / admin)
minikube service kube-prometheus-grafana -n monitoring --url

# Prometheus UI
minikube service kube-prometheus-kube-prom-prometheus -n monitoring --url
```

## Teardown

```bash
devops k8s teardown-stack

# Or manually
helm uninstall otel-collector -n otel
helm uninstall kube-prometheus -n monitoring
helm uninstall argocd -n argocd
kubectl delete -k k8s/
```

## Directory Structure

```
k8s/
├── kustomization.yaml        # Root kustomize: applies namespaces
├── namespaces.yaml           # Namespace definitions
├── argocd/
│   ├── kustomization.yaml    # Kustomize overlay for ArgoCD
│   ├── namespace.yaml        # argocd namespace
│   └── values.yaml           # Helm values for argo/argo-cd
├── monitoring/
│   ├── kustomization.yaml    # Kustomize overlay for monitoring
│   ├── namespace.yaml        # monitoring namespace
│   └── prometheus-values.yaml # Helm values for kube-prometheus-stack
├── otel/
│   ├── kustomization.yaml    # Kustomize overlay for OpenTelemetry
│   ├── namespace.yaml        # otel namespace
│   └── values.yaml           # Helm values for opentelemetry-collector
└── README.md                 # This file
```

## Integration with devops-cli

Once deployed, configure devops-cli to target the in-cluster services:

```bash
# ArgoCD
devops config set argocd.url "$(minikube service argocd-server -n argocd --url)"

# Grafana
devops config set grafana.url "$(minikube service kube-prometheus-grafana -n monitoring --url)"

# Prometheus
devops config set prometheus.url "$(minikube service kube-prometheus-kube-prom-prometheus -n monitoring --url)"

# Enable private network access (minikube uses internal IPs)
export DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true
```
