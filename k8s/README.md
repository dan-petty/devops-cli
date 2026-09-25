# k8s/ — Local Kubernetes Infrastructure & LLM Stacks

Kustomize + Helm-based configurations for deploying infrastructure management (`infra`) and local AI/LLM (`llm`) stacks to the devcontainer's minikube cluster.

## Stacks Overview

| Stack | Components | Namespaces | Default Ports |
| :--- | :--- | :--- | :--- |
| **`infra`** *(Default)* | ArgoCD (backed by Valkey), Prometheus Stack (Prometheus + Grafana), NVIDIA DCGM Exporter, OpenTelemetry Collector | `argocd`, `monitoring`, `otel` | `8080` (ArgoCD), `8030` (Grafana), `8090` (Prometheus) |
| **`llm`** | Ollama, Open-WebUI, Qdrant Vector DB, Valkey Cache, Valkey Run Index | `llm` | `11434` (Ollama), `3000` (WebUI), `6333` (Qdrant), `6379` (Valkey) |
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

# Valkey Run Index: benchmark and evaluation runs shared by workstations. Create its password
# before the first apply (never commit it), then point devops-cli at it through its NodePort.
kubectl -n llm create secret generic valkey-runs-auth --from-literal=password="$(openssl rand -hex 32)"
devops ai runs connect

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

- `devops-review` spreads one model name over every inference server: both vLLM profiles and the Ollama nodes (`gpt-oss:20b`). Each deployment takes a share of requests weighted by its throughput (dual-GPU vLLM 5, single-GPU vLLM 3, each Ollama node 1), and pre-call checks keep a prompt off any deployment whose window it exceeds. No deployment is capped with `max_parallel_requests`: LiteLLM waits on the cap only after routing, so queued requests pile up behind it while larger servers idle, and the backends queue excess requests themselves.
- `ollama/<model>` reaches any model on the Ollama nodes by name, for chat and embeddings, through Ollama's OpenAI-compatible API (e.g. `ollama/gpt-oss:20b`, `ollama/embeddinggemma:300m`).

Recheck the `devops-review` weights whenever a backend, model or node changes. `devops ai gateway tune` measures each deployment on its own, from an ephemeral Python container attached to the gateway pod (`kubectl debug`), since the backends admit only the gateway. It recommends each weight as capacity (fixed-length tokens per second) divided by cost (the tokens the model writes per request), and lists each backend's GPUs and engine. It changes nothing; copy the recommended weights into `litellm_params.weight`:
```bash
devops ai gateway tune                      # devops-review at concurrency 1, 4 and 8
devops ai gateway tune --model devops-chat --format json
```

Point devops-cli at the gateway, so reviews, chat and embeddings all go through it (the key comes from `DEVOPS_CLI_AI_API_KEY` or the keyring):
```yaml
ai:
  gateway_url: http://<node>:<node-port>/v1
  tasks:
    analysis:            # devops ai review
      provider: gateway
      model: devops-review
      context_window: 16384   # sizes review pages to fit the smallest server
    # verification:      # checks the findings analysis produced; unset, analysis verifies
    #   model: devops-reasoning   # layered on analysis: same provider, gateway and window
    chat:                # devops ai chat
      provider: gateway
      model: devops-coder
    embedding:
      provider: gateway
      model: ollama/embeddinggemma:300m
```
Provider `gateway` always sends to `ai.gateway_url`, even when `ai.api_base_url` is set for another provider. To send one task to a different gateway, set `api_base_url` on that task.

`verification` applies on top of `analysis`, so it only has to name what differs. Leave it unset unless a comparison on your own reviews favors a split. On the homelab, verifying with the 32B model (`devops-reasoning`) made reviews slower, since every verification queued on one server. It also rejected nearly every candidate, while one top-severity false positive still passed.

Open WebUI uses the same key: on a fresh install it connects to the gateway automatically. An existing installation keeps the connections stored in its database, so add `http://llm-gateway.llm.svc.cluster.local:4000/v1` under Admin Panel > Settings > Connections.

### GPU Placement: vLLM and Ollama
Inference engines are placed by GPU architecture, using node labels from NVIDIA GPU Feature Discovery (`nvidia.com/gpu.family`) or an architecture labeler (`nvidia.com/gpu.architecture`):

| Workload | Nodes | Model | Served as | Virtual model |
| :--- | :--- | :--- | :--- | :--- |
| `vllm` Deployment | 2+ Ampere-or-newer GPUs | Qwen2.5-Coder-32B-Instruct-AWQ, tensor parallel 2, 64K context (YaRN) | `qwen2.5-coder-32b-instruct` | `devops-reasoning` |
| `vllm-single` Deployment | 1 Ampere-or-newer GPU with 16 GiB+ | Qwen2.5-Coder-14B-Instruct-AWQ, FP8 KV cache, 16K context | `qwen2.5-coder-14b-instruct` | `devops-coder` |
| `ollama` StatefulSet, one pod per node | GPUs older than Ampere | Pulled on demand | Ollama model tags | `devops-chat`, `devops-embedding`, `ollama/*` |

Both vLLM Deployments keep weights on a PersistentVolumeClaim (`vllm-model-cache`, `vllm-single-model-cache`), download through the Squid proxy (trusting its CA, with Hugging Face Xet transfers disabled because they fail through SSL bumping), and are reachable only inside the cluster, through the gateway. A vLLM pod stays `Pending` until a node carries matching GPU labels. The first start downloads the weights, which can take hours on a home connection; the startup probe allows 3 hours before restarting the pod. The gateway lists each Ollama pod (`ollama-<n>.ollama-nodes`) as its own deployment, so it balances load and cools down failures per node. Through the `ollama` Service, LiteLLM's long-lived connections would pin every request to one pod. The Ollama-backed aliases therefore expect `qwen2.5-coder:7b`, `bge-m3` and `gpt-oss:20b` on every Ollama node (`ollama pull qwen2.5-coder:7b`). Set `replicas` in `llm/ollama.yaml` to the number of GPU nodes Ollama may use, and keep one gateway entry per replica in `llm/gateway/configmap.yaml`. A replica with no node to run on stays `Pending`, and requests sent to it fail over to the other nodes.

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
│   ├── dcgm-exporter-values.yaml # Helm values for nvidia/dcgm-exporter (GPU metrics)
│   └── prometheus-values.yaml # Helm values for kube-prometheus-stack, with the vLLM and gateway monitors
├── otel/
│   ├── kustomization.yaml    # Kustomize overlay for OpenTelemetry
│   ├── namespace.yaml        # otel namespace
│   └── values.yaml           # Helm values for opentelemetry-collector
├── llm/
│   ├── kustomization.yaml    # Kustomize overlay for LLM stack base
│   ├── namespace.yaml        # llm namespace
│   ├── valkey.yaml           # Valkey Deployment + Service manifest
│   ├── valkey-runs.yaml      # Run index Valkey: PVC, Deployment, NodePort Service, NetworkPolicy
│   ├── values-ollama.yaml    # Helm values for ollama/ollama
│   ├── values-open-webui.yaml# Helm values for open-webui/open-webui
│   ├── values-qdrant.yaml    # Helm values for qdrant/qdrant
│   ├── gateway/              # LiteLLM gateway: Deployment, routing ConfigMap, NodePort Service, NetworkPolicy
│   ├── vllm/                 # Dual-GPU vLLM (TP=2): Deployment, PVC, Service, NetworkPolicy
│   └── vllm-single/          # Single-GPU vLLM: Deployment, PVC, Service, NetworkPolicy
└── README.md                 # This file
```
