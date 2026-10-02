# k8s/ — Local Kubernetes Infrastructure & LLM Stacks

Kustomize + Helm-based configurations for deploying infrastructure management (`infra`) and local AI/LLM (`llm`) stacks to the devcontainer's minikube cluster.

## Stacks Overview

| Stack | Components | Namespaces | Default Ports |
| :--- | :--- | :--- | :--- |
| **`infra`** *(Default)* | ArgoCD (backed by Valkey), Grafana, Prometheus, Grafana K8s Monitoring Stack (Alloy + exporters), Grafana Pyroscope, NVIDIA DCGM Exporter, OpenTelemetry Collector | `argocd`, `monitoring`, `otel` | `8080` (ArgoCD), `8030` (Grafana), `8090` (Prometheus), `4040` (Pyroscope) |
| **`llm`** | Ollama, Open-WebUI, Qdrant Vector DB, Valkey Cache, Valkey Run Index | `llm` | `11434` (Ollama), `3000` (WebUI), `6333` (Qdrant), `6379` (Valkey) |
| **`all`** | All components from both stacks | `argocd`, `monitoring`, `otel`, `llm` | All ports above |

## Prerequisites

- minikube running (`minikube status` or auto-started by postStart.sh)
- kubectl and helm on PATH (installed by devcontainer features)
- standard Kubernetes context configuration (the CLI uses `$KUBECONFIG` or defaults to `~/.kube/config`)

## Quick Start

```bash
# Ensure kubectl can access the cluster. The devops CLI uses the standard KUBECONFIG environment variable or ~/.kube/config:
export KUBECONFIG=$HOME/.kube/config

# Deploy default infrastructure stack (ArgoCD, K8s Monitoring, OTEL)
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

# Monitoring Stack (Alloy Metrics & Scrapes)
minikube service k8s-monitoring-alloy-metrics -n monitoring --url

# Pyroscope Continuous Profiling UI
kubectl -n monitoring port-forward svc/pyroscope 4040:4040
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

- `devops-review` spreads one model name over every inference server: vLLM and the Ollama node (`qwen3-coder:30b`). Each deployment takes a share of requests weighted by its throughput (dual-GPU vLLM 5, Ollama node 1), and pre-call checks keep a prompt off any deployment whose window it exceeds. No deployment is capped with `max_parallel_requests`: LiteLLM waits on the cap only after routing, so queued requests pile up behind it while larger servers idle, and the backends queue excess requests themselves.
- `ollama/<model>` reaches any model on the Ollama nodes by name, for chat and embeddings, through Ollama's OpenAI-compatible API (e.g. `ollama/gpt-oss:20b`, `ollama/embeddinggemma:300m`).
- `qwen3-coder:30b` and `gpt-oss:20b` each pin one of `devops-review`'s models: the group copies that model's `devops-review` deployments and weights, with no `max_input_tokens` and no fallback, so a review measured on one model is routed as the pool routes it.

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

Inference workloads pull models directly and are reachable inside the cluster through the gateway. The gateway lists each Ollama pod (`ollama-<n>.ollama-nodes`) as its own deployment, balancing load and cooling down failures per node.

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

## Grafana Dashboards

Dashboards live in `monitoring/dashboards/`. Its `kustomization.yaml` generates four ConfigMaps labelled `grafana_dashboard: "1"`, and the Grafana dashboard sidecar (`monitoring/grafana-values.yaml`) loads every ConfigMap with that label:

| ConfigMap | Dashboards |
| :--- | :--- |
| `grafana-k8s-global-dashboards` | `k8s-views-global.json`, `k8s-views-pods.json` |
| `grafana-k8s-node-dashboards` | `k8s-views-nodes.json`, `k8s-views-namespaces.json` |
| `grafana-devops-cli-dashboards` | `devops-cli.json`, `ai-spend.json`, `project-metrics.json` |
| `grafana-stack-dashboards` | `sre-service.json`, `ingress-tunnel.json`, `llm-stack.json`, `otel-collector.json`, `prometheus-server.json` |

`devops k8s deploy-stack` applies them through the root kustomization, in the same run that creates the `monitoring` namespace, and `teardown-stack` removes them. Grafana holds these dashboards as provisioned and refuses to save over them, so change the JSON file and deploy again. To provision another dashboard, add it to a generator entry; each ConfigMap must stay under the 262,144 bytes kubectl's last-applied annotation allows.

The stack dashboards chart the cluster workloads and infrastructure services:

| Dashboard | Exporter / Sources | How Prometheus / Loki gets its series |
| :--- | :--- | :--- |
| `sre-service.json`, "SRE Service & Logs" (`devops-sre-service`) | cAdvisor container CPU, memory, network packets/drops, and Loki service logs | Metrics scraped by Alloy from cAdvisor/Kubelet and Kube State Metrics; logs pushed to Loki via Alloy or OpenTelemetry collector |
| `ingress-tunnel.json`, "SRE / Ingress & Cloudflare Tunnel" (`devops-ingress-tunnel`) | Traefik ingress metrics (port 9100) and Cloudflare Tunnel metrics (port 2000) | Scraped directly by the Prometheus server's `kubernetes-pods` job via pod annotations; network policy allows monitoring to scrape Cloudflare Tunnel |
| `llm-stack.json`, "LLM Gateway & GPUs" (`devops-llm-stack`) | LiteLLM's Prometheus callback on the gateway (`/metrics/`), and the NVIDIA DCGM exporter on every GPU node | The `llm-gateway` ServiceMonitor in `monitoring/k8s-monitoring-values.yaml` and the DCGM chart's own ServiceMonitor (`serviceMonitor.enabled` in `monitoring/dcgm-exporter-values.yaml`), read by Alloy, which remote-writes to the server |
| `otel-collector.json`, "OpenTelemetry Collector" (`devops-otel-traces`) | The collector's own telemetry on port 8888 | The server's `kubernetes-pods` job, through the `prometheus.io/scrape` and `prometheus.io/port` pod annotations in `otel/values.yaml`; not through Alloy, so the collector's export failures stay visible when Alloy is what fails |
| `prometheus-server.json`, "Prometheus Server" (`devops-prometheus-server`) | The Prometheus server's own `/metrics`, and `up` for every target | The server's `prometheus` job, which scrapes itself (`scrapeConfigs.prometheus` in `monitoring/prometheus-values.yaml`) |

```bash
devops grafana dashboards lint k8s/monitoring/dashboards  # also catches a uid two files share
devops grafana dashboards sync                            # posts every file in the directory
```
`sync` exits 1 if any dashboard failed. It reports the provisioned dashboards as skipped, not failed.

`tests/test_stack_dashboards.py` checks every query against captures of these exporters in `tests/fixtures/metrics/`: each series it selects, each label it matches or groups by, and the scrape in the table. No query falls back to a constant such as `or vector(0)`, so a panel without data reads "No data" rather than zero, and a panel drawn against a limit extends its axis to that limit. The gateway's failure, cooldown and fallback panels and the collector's span export failures stay empty until the first such event.

## Teardown

```bash
# Teardown infrastructure stack
devops k8s teardown-stack --stack infra

