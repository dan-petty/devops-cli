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

# LLM Gateway: authenticated OpenAI-compatible API for every model (vLLM and Ollama)
minikube service llm-gateway -n llm --url
```

### LLM Gateway (`llm-gateway`)
The LiteLLM gateway is the single entry point to every inference server. It serves the virtual models `devops-chat`, `devops-coder`, `devops-reasoning` and `devops-embedding`, escalates a prompt too long for a model to the next larger context window (`devops-chat` → `devops-coder` 16K → `devops-reasoning` 64K) before calling any backend, falls back from an unavailable `devops-coder` to `devops-reasoning` before the small Ollama model, and rejects requests without its master key. Create the key once per cluster before deploying (it must start with `sk-`):
```bash
kubectl -n llm create secret generic llm-gateway-secrets \
  --from-literal=master-key="sk-$(openssl rand -hex 24)"
```
The Service is a NodePort that Kubernetes assigns; find it with `kubectl -n llm get svc llm-gateway`, then call the API from any node address:
```bash
KEY=$(kubectl -n llm get secret llm-gateway-secrets -o jsonpath='{.data.master-key}' | base64 -d)
curl -H "Authorization: Bearer $KEY" http://<node>:<node-port>/v1/models
```
Two more routes make the gateway the single router for both engines:

- `devops-review` spreads one model name over every inference server: both vLLM profiles and the Ollama nodes (`gpt-oss:20b`). Routing is least-busy, capped per deployment by `max_parallel_requests`, and pre-call checks keep a prompt off any deployment whose window it exceeds.
- `ollama/<model>` reaches any model on the Ollama nodes by name, for chat and embeddings, through Ollama's OpenAI-compatible API (e.g. `ollama/gpt-oss:20b`, `ollama/embeddinggemma:300m`).

Point devops-cli at the gateway per task, so reviews, chat and embeddings all go through it (the key comes from `DEVOPS_CLI_AI_API_KEY` or the keyring):
```yaml
ai:
  tasks:
    analysis:            # devops ai review
      provider: gateway
      model: devops-review
      api_base_url: http://<node>:<node-port>/v1
      context_window: 16384   # sizes review pages to fit the smallest server
    chat:                # devops ai chat
      provider: gateway
      model: devops-coder
      api_base_url: http://<node>:<node-port>/v1
    embedding:
      provider: gateway
      model: ollama/embeddinggemma:300m
      api_base_url: http://<node>:<node-port>/v1
```
Set `api_base_url` on each task: a global `ai.api_base_url` configured for another provider would otherwise take precedence over `ai.gateway_url`.

Open WebUI uses the same key: on a fresh install it connects to the gateway automatically. An existing installation keeps the connections stored in its database, so add `http://llm-gateway.llm.svc.cluster.local:4000/v1` under Admin Panel > Settings > Connections.

### GPU Placement: vLLM and Ollama
Inference engines are placed by GPU architecture, using node labels from NVIDIA GPU Feature Discovery (`nvidia.com/gpu.family`) or an architecture labeler (`nvidia.com/gpu.architecture`):

| Workload | Nodes | Model | Served as | Virtual model |
| :--- | :--- | :--- | :--- | :--- |
| `vllm` Deployment | 2+ Ampere-or-newer GPUs | Qwen2.5-Coder-32B-Instruct-AWQ, tensor parallel 2, 64K context (YaRN) | `qwen2.5-coder-32b-instruct` | `devops-reasoning` |
| `vllm-single` Deployment | 1 Ampere-or-newer GPU with 16 GiB+ | Qwen2.5-Coder-14B-Instruct-AWQ, FP8 KV cache, 16K context | `qwen2.5-coder-14b-instruct` | `devops-coder` |
| `ollama` DaemonSet | GPUs older than Ampere | Pulled on demand | Ollama model tags | `devops-chat`, `devops-embedding` |

Both vLLM Deployments keep weights on a PersistentVolumeClaim (`vllm-model-cache`, `vllm-single-model-cache`), download through the Squid proxy (trusting its CA, with Hugging Face Xet transfers disabled because they fail through SSL bumping), and are reachable only inside the cluster, through the gateway. A vLLM pod stays `Pending` until a node carries matching GPU labels. The first start downloads the weights, which can take hours on a home connection; the startup probe allows 3 hours before restarting the pod. The Ollama-backed aliases expect `qwen2.5-coder:7b` and `bge-m3` on every Ollama node, since the `ollama` Service balances across them (`ollama pull qwen2.5-coder:7b`).

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
│   ├── values-qdrant.yaml    # Helm values for qdrant/qdrant
│   ├── gateway/              # LiteLLM gateway: Deployment, routing ConfigMap, NodePort Service, NetworkPolicy
│   ├── vllm/                 # Dual-GPU vLLM (TP=2): Deployment, PVC, Service, NetworkPolicy
│   └── vllm-single/          # Single-GPU vLLM: Deployment, PVC, Service, NetworkPolicy
└── README.md                 # This file
```
