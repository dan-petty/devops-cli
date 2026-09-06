# k8s/ — Local Kubernetes Infrastructure & LLM Stacks

Kustomize + Helm-based configurations for deploying infrastructure management (`infra`) and local AI/LLM (`llm`) stacks to the devcontainer's minikube cluster.

## Stacks Overview

| Stack | Components | Namespaces | Default Ports |
| :--- | :--- | :--- | :--- |
| **`infra`** *(Default)* | ArgoCD (backed by Valkey), Prometheus Stack (Prometheus + Grafana), OpenTelemetry Collector | `argocd`, `monitoring`, `otel` | `8080` (ArgoCD), `8030` (Grafana), `8090` (Prometheus) |
| **`llm`** | Ollama, Open-WebUI, Qdrant Vector DB, Valkey Cache | `llm` | `11434` (Ollama), `3000` (WebUI), `6333` (Qdrant), `6379` (Valkey) |
| **`all`** | All components from both stacks | `argocd`, `monitoring`, `otel`, `llm` | All ports above |

## Prerequisites

- minikube running (`minikube status` or auto-started by postStart.sh)
- kubectl and helm on PATH (installed by devcontainer features)

## Quick Start

```bash
# Deploy default infrastructure stack (ArgoCD, Prometheus, Grafana, OTEL)
devops k8s deploy-stack

# Deploy local LLM stack (Ollama, Open-WebUI, Qdrant, Valkey)
devops k8s deploy-stack --stack llm

# Deploy all stacks simultaneously
devops k8s deploy-stack --stack all
```

## Accessing Stack Services

### Infrastructure Stack (`infra`)
```bash
# ArgoCD UI
minikube service argocd-server -n argocd --url

# ArgoCD initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo

# Grafana UI
minikube service kube-prometheus-grafana -n monitoring --url

# Prometheus UI
minikube service kube-prometheus-kube-prome-prometheus -n monitoring --url
```

### LLM Stack (`llm`)
```bash
# Ollama REST API
minikube service ollama -n llm --url

# Open-WebUI Web Interface
minikube service open-webui -n llm --url

# Qdrant Vector Database HTTP API
minikube service qdrant -n llm --url

# Valkey In-Memory Cache
kubectl -n llm exec -it svc/valkey -- valkey-cli ping
```

## Port Forwarding & Automated Configuration

```bash
# Forward ports and automatically detect URLs
devops k8s port-forward --stack infra
devops k8s port-forward --stack llm
devops k8s port-forward --stack all

# Auto-detect URLs and persist to devops config
devops k8s configure-urls --stack infra
devops k8s configure-urls --stack llm
```

## Teardown

```bash
# Teardown infrastructure stack
devops k8s teardown-stack --stack infra

# Teardown LLM stack
devops k8s teardown-stack --stack llm

# Teardown all stacks and namespaces
devops k8s teardown-stack --stack all
```

## Directory Structure

```
k8s/
├── kustomization.yaml        # Root kustomize: applies namespaces
├── namespaces.yaml           # Namespace definitions (argocd, monitoring, otel, llm)
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
├── llm/
│   ├── kustomization.yaml    # Kustomize overlay for LLM stack base
│   ├── namespace.yaml        # llm namespace
│   ├── valkey.yaml           # Valkey Deployment + Service manifest
│   ├── values-ollama.yaml    # Helm values for ollama/ollama
│   ├── values-open-webui.yaml# Helm values for open-webui/open-webui
│   └── values-qdrant.yaml    # Helm values for qdrant/qdrant
└── README.md                 # This file
```