# Teardown LLM stack
devops k8s teardown-stack --stack llm

# Teardown all stacks and namespaces
devops k8s teardown-stack --stack all
```

Teardown leaves the `prometheus-operator-crds` release's CRDs in the cluster. Deleting a CRD deletes every object of its kind, such as every ServiceMonitor, so remove them by hand only when nothing in the cluster uses them.

## Cloudflare Wildcard Tunnel & Ingress Routing

Expose homelab Kubernetes services securely to the internet without public ports, dynamic DNS, or firewall holes using a wildcard Cloudflare Tunnel paired with an in-cluster ingress controller (Traefik or Ingress-Nginx).

### Architecture

```
                                  Cloudflare Edge
[Client / Browser] ──── HTTPS ───▶ [DNS: *.homelab.<domain>]
                                         │
                                  [Access SSO / Zero Trust]
                                         │
                                 (Encrypted Tunnel)
                                         ▼
                           k8s / Namespace: cloudflared
                           [cloudflared Pods (Replicas: 2)]
                                         │
                             (Internal HTTP Ingress)
                                         ▼
                           k8s / Namespace: kube-system
                           [Traefik Ingress (ClusterIP:80)]
                                   │           │
                 ┌─────────────────┘           └─────────────────┐
                 ▼                                               ▼
     k8s / Namespace: llm                         k8s / Namespace: monitoring
  [chat.homelab.<domain>] ──▶ open-webui       [grafana.homelab.<domain>] ──▶ grafana
  [ai.homelab.<domain>]   ──▶ llm-gateway      [argocd.homelab.<domain>]  ──▶ argocd
```

### 1. Cloudflare Dashboard Tunnel Configuration

1. In **Cloudflare Zero Trust** (`Networks` > `Tunnels`), select your tunnel (e.g. `homelab`).
2. Add a **Public Hostname**:
   - **Subdomain**: `*.homelab`
   - **Domain**: `<domain>` (e.g. `example.com`)
   - **Path**: *(empty)*
   - **Type**: `HTTP`
   - **URL**: `traefik.kube-system.svc.cluster.local:80` (or `traefik.ingress.svc.cluster.local:80`)
   - **Additional Settings** > **HTTP Settings**:
     - **HTTP Host Header**: *(Leave blank)* — this preserves the client's original host header (e.g. `chat.homelab.<domain>`) so Traefik can route it.

### 2. Cloudflare Zero Trust Access Policy

1. In **Access** > **Applications**, add a **Self-Hosted Application**:
   - **Application Name**: `Homelab Wildcard`
   - **Application Domain**: `*.homelab.<domain>`
2. Define an **Access Policy** (e.g. Action: `Allow`, Include: `Emails` or `Email Domain`).

### 3. In-Cluster Deployment

1. Create the `cloudflared` namespace and tunnel token secret:
   ```bash
   kubectl create namespace cloudflared
   kubectl create secret generic cloudflared-token \
     --from-literal=token="<your-tunnel-token>" \
     -n cloudflared
   ```
2. Apply the declarative tunnel manifests:
   ```bash
   kubectl apply -k k8s/cloudflared/
   ```
3. Set your Traefik ingress service type to `ClusterIP`:
   ```bash
   kubectl patch svc traefik -n kube-system -p '{"spec": {"type": "ClusterIP"}}'
   ```
4. Deploy the core service Ingress definitions with template substitution (substitutes `k8s.domain` from `config.yaml`):
   ```bash
   devops k8s apply k8s/ingress/ingress-routes.yaml --template
   ```
   Or preview the rendered manifests before applying:
   ```bash
   devops k8s render k8s/ingress/ingress-routes.yaml
   ```

## Directory Structure

```
k8s/
├── kustomization.yaml        # Root kustomize: applies namespaces, cloudflared, registry, Grafana dashboard ConfigMaps
├── namespaces.yaml           # Namespace definitions (argocd, monitoring, otel, llm, cloudflared)
├── cloudflared/
│   ├── kustomization.yaml    # Kustomize overlay for Cloudflare Tunnel
│   ├── deployment.yaml       # Multi-replica non-root cloudflared deployment
│   ├── networkpolicy.yaml    # Network isolation for tunnel ingress and egress
│   └── secret.example.yaml   # Token secret template and creation instructions
├── ingress/
│   ├── kustomization.yaml    # Kustomize overlay for cluster ingress routes
│   ├── traefik-values.yaml   # Traefik Helm values with ClusterIP service type
│   └── ingress-routes.yaml   # Ingress rules for chat, ai, grafana, argocd, prometheus, qdrant
├── argocd/
│   ├── kustomization.yaml    # Kustomize overlay for ArgoCD
│   ├── namespace.yaml        # argocd namespace
│   └── values.yaml           # Helm values for argo/argo-cd
├── monitoring/
│   ├── kustomization.yaml    # Kustomize overlay for monitoring: namespace, NetworkPolicy, Service aliases, dashboards
│   ├── namespace.yaml        # monitoring namespace
│   ├── networkpolicy.yaml    # Default perimeter for the monitoring namespace
│   ├── service-aliases.yaml  # Alias Services for Prometheus and Grafana
│   ├── dcgm-exporter-values.yaml # Helm values for nvidia/dcgm-exporter (GPU metrics)
│   ├── grafana-values.yaml   # Helm values for grafana/grafana (datasources, dashboard sidecar)
│   ├── k8s-monitoring-values.yaml # Helm values for grafana/k8s-monitoring (Alloy, kube-state-metrics, node-exporter, and gateway monitors)
│   ├── prometheus-operator-crds-values.yaml # Helm values for prometheus-community/prometheus-operator-crds (ServiceMonitor and other monitoring.coreos.com CRDs)
│   ├── prometheus-values.yaml # Helm values for prometheus-community/prometheus (server only)
│   └── dashboards/
│       ├── kustomization.yaml # configMapGenerator: sidecar-labelled ConfigMaps for six dashboards
│       ├── k8s-views-global.json, k8s-views-pods.json # ConfigMap grafana-k8s-global-dashboards
│       ├── k8s-views-nodes.json, k8s-views-namespaces.json # ConfigMap grafana-k8s-node-dashboards
│       ├── devops-cli.json   # devops-cli commands, reviews, RAG and spend (grafana-devops-cli-dashboards)
│       ├── ai-spend.json     # AI spend and LLM usage (grafana-devops-cli-dashboards)
│       ├── project-metrics.json # Project & engineering velocity, release cadence and CI pass rates (grafana-devops-cli-dashboards)
│       ├── llm-stack.json    # LiteLLM gateway and GPUs; not provisioned, reaches Grafana through sync
│       ├── otel-collector.json # The collector's own telemetry; not provisioned, reaches Grafana through sync
│       └── prometheus-server.json # The Prometheus server; not provisioned, reaches Grafana through sync
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
│   └── gateway/              # LiteLLM gateway: Deployment, routing ConfigMap, NodePort Service, NetworkPolicy
└── README.md                 # This file
```
