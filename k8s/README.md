# k8s/ — Local Kubernetes Infrastructure & LLM Stacks

Kustomize + Helm-based configurations for deploying infrastructure management (`infra`) and local AI/LLM (`llm`) stacks to the devcontainer's minikube cluster.

## Stacks Overview

| Stack | Components | Namespaces | Default Ports |
| :--- | :--- | :--- | :--- |
| **`infra`** *(Default)* | ArgoCD (backed by Valkey), Argo Workflows controller, Grafana k8s-monitoring (Alloy + kube-state-metrics + node-exporter), Prometheus server, Grafana, Alertmanager, Grafana Pyroscope, NVIDIA DCGM Exporter, OpenTelemetry Collector, Grafana Tempo | `argocd`, `argo-workflows`, `monitoring`, `otel` | `8080` (ArgoCD), `8030` (Grafana), `8090` (Prometheus), `4040` (Pyroscope), `3200` (Tempo) |
| **`llm`** | Ollama (per-VRAM-tier DaemonSets), LLM Gateway (LiteLLM), Open-WebUI, Qdrant Vector DB, Valkey Cache | `llm` | `11434` (Ollama), `3000` (WebUI), `6333` (Qdrant), `6379` (Valkey) |
| **`logging`** | Loki, Fluent Bit (pod logs shipped from `infra` stack's Alloy) | `logging` | `3100` (Loki) |
| **`gitea`** | Gitea: the internal forge and container registry ([Gitea](#gitea)) | `gitea` | `3000` (Gitea HTTP, in the cluster) |
| **`all`** | All components from the stacks above, and the `devops` stack | `argocd`, `argo-workflows`, `monitoring`, `otel`, `llm`, `logging`, `gitea`, `devops` | All ports above |

Register each manifest, Helm release and post-Helm step that runs in the cluster in `_MANIFESTS_BY_STACK`, `_HELM_RELEASES_BY_STACK` or `_POST_HELM_BY_STACK` (`src/devops_cli/commands/k8s/stack_lifecycle.py`), so that `devops k8s deploy-stack --stack all` deploys it with the `infra`, `llm`, `logging`, `devops` and `gitea` stacks. deploy-stack applies a file of `_MANIFESTS_BY_STACK` with `kubectl apply -f` and a kustomization directory with `kubectl apply -k`.

## Prerequisites

- minikube running (`minikube status` or auto-started by `devops devcontainer post-start`)
- kubectl and helm on PATH (installed by devcontainer features)
- standard Kubernetes context configuration (the CLI uses `$KUBECONFIG` or defaults to `~/.kube/config`)

Kubernetes supports `kubectl` within one minor version of the API server. The `tools.lock` file tracks a current `kubectl` release. The homelab cluster runs Kubernetes 1.31 (`v1.31.4+k3s1`), which stays outside the supported skew range until dan-petty/homelab#3 lands. We do not pin `kubectl` to 1.31 or 1.32, because both versions are end of life and the devcontainer minikube runs a current release.

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
# Shell in a pod from the UI: open its Application, select the pod, then the Terminal tab

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
# Ollama REST API of the fast tier (a speed Service; see GPU Placement: Ollama tiers)
kubectl -n llm port-forward svc/ollama-fast 11434:11434

# Open-WebUI Web Interface
minikube service open-webui -n llm --url

# Qdrant Vector Database HTTP API. It requires the key of llm/qdrant-api-key (see Cluster Secrets).
minikube service qdrant -n llm --url

# Valkey In-Memory Cache: Open WebUI's state. It requires the password of llm/valkey-auth (see Cluster Secrets).
kubectl -n llm exec -it svc/valkey -c valkey -- sh -c 'VALKEYCLI_AUTH="$VALKEY_PASSWORD" valkey-cli ping'

# Valkey Run Index (deployed by deploy-stack; see Cluster Secrets for its password):
# benchmark and evaluation runs shared by workstations. Its password Secret comes from the keyring (see Cluster Secrets),
# then point devops-cli at it through its NodePort.
devops k8s push-secrets --only llm/valkey-runs-auth
devops ai runs connect

# LLM Gateway: authenticated OpenAI-compatible API for every Ollama model
minikube service llm-gateway -n llm --url
```

### LLM Gateway (`llm-gateway`)
The LiteLLM gateway is the single entry point to every inference server. It serves the virtual models `devops-chat`, `devops-coder`, `devops-reasoning` and `devops-review`, plus models by name (`qwen3.8:27b`, `gemma4:31b`, `deepseek-r1:70b`, `qwen3-embedding:0.6b`). It moves a prompt too long for `devops-chat` to `devops-coder`, then `devops-reasoning`, before calling any backend. It falls back from an unavailable `devops-coder` to `devops-reasoning` before the small Ollama model, and rejects requests without its master key. `devops k8s deploy-stack` writes the key (`llm/llm-gateway-secrets`, starting with `sk-`) from the keyring before the gateway starts, adopting a live key the keyring lacks and generating one where neither has it; `devops k8s push-secrets --only llm/llm-gateway-secrets` does the same alone (see Cluster Secrets).

The routing config is `llm/gateway/config.yaml`. LiteLLM reads it only at start. The gateway kustomization (`llm/gateway/kustomization.yaml`) generates ConfigMap `llm-gateway-config-<hash>` from that file, and writes the name into the Deployment. When the config changes, the name and the pod template change, and Kubernetes rolls the gateway onto the new config. Argo CD's `llm` Application renders the kustomization when it syncs, and `devops k8s deploy-stack --stack llm` applies it with `kubectl apply -k llm/gateway`. Thus a config change needs no `kubectl rollout restart` (#1929). Argo CD prunes the ConfigMap of the old config. Without Argo CD, that ConfigMap stays until `teardown-stack` deletes the namespace.

A workstation reaches the gateway through the Cloudflare tunnel, and the Cloudflare edge cuts a request that has no data for 125 s (#2365). The CLI therefore streams every OpenAI-compatible chat call, and the gateway writes an SSE comment (`: ping`) into a streamed reply that has no data for 30 s (`litellm_settings.sse_keepalive_ping_interval_seconds`), also before its first token. Thus a long prefill, queue or reasoning does not end the call. A ping sends the status line before the gateway has routed the call, so a call whose first token comes after the first ping has no `x-litellm-*` response headers, and its spend-ledger row names no serving backend. A failure after the first ping comes as an SSE error frame under status 200, and the client reports it as the HTTP status that the frame names.

The Service is a NodePort that Kubernetes assigns; find it with `kubectl -n llm get svc llm-gateway`, then call the API from any node address:
```bash
KEY=$(kubectl -n llm get secret llm-gateway-secrets -o jsonpath='{.data.master-key}' | base64 -d)
curl -H "Authorization: Bearer $KEY" http://<node>:<node-port>/v1/models
```
These groups route reviews, embeddings and background work:

- `devops-review` spreads one model name over three Ollama tiers: `qwen3-coder:30b` on `ollama-48gib-fast` and `ollama-64gib-standard`, and `gpt-oss:20b` on `ollama-16gib-fast`. The router sends each request to the deployment with the fewest requests in flight (`least-busy`), and pre-call checks keep a prompt off any deployment whose window it exceeds. No deployment is capped with `max_parallel_requests`: LiteLLM waits on the cap only after routing, so queued requests pile up behind it while larger servers idle, and the backends queue excess requests themselves.
- Ollama models are also served under their own names: `qwen3.8:27b`, `gemma4:31b`, `deepseek-r1:70b`, and the embedding model `qwen3-embedding:0.6b`. An embedding group configures `model_info.mode: embedding` so health checks embed rather than generate.
- `qwen3-embedding:0.6b` has one deployment on each serving tier, and LiteLLM's `order` sets which the router tries first. The gateway routes the embedding group with `simple-shuffle` across order 1 deployments (#2027). Order 1 is `ollama-48gib-fast` and `ollama-64gib-standard`, which embed a 32-chunk RAG batch in under 5 s beside their chat model. Order 2 is `ollama-16gib-fast`, whose chat model leaves no VRAM for the embedder, and `ollama-48gib-slow`, which takes 12 to 30 s. The router sends a request to order 2 only when every order 1 deployment fails. Each deployment sets `num_ctx` to `CONST_RAG_MAX_CHUNK_TOKENS` (8,192), so the largest RAG chunk fits. With its 32,768-token default, the embedder takes 5.2 GB, not 2.9 GB, on `ollama-64gib-standard`. These tiers keep two models loaded, so the embedder stays beside the chat model where both fit, and each must hold the model: `kubectl -n llm exec ds/<tier> -c ollama -- ollama pull qwen3-embedding:0.6b`.
- `qwen3-coder:30b` and `gpt-oss:20b` each pin one of `devops-review`'s models: the group copies that model's `devops-review` deployments and weights, with no `max_input_tokens` and no fallback, so a review measured on one model is routed as the pool routes it.
- `devops-background` is the background tier's one generation model: `qwen3.8:27b` on `ollama-48gib-slow`. That tier serves one request at a time, so it is in no interactive or review pool, where background work would queue in front of review calls. It keeps its embedding model and `qwen3.8:27b` loaded together and is sent no other model. In-cluster services (`k8s/devops/` such as `roadmap-service` and cluster jobs) and `devops-review` fallback reach it; the pinned groups have no fallback. The client streams the call and the gateway's pings keep it open, so the client reads the reply of a `devops-review` call that falls back to this tier. Use it for `devops review path --watch`, `devops ai pipeline`, `devops ai agents` and `devops ai analyze` through environment overrides, never in workstation `config.yaml`, so no interactive run lands on it. Set `DEVOPS_CLI_AI_MAX_RETRIES=1`. The gateway stops a call when the tier sends no token for 1,100 s, and does not retry it. The client retries a call that fails or times out before its reply starts in its HTTP transport, the single retry layer, `ai.max_retries + 1` times, and each retry waits for the same single slot. A call that fails after its reply starts is not retried. With `1` a call is sent at most two times; `0` does not stop retries, because the transport then makes five attempts:
  ```bash
  DEVOPS_CLI_AI_MAX_RETRIES=1 DEVOPS_CLI_AI_TASK_ANALYSIS_MODEL=devops-background \
    DEVOPS_CLI_AI_TASK_COMPOSE_MODEL=devops-background devops review path src --watch --concurrency 1
  DEVOPS_CLI_AI_MAX_RETRIES=1 DEVOPS_CLI_AI_TASK_CHAT_MODEL=devops-background devops ai pipeline "<goal>"
  DEVOPS_CLI_AI_MAX_RETRIES=1 DEVOPS_CLI_AI_MODEL=devops-background devops ai agents   # likewise devops ai analyze
  ```

Recheck the `devops-review` weights whenever a backend, model or node changes. `devops ai gateway tune` measures each deployment on its own, from an ephemeral Python container attached to the gateway pod (`kubectl debug`), so each backend is measured over the gateway's own network path. It recommends each weight as capacity (fixed-length tokens per second) divided by cost (the tokens the model writes per request), and lists each backend's GPUs and engine. It changes nothing; copy the recommended weights into `litellm_params.weight`:
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
      context_window: 16384   # review page size; every devops-review backend holds at least 48K
    chat:                # devops ai chat
      provider: gateway
      model: devops-coder
    embedding:
      provider: gateway
      model: qwen3-embedding:0.6b
```
Provider `gateway` always sends to `ai.gateway_url`, even when `ai.api_base_url` is set for another provider. To send one task to a different gateway, set `api_base_url` on that task.

Open WebUI uses the same key: on a fresh install it connects to the gateway automatically, and it sends its RAG embeddings to the gateway's `qwen3-embedding:0.6b`. An existing installation keeps the connections and the document settings stored in its database. Add `http://llm-gateway.llm.svc.cluster.local:4000/v1` under Admin Panel > Settings > Connections, and replace an Ollama connection to a tier that does not serve with `ollama-fast` or `ollama-standard`. Under Admin Panel > Settings > Documents, set the embedding engine to OpenAI, with the gateway URL, the master key and `qwen3-embedding:0.6b`.

### GPU Placement: Ollama tiers
Ollama runs as one DaemonSet per total-VRAM tier (`ollama-16gib` … `ollama-128gib`, `llm/profiles/ollama-profiles.yaml`), each behind its ClusterIP Service `ollama-<n>gib`. The gateway reaches the tiers through aliases of those Services, `ollama-16gib-fast`, `ollama-48gib-fast`, `ollama-48gib-slow` and `ollama-64gib-standard` (`llm/gateway/config.yaml`).

The speed Services `ollama-fast`, `ollama-standard` and `ollama-slow` (`llm/profiles/services.yaml`) name no VRAM size. Clients of Ollama's native API use them: `ollama-fast` is the `ollama-ingress` backend and the CLI's default Service (`devops k8s port-forward`, `configure-urls`). Open WebUI connects to `ollama-fast` and `ollama-standard`, and sends its RAG embeddings to the gateway. When a host changes, change the selector of the speed Service. Its clients then follow with no edit. [llm/profiles/README.md](llm/profiles/README.md) describes the profiles and their Services.

A tier's pods schedule only on a node whose labels satisfy the tier's required node affinity. Every tier requires `nvidia.com/gpu.total-vram-gib` to be one of its values, and three also require `nvidia.com/gpu.architecture`. `nvidia.com/gpu.present=true` marks a GPU node, and `deploy-stack` treats a node with `nvidia.com/gpu` capacity above zero as one too.

| Tier | `nvidia.com/gpu.total-vram-gib` | `nvidia.com/gpu.architecture` | Serves |
| :--- | :--- | :--- | :--- |
| `ollama-16gib` | `16Gi`, `20Gi` | any | yes |
| `ollama-24gib` | `24Gi`, `28Gi` | `pascal`, `maxwell`, `kepler` | no |
| `ollama-32gib` | `32Gi`, `36Gi`, `40Gi`, `44Gi` | any | no |
| `ollama-48gib` | `48Gi`, `52Gi`, `56Gi`, `60Gi` | `ada-lovelace`, `ampere`, `blackwell`, `hopper` | yes |
| `ollama-48gib-slow` | `48Gi`, `52Gi`, `56Gi`, `60Gi` | `pascal`, `maxwell`, `kepler` | yes |
| `ollama-64gib` | `64Gi`, `68Gi` | any | yes |
| `ollama-72gib` | `72Gi`, `76Gi`, `80Gi`, `84Gi`, `88Gi`, `92Gi` | any | no |
| `ollama-96gib` | `96Gi`, `100Gi` … `124Gi` in steps of 4 | any | no |
| `ollama-128gib` | `128Gi` | any | no |

**Serves** says whether a node of the cluster satisfies the tier, so that the tier has a pod. Every client that names an Ollama Service names one that selects a serving tier: the CLI defaults, the `ollama-ingress` backend, Open WebUI, the gateway's `api_base` targets and the devcontainer's `ollama.endpoint`. `tests/test_k8s_llm_gateway.py` checks this against the column. When a host goes offline or a tier gets a node, change the column. The test then names each client to move.

**What sets the labels.** The cluster's node-provisioning automation, which lives outside this repository, sets `nvidia.com/gpu.present` and `nvidia.com/gpu.architecture` on every GPU node. It sets `nvidia.com/gpu.total-vram-gib` only on a node with more than one GPU, as the sum of its GPUs' memory rounded to the nearest whole GiB. GPU Feature Discovery labels per-GPU memory and the GPU count, not a total. So a single-GPU node gets no total, and a multi-GPU total can come out as a value no tier lists, such as `47Gi`. Set the label by hand, with a value from the table:

```bash
kubectl label node <node> nvidia.com/gpu.total-vram-gib=<N>Gi --overwrite
```

`deploy-stack --stack llm` reads the nodes once, right after it checks the cluster is reachable, and warns about each GPU node no tier accepts: the missing or unaccepted `total-vram-gib` with the command above, or an `architecture` outside the accepted ones. If no node satisfies any tier, it says no Ollama pod will schedule, and if it cannot read the nodes it says it could not check the labels. It also warns on an Argo CD-managed cluster. It never stops the deploy, since the stack's other workloads need no GPU label. The accepted values are read from `ollama-profiles.yaml`, so a tier changed there is checked with no other edit.

The gateway's policy `llm-gateway-perimeter` (`llm/gateway/networkpolicy.yaml`) is applied with the llm manifests, by `deploy-stack` or Argo CD's `llm` Application. It admits TCP 4000 from any source, since LiteLLM rejects a request without the master key, and limits the gateway's egress to the pods labelled `llm.devops.io/provider: ollama` on 11434 and kube-system DNS on port 53.

The cache Valkey's policy `valkey-perimeter` (`llm/valkey.yaml`) admits Open WebUI on TCP 6379 and the `monitoring` namespace on the exporter port 9121. It allows no egress, and `llm-default-perimeter` leaves the Valkey pods out. Valkey requires the password of `llm/valkey-auth` (see Cluster Secrets). Open WebUI sends it in its Redis URL, and Valkey reads it from a quoted config line. A typed value must therefore use only letters, digits, `-`, `.`, `_` and `~`. The gateway and Portkey use no Valkey: the gateway config turns on no cache, and Portkey reads a cache only from `REDIS_CONNECTION_STRING`, which is not set.

The cache Valkey keeps at most 1536 MiB of data (`--maxmemory`), three quarters of its 2048Mi limit. The rest of the limit holds fragmentation and Valkey's own overhead. At the bound, Valkey refuses writes and evicts no key (`--maxmemory-policy noeviction`). Open WebUI keeps its session pools and token revocations there, and an evicted revocation makes a signed-out token valid again. The run index (`llm/valkey-runs.yaml`) uses the same policy with a bound of 512 MiB.

Qdrant requires the key of `llm/qdrant-api-key` (see Cluster Secrets) on every REST and gRPC request. Only `/`, `/healthz`, `/readyz`, `/livez` and the files of its web UI need no key. The qdrant container reads the key as `QDRANT__SERVICE__API_KEY` through `env` in `llm/values-qdrant.yaml`. Open WebUI is the only workload under `k8s/` that names the Qdrant Service, and it sends the key as `QDRANT_API_KEY`. Alloy scrapes `/metrics` with the key as a bearer token, and devops-cli sends keyring `qdrant_api_key`, which the push keeps equal to the Secret. `tests/test_k8s_qdrant_security.py` fails on a top-level key of `llm/values-qdrant.yaml` that the pinned chart (`tests/fixtures/charts/qdrant/`) does not declare, because Helm drops such a key with no error.

Every tier runs ollama as UID and GID 10001, which no host login account uses, with RuntimeDefault seccomp, no privilege escalation, all capabilities dropped and a read-only root filesystem; `/tmp` is an emptyDir. `HOME` is `/home/ollama`, so the key and `models/` stay in the hostPath `/var/lib/ollama` on each GPU node, mounted at `/home/ollama/.ollama`. `fsGroup` does not apply to a hostPath volume, so the initContainer `own-model-directory` gives that directory to 10001 at every start (`chown -R`). It runs as root with `CAP_CHOWN` alone, no privilege escalation and a read-only root filesystem, and exits before ollama starts. It is the one exception to kube-linter's `run-as-non-root` in `ollama-profiles.yaml`, recorded in the manifest's header rather than suppressed with an ignore annotation.

Inference workloads pull models directly and are reachable inside the cluster through the gateway.

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

The `monitoring` perimeter (`monitoring/networkpolicy.yaml`) admits Grafana, Prometheus, Alloy and Pyroscope traffic from three places: the namespace's own pods, the `otel` namespace, and Traefik in `kube-system`. Argo CD's `monitoring` Application applies it on a cluster it manages. Without Argo CD, `devops k8s deploy-stack --stack infra` (or `all`) applies it with the `monitoring` kustomization before any chart installs into the namespace, and `teardown-stack` removes it with the namespace. External clients come in through the Cloudflare tunnel, and `cloudflared` forwards only to Traefik. The perimeter names no address range. The cluster's policy engine, kube-router, matches an ingress `ipBlock` against pod addresses, so `0.0.0.0/0` or a private range would admit every pod in the cluster. How each way of reaching the stack gets through:

- `devops k8s port-forward` works wherever the pods run: `kubectl port-forward` enters the pod's own network namespace, and no policy applies.
- `--addressing fqdn` goes through Traefik.
- `--addressing proxy` writes `k8s://` addresses that the API server proxies from the control-plane node's host network. kube-router admits host-network traffic only to pods on the same node, so in a namespace behind a perimeter (Grafana, Prometheus and Pyroscope in `monitoring`, and the `llm` Services), a Service answers this way only while its pod runs on the control-plane node, and the pods on local-path volumes keep off that node (Local-Path Volume Placement, below). So `configure-urls --addressing proxy` sends one GET through the API server for each address. It writes only the addresses that the Service answers. When the API server cannot dial the Service, it writes nothing for that key and names `fqdn` and port-forward.

## Scrape Ownership

Alloy, run by the `k8s-monitoring` release (`monitoring/k8s-monitoring-values.yaml`), scrapes every target but two and remote-writes to the Prometheus server: the kubelet, cAdvisor, kube-state-metrics, node-exporter, the `argocd` (`controller`, `server`, `repoServer`, and `redis` exporter), `argo-workflows` (the workflow controller), `llm-gateway`, `pyroscope` and `qdrant` ServiceMonitors, CoreDNS (`clusterMetrics.kubeDNS`), the pods annotated for scraping (`annotationAutodiscovery`), and the Alloy collectors, Grafana, Loki, Tempo and the DCGM exporter (`integrations`). The Prometheus server scrapes only itself and the OpenTelemetry Collector (#1130). These monitoring components run outside k8s-monitoring:

| Component | Owner | Reason |
| :--- | :--- | :--- |
| Prometheus server and Alertmanager | Their own `prometheus` release (`monitoring/prometheus-values.yaml`) | k8s-monitoring ships collectors, not a metrics store or an alert router. Alloy writes to this server, which evaluates the alert rules and sends alerts to Alertmanager. The server scrapes itself, and Alloy scrapes Alertmanager through its pod annotations |
| Grafana | Its own `grafana` release (`monitoring/grafana-values.yaml`) | k8s-monitoring does not deploy Grafana; its `grafana` integration scrapes Grafana's pod (#1131) |
| Loki | Its own `loki` release, in the `logging` stack (`logging/loki-values.yaml`) | Loki belongs to the logging stack, so k8s-monitoring's Loki integration scrapes it only where that stack runs |
| Pyroscope server | Separate `pyroscope` release (`monitoring/pyroscope-values.yaml`); collection: k8s-monitoring `profiling` | k8s-monitoring collects profiles (`profiling` in `monitoring/k8s-monitoring-values.yaml`, sent to `destinations.localPyroscope`); it does not deploy the server that stores profiles, and it scrapes Pyroscope through the chart's own ServiceMonitor (#1131, #1134) |
| Trace backend (Tempo) | Its own `tempo` release (`otel/tempo-values.yaml`) | k8s-monitoring's Tempo integration scrapes Tempo, which its own chart deploys in `otel`. The collector's trace exporter has a Tempo to reach when the collector starts: `deploy-stack` installs `tempo` before `otel-collector`, and the `cluster` app-of-apps syncs the `otel-collector` Application in sync wave 1, after `tempo` (#409) |
| dcgm-exporter | Its own `dcgm-exporter` chart (`monitoring/dcgm-exporter-values.yaml`) | k8s-monitoring's dcgm-exporter integration scrapes the exporter but ships none, so the chart deploys it on every GPU node; the chart's own ServiceMonitor stays off |
| otel-collector | Its own `otel-collector` release (`otel/values.yaml`), scraped by the Prometheus server's `kubernetes-pods` job, which keeps only namespace `otel` | devops-cli exports delta temporality, and Alloy's `deltatocumulative` is experimental only, so k8s-monitoring cannot replace the collector (#1132). The server scrapes it, not Alloy, so the collector's export failures stay visible when Alloy is what fails |
| prometheus-operator-crds | Its own release, installed first | The `argocd`, `argo-workflows`, `llm-gateway`, `pyroscope` and `qdrant` ServiceMonitors need the `monitoring.coreos.com` CRDs, which k8s-monitoring 4.x no longer ships |

cloudflared, Traefik, Alertmanager, roadmap-service and `llm/valkey` (`redis-exporter` sidecar on port 9121) are found by annotation autodiscovery (#1130, #551), through the `prometheus.io/*` annotations their plain manifests carry, each with the pod's `app.kubernetes.io/name` as its job; CoreDNS comes through `clusterMetrics.kubeDNS`.

`devops prometheus targets` reads the server's `/api/v1/targets`, so it lists only the server's two jobs; Alloy's targets appear in Prometheus as their `up` series.

## Grafana Dashboards

Dashboards live in `monitoring/dashboards/`. Its `kustomization.yaml` generates four ConfigMaps labelled `grafana_dashboard: "1"`, and the Grafana dashboard sidecar (`monitoring/grafana-values.yaml`) loads every ConfigMap with that label:

| ConfigMap | Dashboards |
| :--- | :--- |
| `grafana-k8s-global-dashboards` | `k8s-views-global.json`, `k8s-views-pods.json` |
| `grafana-k8s-node-dashboards` | `k8s-views-nodes.json`, `k8s-views-namespaces.json` |
| `grafana-devops-cli-dashboards` | `devops-cli.json`, `ai-spend.json`, `project-metrics.json` |
| `grafana-stack-dashboards` | `sre-service.json`, `ingress-tunnel.json`, `llm-stack.json`, `otel-collector.json`, `prometheus-server.json`, `pyroscope.json`, `nvidia-dcgm.json`, `coredns.json` |

On a cluster Argo CD manages, its `monitoring` Application applies them; the root kustomization leaves them out, so the `base` Application does not own them as well. Without Argo CD, `devops k8s deploy-stack --stack infra` (or `all`) applies the `monitoring` kustomization, which lists the namespace's perimeter and `dashboards`, right after the root kustomization creates the `monitoring` namespace, and `teardown-stack` removes them with that namespace. Grafana holds these dashboards as provisioned and refuses to save over them, so change the JSON file and deploy again. To provision another dashboard, add it to a generator entry; each ConfigMap must stay under the 262,144 bytes kubectl's last-applied annotation allows.

The AI spend dashboard (`ai-spend.json`) prices local savings in Prometheus. It multiplies the tokens that a local model ran (`devops_cli_ai_tokens_total{local="true"}`) by its hidden constant `reference_price_usd_per_token`, a PromQL vector of one price for each operation and token type. Each price is genai-prices' price of the default reference model of its operation (`gpt-4o` for chat, `text-embedding-3-small` for embeddings), so every process that sends tokens, and every time range in the retention window, is priced at one reference. A recording rule has samples only from its first evaluation, so the dashboard holds the prices and Prometheus records none. The savings queries also count the series from before the `local` label (#1672) that the gateway served, because the gateway serves only local models, and they count a series without the `operation` label as chat. Remove that mapping when `count(last_over_time(devops_cli_ai_tokens_total{local=""}[30d]))` is empty. `tests/test_k8s_monitoring_dashboards.py` fails when a price of the dashboard differs from genai-prices.

The stack dashboards chart the cluster workloads and infrastructure services:

| Dashboard | Exporter / Sources | How Prometheus / Loki gets its series |
| :--- | :--- | :--- |
| `sre-service.json`, "SRE Service & Logs" (`devops-sre-service`) | cAdvisor container CPU, memory, network packets/drops, Loki service logs, and Pyroscope flamegraphs | Metrics scraped by Alloy from cAdvisor/Kubelet and Kube State Metrics; logs pushed to Loki via Alloy or OpenTelemetry collector; continuous profiles queried from Pyroscope datasource |
| `ingress-tunnel.json`, "SRE / Ingress & Cloudflare Tunnel" (`devops-ingress-tunnel`) | Traefik ingress metrics (port 9100) and Cloudflare Tunnel metrics (port 2000) | Alloy's annotation autodiscovery (`annotationAutodiscovery` in `monitoring/k8s-monitoring-values.yaml`), through the pods' `prometheus.io/*` annotations; network policy allows monitoring to scrape both ports |
| `llm-stack.json`, "LLM Gateway & GPUs" (`devops-llm-stack`) | LiteLLM's Prometheus callback on the gateway (`/metrics/`), the NVIDIA DCGM exporter on every GPU node, and Qdrant's `/metrics` on port 6333 | The `llm-gateway` ServiceMonitor (`llm/gateway/servicemonitor.yaml`), the `dcgm-exporter` integration (`integrations` in `monitoring/k8s-monitoring-values.yaml`), and the `qdrant` ServiceMonitor (`metrics.serviceMonitor` in `llm/values-qdrant.yaml`, authenticating with the `qdrant-api-key` Secret), run by Alloy, which remote-writes to the server |
| `otel-collector.json`, "OpenTelemetry Collector" (`devops-otel-traces`) | The collector's own telemetry on port 8888 | The server's `kubernetes-pods` job, which keeps only namespace `otel`, through the `prometheus.io/scrape` and `prometheus.io/port` pod annotations in `otel/values.yaml`; not through Alloy, whose annotation autodiscovery skips `otel`, so the collector's export failures stay visible when Alloy is what fails |
| `prometheus-server.json`, "Prometheus Server" (`devops-prometheus-server`) | The Prometheus server's own `/metrics`, and `up` for every target | The server's `prometheus` job, which scrapes itself (`scrapeConfigs.prometheus` in `monitoring/prometheus-values.yaml`) |
| `pyroscope.json`, "Continuous Profiling / Pyroscope Flamegraphs" (`devops-pyroscope`) | Grafana Pyroscope continuous profiling (CPU, memory, goroutines) | Continuous profiles collected by k8s-monitoring's `profiling` feature (`alloy-profiles` DaemonSet, eBPF `targetingScheme: all` and `pprof`, in `monitoring/k8s-monitoring-values.yaml`) and sent to `destinations.localPyroscope` (#1134) |
| `coredns.json`, "CoreDNS" (`devops-coredns`) | CoreDNS metrics on port 9153 (`coredns_dns_*`, `coredns_cache_*`, `coredns_proxy_*`) | Alloy's `clusterMetrics.kubeDNS` job (`job="integrations/kubernetes/kube-dns"` in `monitoring/k8s-monitoring-values.yaml`) (#822) |

```bash
devops grafana dashboards lint k8s/monitoring/dashboards  # also catches a uid two files share
devops grafana dashboards sync                            # posts every file in the directory
```
`sync` exits 1 if any dashboard failed. It reports the provisioned dashboards as skipped, not failed.

`tests/test_stack_dashboards.py` checks every query in `llm-stack.json`, `otel-collector.json`, `prometheus-server.json`, `coredns.json`, `ingress-tunnel.json`, `k8s-views-global.json`, `k8s-views-namespaces.json` and `k8s-views-nodes.json` against captures of these exporters in `tests/fixtures/metrics/` (filtered by `tests/fixtures/k8s_monitoring/cluster_metrics/` and `includeMetrics` for cAdvisor, kube-state-metrics and the kubelet): each series it selects, each label it matches or groups by, and the scrape in the table. No query falls back to a constant such as `or vector(0)`, so a panel without data reads "No data" rather than zero, and a panel drawn against a limit extends its axis to that limit. The gateway's failure, cooldown and fallback panels, Qdrant's REST request rate and latency panels, and the collector's span export failures (`noValue: "none recorded"`) stay empty until the first such event.

## Log and Metric Retention

Logs and metrics are kept for 30 days:

| Store | Kept for | Deleted by | Volume |
| :--- | :--- | :--- | :--- |
| Loki (`logging/loki-values.yaml`) | `limits_config.retention_period: 720h` | The compactor, which applies retention only with `compactor.retention_enabled`, every 10 minutes | `storage-loki-0`, 20Gi |
| Prometheus (`monitoring/prometheus-values.yaml`) | `server.retention: 30d` | The TSDB, by age. `server.retentionSize: 16GB` only guards the disk and sits well above 30 days of samples | `prometheus-server`, 20Gi |

Logs leave Loki only by age: `limits_config.deletion_mode: disabled` closes the log delete API, which would otherwise accept requests without credentials while `auth_enabled` is false.

Both volumes use the `local-path` class. It keeps a volume on its node's root filesystem, does not hold the volume to its claimed size, and cannot expand a claim in place. Loki's claim comes from its StatefulSet's `volumeClaimTemplates`, which Kubernetes does not let an upgrade change, so a new `singleBinary.persistence.size` needs the StatefulSet deleted with `--cascade=orphan` and the volume rebound to the new claim before the upgrade.

Two alerts in `serverFiles.alerting_rules.yml` (`monitoring/prometheus-values.yaml`) warn before a volume fills:

- `LogOrMetricVolumeDiskLow`: the root filesystem of the node holding `storage-loki-0` or `prometheus-server` has had less than 10% free for 30 minutes.
- `PrometheusNearRetentionSizeCap`: the TSDB has used over 80% of `server.retentionSize` for an hour, before the cap would delete blocks younger than 30 days.

They route like every other rule (Alerting, below), and are listed there with the rest.

Loki's compactor retention takes effect once #550's Loki migration has been applied, a step a person runs: the volume rebind above, then the Loki upgrade. Until then Loki deletes no logs by age. k8s-monitoring's Loki integration scrapes Loki wherever the logging stack runs (Scrape Ownership, above), and the migration only turns retention on; `LokiRetentionNotRunning` fires if the compactor stops applying it.

## Alloy Metrics Write-Ahead Log

The `alloy-metrics` collector (`collectors.alloy-metrics` in `monitoring/k8s-monitoring-values.yaml`) keeps its write-ahead log at `alloy.storagePath`, `/var/lib/alloy`, on the volume of the claim template `alloy-wal`. A pod restart keeps the samples that Alloy buffered and did not send, for example while Prometheus is down. Alloy keeps unsent samples for up to 8 hours (`max_keepalive_time`) and truncates the log every 2 hours. At the 14 MB an hour that it writes, the log holds about 140 MB at most, and the claim asks for 1Gi. The claim uses the `local-path` class, which binds the volume on the node where the pod first runs. The pod's node affinity (`node-role.kubernetes.io/control-plane` `DoesNotExist`) keeps the pod and its volume off the control-plane node, whose root disk has the least free space.

The Alloy Operator, not Argo CD, makes the StatefulSet from the `Alloy` resource `k8s-monitoring-alloy-metrics` that Argo CD syncs. Kubernetes does not let an upgrade change `volumeClaimTemplates`, so after a change to the claim template the operator cannot upgrade the StatefulSet until the old StatefulSet is gone. When Argo CD has synced the change, a person runs these commands:

```bash
# The Alloy resource holds the new claim template.
kubectl -n monitoring get alloys.collectors.grafana.com k8s-monitoring-alloy-metrics \
  -o jsonpath='{.spec.controller.volumeClaimTemplates[*].metadata.name}'
# Delete the old StatefulSet and keep its pod.
kubectl -n monitoring delete statefulset k8s-monitoring-alloy-metrics --cascade=orphan
# The operator makes the StatefulSet again with the claim template.
kubectl -n monitoring get statefulset k8s-monitoring-alloy-metrics \
  -o jsonpath='{.spec.volumeClaimTemplates[*].metadata.name}'
# Delete the adopted pod, so that the StatefulSet makes a pod that mounts the volume.
kubectl -n monitoring delete pod k8s-monitoring-alloy-metrics-0
kubectl -n monitoring get pvc alloy-wal-k8s-monitoring-alloy-metrics-0
```

`--cascade=orphan` keeps the pod while the StatefulSet is gone, so the metrics stop only for the restart of the pod. The new StatefulSet adopts the pod but cannot replace it: Kubernetes does not let a pod's volumes change, so each update fails with `pod updates may not change fields other than ...`, and the claim stays `Pending`. The pod that the StatefulSet makes after the delete mounts the volume of `alloy-wal-k8s-monitoring-alloy-metrics-0`, and the claim binds on the node of that pod. The samples in the old pod's own filesystem are lost one time. The StatefulSet keeps its claims when it is deleted or scaled down, so the volume and its log stay.

## Local-Path Volume Placement

The StorageClasses `local-path` and `fast-nvme` use the local-path provisioner. It keeps a volume in a directory on the root filesystem of one node, and it binds the volume on the node where the first pod of the claim runs (`WaitForFirstConsumer`). The volume then keeps each later pod of the claim on that node. The root disk of the control-plane node is the smallest in the cluster, and it also holds the model store of the slow Ollama tier (GPU Placement, above). So each pod that mounts a claim has this required node affinity:

```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
            - key: node-role.kubernetes.io/control-plane
              operator: DoesNotExist
```

Kubernetes puts the label `node-role.kubernetes.io/control-plane` on each control-plane node, so the rule needs no label of its own. The affinity has an effect on a new volume and on a moved volume. A bound volume keeps its pod on its node.

`tests/test_k8s_local_path_placement.py` fails when a pod that mounts a claim has no such affinity, in a chart values file or in a manifest under `k8s/`. It also fails when an Argo CD Application installs a chart that the test does not know, because each chart keeps its claims and its affinity at different values. A pod that must stay on the control-plane node is in `CONST_K8S_CONTROL_PLANE_CLAIM_EXEMPTIONS` (`src/devops_cli/config/constants.py`), with its reason. Grafana (claim `grafana`), the Prometheus server (`prometheus-server`) and Loki (`storage-loki-0`) are in it, because their volumes are on the control-plane node, and with the affinity their pods cannot start. Move each volume as below, then remove its exemption and add the affinity to its values in one pull request.

`LocalPathNodeDiskHigh` (Alerting, below) warns when the root filesystem of a node that runs a pod on a `local-path` claim is over 85% used. At 85% the kubelet starts to delete unused images. Under DiskPressure it evicts pods, and a pod on a local-path volume cannot start on another node.

### Move a volume to another node

`devops k8s volume move <namespace>/<claim>` copies the data of a claim to a new volume on a worker node, and binds the claim to that volume. The workload stops while the copy runs. Move one volume at a time.

```bash
devops k8s volume move monitoring/grafana --plan
devops k8s volume move monitoring/grafana
devops k8s volume move logging/storage-loki-0 --to-node <worker-node>
```

`--plan` only reads, and prints each step with the real names. `--dry-run` makes no request, and prints the requests of a move. Without `--to-node`, the command moves a volume from the control-plane node to the worker node with the most free disk (`node.fs.availableBytes` in the kubelet's `/stats/summary`). A volume on a worker node moves only to the node that `--to-node` names. The command refuses a claim that is not `Bound`, a target on the control-plane node, a StatefulSet that deletes its claims when it scales down (`persistentVolumeClaimRetentionPolicy.whenScaled: Delete`), and the leftovers of an earlier move: the pods `<claim>-src` and `<claim>-dst` and the claim `<claim>-move`.

The move does these steps, and prints each one:

1. It pauses automated sync from the top down: `bootstrap`, `cluster`, then each Application that tracks the claim or the workloads that mount it (Pausing an Application, below). If it did not, self-heal would start the workload again during the copy.
2. It makes the claim `<claim>-move`, with the size and the class of the old claim, and the pod `<claim>-dst` on the target node. local-path binds the new volume on that node.
3. It scales the workloads that mount the claim to zero. It finds them from the volumes of the pod specs, not from labels. Then it starts the pod `<claim>-src`, which mounts the old claim read-only. Its volume keeps it on the old node, so one pod cannot mount the two claims.
4. It copies through the API server with GNU tar in `debian:trixie-slim`, which keeps the owners, the modes and the sparse files. When the exec stream stops (`connection reset by peer`), it empties the destination and copies one more time.
5. It compares the two sides: the number of entries, the number of files, the bytes of the regular files (not `du`, which counts directory blocks), a digest of the metadata (`%y %m %U:%G %P` of each entry) and a digest of the content. It stops at a difference.
6. It sets the two volumes to `Retain`, deletes the copy pods, saves the old claim as a JSON file in `k8s/volume-move/` under the data directory, and deletes the old claim. This is the point of no return.
7. It deletes `<claim>-move`, reserves its volume for the claim name (`claimRef`), and makes the claim again from the saved one, with `spec.volumeName`. It leaves out the annotation `kubectl.kubernetes.io/last-applied-configuration`, and puts the saved value back after the create. `kubectl create` writes the whole new object, `volumeName` included, into that annotation when the manifest has it. Argo CD then tries to remove `volumeName`, and the API server refuses the change (`spec is immutable after creation`).
8. It scales the workloads back, makes sure that their pods run on the target node, and turns on automated sync again: the Application, `cluster`, then `bootstrap`.

Before the point of no return, a failure undoes each change of the move, the last change first. From the point of no return on, a failure leaves Argo CD paused, because a self-heal would make an empty claim. The command then prints the saved claim and the steps that did not run.

The copy pods run as root, so that tar keeps the owners. The namespace must allow that: `monitoring` (`privileged`) and `logging` (`baseline`) do.

The old volume stays `Released`, with its data, until a person deletes it. The command prints the command that deletes it: with the reclaim policy `Delete`, local-path deletes the volume and its directory on the node.

```bash
kubectl patch pv <old-pv> -p '{"spec":{"persistentVolumeReclaimPolicy":"Delete"}}'
```

#### Finish a stopped move

When a move stops after the point of no return, the old claim is gone, the new volume has the copy, and Argo CD stays paused. Do the steps that the command prints:

1. Make the claim again from the saved file with `spec.volumeName: <new-pv>`. Leave out `kubectl.kubernetes.io/last-applied-configuration` and the annotations of the volume controllers (`pv.kubernetes.io/*`, `volume.kubernetes.io/*`, `volume.beta.kubernetes.io/*`). Then put the saved last-applied value back with `kubectl annotate pvc <claim> -n <namespace> --overwrite kubectl.kubernetes.io/last-applied-configuration=<value>`.
2. Scale the workloads back to their replicas, and make sure that their pods run on the target node.
3. Turn on automated sync again: the Application, then `bootstrap`, which restores `cluster`, which restores the others from git.

## Host Journals and Health Metrics

Each node sends its journal to Loki and its health series to Prometheus through the k8s-monitoring chart (`monitoring/k8s-monitoring-values.yaml`), with no agent installed on the host:

- **Journal (`nodeLogs`)**: the `alloy-logs` DaemonSet, which already reads pod logs, reads `/var/log/journal`. It keeps kernel lines at every priority, the `k3s`, `k3s-agent`, `nvidia-power-limit`, `containerd` and `systemd-journald` units and systemd's own lines about them at info and above, and every other line at warning and above. Each unit may send 1 line/s after a burst of 10,000; kernel lines have no limit. Lines carry `job="integrations/kubernetes/journal"`, `instance` (the node), `unit`, `transport` and `level`, with the boot ID as structured metadata (`boot_id`).
- **What the journal reader drops**: counted only on each `alloy-logs` pod's own `/metrics` (port 12345), in series the Alloy integration's default allow list does not forward to Prometheus. Every entry the keep rules drop counts as `loki_source_journal_target_parsing_errors_total{error="empty_labels"}`, so that series counts the filter at work, not errors; lines the rate limit cuts count per unit in `loki_process_dropped_lines_by_label_total{label_name="unit"}`.
- **Metrics (`hostMetrics`)**: Prometheus keeps every series node-exporter serves, with no allow list (#1129), because node-exporter's collector flags decide what is collected. Among them are `node_boot_time_seconds`, `node_hwmon_temp_celsius` with `node_hwmon_chip_names`, `node_pressure_*`, the EDAC correctable and uncorrectable error counters, `node_nvme_info`, filesystem size and free space, and `node_systemd_unit_state` for the units above, from the systemd collector the values turn on. node-exporter's systemd collector reads unit state over the host's D-Bus socket, reached through the node root the chart mounts at `/host/root`.

```text
{job="integrations/kubernetes/journal", transport="kernel"}               # LogQL: kernel lines
{job="integrations/kubernetes/journal", unit=~"k3s(-agent)?\\.service"}   # LogQL: k3s
changes(node_boot_time_seconds[30d])                                       # PromQL: reboots per node
node_systemd_unit_state{state="failed"} == 1                               # PromQL: failed host units
```

## Alerting

Alertmanager runs from the prometheus chart (`alertmanager` in `monitoring/prometheus-values.yaml`), and Grafana reads it as the `Alertmanager` datasource. The rules are in the same file, under `serverFiles.alerting_rules.yml`; `tests/test_k8s_monitoring_alerting.py` pins them and checks that each selects only series a scrape in `k8s/` serves. No rule watches the controller manager, scheduler or proxy: k3s runs them inside its server process, so nothing scrapes them and such a rule would fire on the missing target.

| Alert | Fires when | For | Severity |
| :--- | :--- | :--- | :--- |
| `NodeNotReady` | Kubernetes reports a node not Ready | 5m | critical |
| `TargetDown` | A scrape target is down (`up == 0`) | 10m | warning |
| `NodeRebooted` | A node has been up for under 30 minutes | — | warning |
| `K3sServiceNotActive` | A node's `k3s.service` or `k3s-agent.service` is not active | 5m | critical |
| `GpuPowerLimitServiceNotActive` | `nvidia-power-limit.service` is not active, so the GPU power caps may not be applied | 10m | critical |
| `GpuTemperatureHigh` | A GPU is over 85 °C (warning) or at 90 °C or more (critical) | 10m, 2m | warning, critical |
| `GpuPowerOverSiteBudget` | All GPUs together draw more than the site budget in the rule (1000 W) | 5m | critical |
| `HostFilesystemSpaceLow` | A node filesystem has under 10% (warning) or 5% (critical) free | 15m, 5m | warning, critical |
| `LocalPathNodeDiskHigh` | The root filesystem of a node that runs a pod on a `local-path` claim is over 85% used, where the kubelet starts to delete unused images | 15m | warning |
| `PersistentVolumeSpaceLow` | A volume that reports kubelet volume stats has under 10% free; no volume on this cluster reports them yet | 15m | warning |
| `LogOrMetricVolumeDiskLow` | The root filesystem of the node holding `storage-loki-0` or `prometheus-server` has under 10% free; names the claim at risk | 30m | warning |
| `PrometheusNearRetentionSizeCap` | Prometheus's data uses over 80% of `server.retentionSize`, before the cap deletes blocks younger than 30 days | 1h | warning |
| `PrometheusSizeLimitCutHistory` | Prometheus deleted blocks to stay under its size cap | — | warning |
| `PrometheusStorageNearClaim` | Prometheus's data uses over 80% of the `prometheus-server` claim, which with the cap at 80% of the claim means the cap is not holding it | 1h | warning |
| `LokiRetentionNotRunning` | Loki's compactor has not applied retention for over an hour; retention runs once #550's Loki migration has turned it on | 30m | warning |
| `LokiRequestErrors` | Over 5% of a Loki route's requests return 5xx | 15m | warning |
| `PyroscopeQueryErrors` | A Pyroscope route's 5xx request rate over 15m is above 0 | 15m | warning |
| `AlloyRemoteWriteSamplesFailed` | An Alloy collector failed to remote-write samples to Prometheus | 15m | warning |
| `AlloyLogEntriesDropped` | An Alloy collector dropped log entries on their way to Loki | 15m | warning |
| `PodLogsNotShipped` | An `alloy-logs` pod has sent 0 log entries to Loki (`node` joined from `kube_pod_info`) | 30m | warning |
| `ArgoCdApplicationOutOfSync` | An Argo CD Application's `sync_status` is not `Synced` | 15m | warning |
| `ArgoCdApplicationUnhealthy` | An Argo CD Application's `health_status` is neither `Healthy` nor `Progressing` | 15m | warning |
| `ArgoCdAutoSyncDisabled` | An Argo CD Application's `autosync_enabled` is `false` | 15m | warning |
| `ArgoCdSyncOperationStuck` | An Argo CD Application has a sync operation running | 1h | warning |
| `IngressServesPlaceholderHost` | An Ingress routes a host under the placeholder domain of git (`kube_ingress_path`), so Traefik returns 404 for its real host; see Homelab Values at Deploy Time | 5m | critical |
| `CloudflareTunnelDegraded` | Total Cloudflare Tunnel HA connections across `cloudflared` replicas are under 2 | 5m | warning |
| `CoreDnsServfailResponses` | Over 5% of CoreDNS responses return `SERVFAIL` | 5m | warning |
| `ValkeyCacheErrors` | A Valkey exporter reports `redis_up == 0` or rejected client connections | 5m | warning |
| `ClusterMetricsMissing` | `kube_node_status_condition` is absent, so the node rules cannot fire | 10m | critical |
| `PrometheusConfigReloadFailed`, `PrometheusRuleEvaluationFailures`, `PrometheusNotConnectedToAlertmanager`, `PrometheusDroppingAlerts`, `PrometheusCompactionsFailing` | Prometheus's own health | 0–15m | warning |
| `AlertmanagerConfigReloadFailed`, `AlertmanagerNotificationsFailing` | Alertmanager's own health; the second only once the webhook Secret exists | 10m, 15m | warning |

Retention, volume sizes and what `LogOrMetricVolumeDiskLow` and `PrometheusNearRetentionSizeCap` watch are in Log and Metric Retention, above.

The local-path volumes are host directories. They report no kubelet volume stats and do not enforce their claim's size, so the host filesystem under them is what fills. `HostFilesystemSpaceLow` watches every filesystem of every node; `LogOrMetricVolumeDiskLow` watches the same 10% on the root filesystem of the node holding Loki's and Prometheus's claims and names the claim at risk, so on that node both fire. For Prometheus, `PrometheusNearRetentionSizeCap` warns before its size cap deletes anything, `PrometheusSizeLimitCutHistory` once it has, and `PrometheusStorageNearClaim` if the data outgrows the claim with no cap holding it.

The GPU power budget is one number for the whole site, from the GPUs' draw before a breaker trip on the circuit every node shared. Once the power layout is settled, it should become one budget per circuit.

### Receiver

Alerts without a routed severity go to the `null` receiver, which sends nowhere. `critical` and `warning` alerts go to `webhook`, which posts Alertmanager's webhook JSON to the URL in the `url` key of the Secret `alertmanager-webhook` in `monitoring`. The Secret is mounted optional, as a directory, at `/etc/alertmanager-webhook`, so Alertmanager starts without it and the running pod sees the file about a minute after the Secret is created. Until then each webhook notification fails, Alertmanager logs `Notify for alerts failed`, and nothing leaves the cluster.

To wire a channel, write its URL to a file (so it stays out of shell history) and create the Secret:

```bash
kubectl -n monitoring create secret generic alertmanager-webhook --from-file=url=<file-holding-the-url>
```

The monitoring perimeter lets Alertmanager reach ports 80 and 443 outside the cluster; a receiver on another port needs an egress rule in `monitoring/networkpolicy.yaml`.

### Planned maintenance

Silence the node, then drain it. Every alert about one node carries a `node` label: node-exporter's rules copy it from `instance`; the discovery rules of Alloy's annotation autodiscovery, kube-dns job and DCGM integration, and the server's `kubernetes-pods` job for the collector, set it on the pods they scrape; the Loki integration puts Loki's node in `instance`, which `TargetDown` falls back to; and `LogOrMetricVolumeDiskLow` and `PodLogsNotShipped` take it from `kube_pod_info`. So one silence covers the node, its scrape targets, its units and the `NodeRebooted` that follows. Make it last the work plus 30 minutes:

```bash
kubectl -n monitoring exec statefulset/prometheus-alertmanager -c alertmanager -- \
  amtool --alertmanager.url=http://localhost:9093 silence add 'node="<node>"' \
  --duration=3h --author=<name> --comment="<reason>"
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data
```

The drain moves the pods that can move to other nodes. A few cluster-wide alerts have no `node` label. One pod, `k8s-monitoring-alloy-metrics-0`, forwards every series from kube-state-metrics, node-exporter and the DCGM exporter, and scrapes the annotated pods, the Alloy collectors, Grafana, Loki, Tempo, Pyroscope and CoreDNS. Its write-ahead log is on a `local-path` volume (Alloy Metrics Write-Ahead Log, above), so it cannot move to another node. Drained, or on a node that powers off, it waits for its node. While it waits, those series stop: the `up` series of the targets it scrapes go stale instead of reporting 0, so no `TargetDown` fires for them, and no other node's `NodeNotReady` can fire. After about 15 minutes `ClusterMetricsMissing` (critical, no `node` label) pages, because the node silence does not match it. Pods on `local-path` volumes (Prometheus, Loki, Grafana, Pyroscope, Alertmanager and `alloy-metrics`) cannot move and wait for their node. While the node holding Prometheus or Alertmanager is down, no alert is evaluated or sent at all.

After the work, let pods back onto the node, and expire the silence if the work ended early:

```bash
kubectl uncordon <node>
kubectl -n monitoring exec statefulset/prometheus-alertmanager -c alertmanager -- \
  amtool --alertmanager.url=http://localhost:9093 silence query
kubectl -n monitoring exec statefulset/prometheus-alertmanager -c alertmanager -- \
  amtool --alertmanager.url=http://localhost:9093 silence expire <silence-id>
```

In Grafana, Alerting > Silences with the `Alertmanager` datasource selected does the same; anonymous viewers can only list silences. Alertmanager keeps silences on its volume, so they survive a restart.

## Cluster Secrets

Every Secret the stacks read comes from the workstation's OS keyring. `devops k8s push-secrets` writes them (workstation keyring → cluster, the reverse of `devops k8s sync-secrets`), and `devops k8s deploy-stack` runs the same push right after the namespaces, before any manifest or Helm release. One table in `src/devops_cli/k8s/cluster_secrets.py` lists them, and a test fails on any Secret a manifest or values file here references without a row:

| Secret | Key | Source | Required | When the keyring has no value | Stack | Restarted when it changes |
|---|---|---|---|---|---|---|
| `llm/llm-gateway-secrets` | `master-key` | keyring `llm_gateway_master_key` | yes | adopt the live value; else generate `sk-` + 48 hex | llm | `deployment/llm-gateway` |
| `llm/qdrant-api-key` | `api-key` | keyring `qdrant_api_key` | yes | adopt the live value; else generate `token_urlsafe(32)` | llm | `statefulset/qdrant`, `statefulset/open-webui` |
| `llm/valkey-runs-auth` | `password` | keyring `runs_index_password` | yes | adopt the live value; else generate 64 hex | llm | `deployment/valkey-runs` |
| `llm/valkey-auth` | `VALKEY_PASSWORD` | keyring `valkey_password` | yes | adopt the live value; else generate 64 hex | llm | `deployment/valkey`, `statefulset/open-webui` |
| `cloudflared/cloudflared-token` | `token` | keyring `cloudflare_tunnel_token` | no | adopt the live value; else skip with a warning | base | `deployment/cloudflared` |
| `devops/devops-cli` | `GH_TOKEN` | gh account | yes | fail | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_AI_API_KEY` | keyring `llm_gateway_master_key` | yes | adopt from `llm/llm-gateway-secrets master-key`; else fail | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS` | keyring `service_webhook_secrets` | no | adopt the live value; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_TAVILY_API_KEY` | keyring `tavily_api_key` | no | adopt the live value; else skip with a warning | devops | `deployment/roadmap-service` |
| `monitoring/grafana-admin` | `admin-user` | literal | yes | fail | infra | `deployment/grafana` |
| `monitoring/grafana-admin` | `admin-password` | keyring `grafana_password` | yes | adopt from `monitoring/grafana admin-password`; else generate `token_urlsafe(32)` | infra | `deployment/grafana` |
| `gitea/gitea-admin` | `username` | literal | yes | fail | gitea | `deployment/gitea` |
| `gitea/gitea-admin` | `password` | keyring `gitea_admin_password` | yes | adopt the live value; else fail | gitea | `deployment/gitea` |

- The keyring must be unlocked (`devops devcontainer unlock-keyring`); a locked or missing keyring stops the push before anything is read or written, and stops deploy-stack before it applies anything.
- A value the keyring lacks but the cluster holds is adopted into the keyring, so a first push changes nothing live. Only values nobody types are generated, and each is stored in the keyring before it is pushed.
- Typed values are stored at a hidden prompt: `devops config set cloudflare.tunnel_token` or `devops config set gitea.admin_password`.
- `GH_TOKEN` is the token gh keeps in the OS keyring for the machine account named by `--github-account` or `devops config set k8s.github_account <login>`. The push takes gh's word for it: `gh auth status` must list the login with its token in the keyring and its own check of the token passing, then `gh auth token --user <login>` reads it. devops-cli never calls GitHub with the machine token itself, so a run keeps the one GitHub identity it has (#767).
- `devops` rows are pushed wherever namespace `devops` exists, also by every deploy-stack run. `devops k8s deploy-stack --no-push-secrets` skips the push on a cluster without a keyring.
- `gitea` rows are pushed by `push-secrets` with no `--stack` or with `--stack gitea`, and by `deploy-stack --stack gitea` or `all`. The root kustomization creates namespace `gitea` on every cluster, so these pushes need the Gitea admin password in the keyring. A deploy of another stack never reads it.
- Secrets are server-side applied from stdin under field manager `devops-cli`, labelled `app.kubernetes.io/managed-by: devops-cli`, with values in `data`: never in argv, a file, an annotation or the output. A Secret still carrying a client-side apply's `kubectl.kubernetes.io/last-applied-configuration` loses it.
- `--plan` reads the keyring, the live Secrets and, for `devops/devops-cli`, the machine account's token from gh (`gh auth status`, which checks the token on github.com, then `gh auth token`), says so, and prints each key's state (`would adopt`, `unchanged`, `differs`, ...) and the workloads a change would restart, writing nothing. `--dry-run` makes no request at all, not even those reads: it prints the requests a push would make, in order, with `<placeholders>` for every value and the condition under which each later request runs.
- A Secret whose data changed has its workloads restarted (`kubectl rollout restart`); `--no-restart` prints the commands instead. Open WebUI keeps the gateway connection in its database, so a changed gateway key is also updated under Admin Panel > Settings > Connections.

Rotation: a live value that differs from the keyring stops the push. Either replace the live value with the keyring's, or adopt the live value by removing the keyring entry:
```bash
devops k8s push-secrets --only llm/qdrant-api-key --plan      # reads the cluster; shows "differs"
devops k8s push-secrets --only llm/qdrant-api-key --rotate     # the keyring's value wins
uv run keyring del devops-cli qdrant_api_key                  # or: drop it, and the next push adopts the live value
```
To rotate a generated value, store a new one at a hidden prompt with `uv run keyring set devops-cli <keyring key>`, then push with `--rotate`.

## devops-cli in the cluster

`k8s/devops/` runs devops-cli as cluster Jobs, so agents drive it with kubectl and never handle keys. It is managed by `devops k8s deploy-stack --stack devops` (and `--stack all`), the only command that creates its ConfigMap `devops-cli-config`, which it renders from `config.yaml`; `devops k8s apply k8s/devops/ --template` applies the rest without it, and the pods wait for that ConfigMap. Each Job reads its credentials from Secret `devops/devops-cli` through `envFrom`, its configuration from ConfigMap `devops-cli-config` (provider `gateway` at `http://llm-gateway.llm.svc.cluster.local:4000/v1`), holds no Kubernetes API token, accepts no ingress, and reaches only DNS, the gateway, the OpenTelemetry collector in namespace `otel` and public HTTPS. Commands that need Qdrant, Prometheus, Grafana, Argo CD or a repository checkout do not run there yet.

```bash
devops config set service.repos <owner/name>             # the repositories the service works for
devops config set k8s.github_account <machine-login>     # push-secrets needs it, even with service.machine_account set
devops k8s deploy-stack --stack devops --context <context>
devops k8s push-secrets --context <context> --plan       # reads the keyring, gh and the cluster: key names and states, never a value
devops k8s push-secrets --context <context>
devops k8s run-job --context <context> -- --version      # follows the log, exits with the Job's exit code
devops k8s run-job --context <context> --no-wait -- ai gateway status --format json
```

`run-job --dry-run` reads nothing, not even the CronJob, and prints the kubectl requests a run would make. `run-job` creates the Job from suspended CronJob `devops-cli`, changing only the container's args, the name (`devops-cli-<UTC time>-<hex>`) and the label `app.kubernetes.io/name: devops-cli-job`. A Job never retries (`backoffLimit: 0`), stops after two hours and is deleted a day after it finishes. Follow or clean up Jobs with kubectl:
```bash
kubectl -n devops get jobs -l app.kubernetes.io/name=devops-cli-job
kubectl -n devops logs -f job/<name>
```

### Roadmap service

> **Suspended ([#1562](https://github.com/dan-petty/devops-cli/issues/1562)).** GitHub suspended the machine account, and `deployment/roadmap-service` is held at `replicas: 0`. Do not run the steps below, scale the deployment, or rotate its secrets until #1562's revert merges. Disable each managed repository's webhook meanwhile.

1. `uv run devops config set service.repos <owner/name>` (each repository the service works for), then `uv run devops config set service.webhook_secrets` (hidden prompt; a JSON object mapping `owner/name` to its secret). deploy-stack refuses the devops stack until `service.repos` and the machine account (step 2) are set.
2. `uv run devops k8s push-secrets --stack devops`, with the machine account's login in `k8s.github_account` (#741). deploy-stack also pushes it once namespace `devops` exists.
3. Invite the machine account as a Write collaborator on each repo and board.
4. Check that the GHCR `service` package is public (#741 made it so): `DOCKER_CONFIG=$(mktemp -d) docker pull ghcr.io/dan-petty/devops-cli/service:<tag>`.
5. `devops cloudflare tunnel routes`. If no route covers the webhook host, add one in the dashboard, not with `tunnel sync` (#794).
6. `devops cloudflare access status`, then add a Bypass application for `hooks.<domain>/webhooks/github`.
7. `devops k8s deploy-stack --stack devops` (or `--stack all`).
8. Add each repo's webhook: `https://hooks.<domain>/webhooks/github`, `application/json`, that repo's secret, and only the Issues event. The Service acknowledges an event with no subscriber, a push included, and starts no round for it, so a hook that sends every event or only pushes is harmless, but only an issue that opens or reopens starts a round before the next poll ([ADR 0009](../docs/adr/0009-one-webhook-router-delivers-each-event-to-the-consumers-subscribed-to-it.md), #1386).
9. To rotate a credential, update it in the keyring (`uv run devops config set service.webhook_secrets`, or `gh auth login` for the machine account), then run `uv run devops k8s push-secrets --only devops/devops-cli --rotate`. It restarts `roadmap-service`.
10. Run one service per set of repos. While it runs, use `devops roadmap run --dry-run` (#981).

### Agent sessions

`k8s/agents/` defines read-only identity and boundaries for autonomous AI agent sessions running against the cluster:

- **Namespace `agents`**: Enforces `restricted` Pod Security Standards across `enforce`, `warn`, and `audit` levels.
- **ServiceAccount `devops-agent`**: Created in namespace `agents` with `automountServiceAccountToken: false` to ensure agents do not automatically mount cluster credentials.
- **ClusterRoleBinding `devops-agent-view`**: Binds `devops-agent` exclusively to the built-in read-only `view` ClusterRole. No other RBAC manifests grant mutating or secret-reading permissions to this identity.
- **GitOps Management**: Managed by Application `agents` (`k8s/argocd/apps/agents.yaml`) under the `homelab` project, with AppProject orphan-ignore rules configured for transient session secrets (`agent-grant-*`).

## Argo Workflows

`k8s/argo-workflows/` installs the [Argo Workflows](https://argo-workflows.readthedocs.io/) controller in its own namespace, `argo-workflows`, with one WorkflowTemplate that measures what a Workflow costs. [ADR 0008](../docs/adr/0008-argo-workflows-run-the-roadmap-jobs-after-a-measured-go.md) records why and what result counts as a go (#1535). No roadmap job runs on it yet.

- **Controller.** The argo-helm chart `argo-workflows`, pinned in Application `argo-workflows`, with `argo-workflows/values.yaml`: one replica that the Recreate strategy replaces, so two controllers never run, watching only namespace `argo-workflows` (`singleNamespace`). It has no argo-server, database or workflow archive. Its CRDs are the chart's minimal ones, kept when the release is uninstalled.
- **Namespace.** `argo-workflows` enforces Pod Security `restricted` and carries `Prune=false,Delete=false` (`namespaces.yaml`). The `homelab` project lists it as a destination.
- **Executor.** Workflows run as ServiceAccount `argo-workflows-executor`, whose Role grants only `create` and `patch` on `workflowtaskresults`. The controller and the executor's init and wait containers set the security context that `restricted` requires.
- **Perimeter.** `argo-workflows/networkpolicy.yaml` admits only the metrics scrape from `monitoring` on port 9090, and lets pods reach only DNS and the API server on port 6443, through an ipBlock that excludes the cloud metadata address. There is no public HTTPS and no OpenTelemetry egress. Alloy scrapes the controller through the chart's ServiceMonitor ([Scrape Ownership](#scrape-ownership)), and `monitoring/networkpolicy.yaml` allows that egress.
- **Template.** WorkflowTemplate `devops-cli-version` runs `devops --version` in the Service image: no GitHub request, no Secret, no `envFrom`, and telemetry off. It has the cluster job template's pod and container security context, an `activeDeadlineSeconds`, and `ttlStrategy` and `podGC` settings that delete finished Workflows and, once a Workflow succeeds, its pods. Application `argo-workflows-manifests` syncs the perimeter and the template from `k8s/argo-workflows/`, and skips the dry run until the chart's CRDs exist.

On a cluster Argo CD manages, those two Applications install it. Without Argo CD, `devops k8s deploy-stack --stack infra` (or `all`) applies the perimeter before any chart, installs release `argo-workflows` after `argocd`, and applies the template after the Helm releases. `teardown-stack` deletes the template before it uninstalls the releases, and the namespace with the others. `deploy-stack --dry-run` lists every step.

Check the install:

```bash
devops argo cd apps status argo-workflows              # Synced and Healthy
devops argo cd apps status argo-workflows-manifests    # Synced and Healthy
kubectl -n argo-workflows get deploy,pods              # one workflow-controller replica, Running
kubectl get crd workflows.argoproj.io workflowtemplates.argoproj.io workflowtaskresults.argoproj.io   # the Workflow CRDs exist
kubectl auth can-i create workflowtaskresults.argoproj.io -n argo-workflows \
  --as=system:serviceaccount:argo-workflows:argo-workflows-executor   # yes
devops prometheus query 'up{namespace="argo-workflows"}'  # the controller's metrics target is 1
kubectl -n devops get deploy roadmap-service           # unchanged, still at 0 replicas
```

### Measurement

The go/no-go measurement needs the cluster and the `argo` CLI (`devops install-tools --tool argo`), whose pin in `tools.lock` is the chart's app version. The CLI talks to the Kubernetes API directly, so no argo-server is needed. A person (or an agent on the homelab) runs it once after the install syncs:

```bash
# API-server requests handled so far, then how many of them were 429 or 5xx
counters() { kubectl get --raw /metrics | awk '/^apiserver_request_total/ {all += $NF} /^apiserver_request_total\{.*code="(429|5[0-9][0-9])"/ {bad += $NF} END {print all, bad+0}'; }

# one batch of 20 Workflows, <parallelism> at a time: prints the counters before and after, and the seconds it took
batch() {  # batch <label> <parallelism>
  counters; start=$(date +%s)
  seq 20 | xargs -P "$2" -I{} argo submit --from workflowtemplate/devops-cli-version -n argo-workflows --wait --labels measurement="$1"
  counters; echo "seconds $(( $(date +%s) - start ))"
}

batch sequential 1   # the first Workflow is the cold run when no node holds the Service image yet
batch burst 20

# the same counters over an idle interval as long as the batch took, for the baseline
idle=120   # set to the seconds that `batch` printed
counters; sleep "$idle"; counters

# the controller's CPU and memory while a batch runs: run this in a second terminal during `batch`
kubectl -n argo-workflows top pod
```

Read the durations before the template's `ttlStrategy` removes the Workflows (an hour after they finish). The first command prints the cold run and the warm p50 and p95 of the other 19 Workflows, the second the burst's p50 and p95, as the nearest-rank percentile (the value at position ceil(p x n) of the sorted durations):

```bash
kubectl -n argo-workflows get workflows -l measurement=sequential -o json | jq -r '
  [.items | sort_by(.metadata.creationTimestamp)[] | (.status.finishedAt | fromdate) - (.metadata.creationTimestamp | fromdate)]
  | "cold \(.[0]) s", (.[1:] | sort | "warm p50 \(.[(length * 0.5 | ceil) - 1]) s, p95 \(.[(length * 0.95 | ceil) - 1]) s")'
kubectl -n argo-workflows get workflows -l measurement=burst -o json | jq -r '
  [.items[] | (.status.finishedAt | fromdate) - (.metadata.creationTimestamp | fromdate)] | sort
  | "burst p50 \(.[(length * 0.5 | ceil) - 1]) s, p95 \(.[(length * 0.95 | ceil) - 1]) s"'
```

Record these, each batch apart:

- Creation to Succeeded for each Workflow, as the p50 and p95. Report the first sequential run (the cold run) apart, and take the warm p95 over the other 19. Both timestamps have one-second resolution.
- API-server requests per Workflow: the change in the first counter across the batch, minus the change over an idle interval as long as the batch took (the `sleep` pair above, repeated for that many seconds), divided by the Workflows in the batch.
- The change in the second counter across the burst, which must be 0, and any `argo submit` that fails with a 429 or a 5xx.
- The controller's CPU and memory, from `kubectl top` or the cAdvisor series Alloy already scrapes (`container_cpu_usage_seconds_total`, `container_memory_working_set_bytes`).

Go when the warm p95 is at most 30 seconds and the burst finished with no 429 or 5xx. Post the numbers and the verdict as a comment on [#1535](https://github.com/dan-petty/devops-cli/issues/1535). After a go, file the later steps with `devops roadmap intake`; after a no-go, the owner chooses between re-scoping the engine and the runner-up in ADR 0008.

## Gitea

Gitea is the internal forge of the homelab (#1081). It holds the iteration branches that the owner and the agents push without GitHub, and its container registry holds the pull-request images (#1082, [Internal Image Registry](#internal-image-registry)). GitHub stays the source of truth for `main`, tags, pull requests, CI and releases. #1090 adds the Gitea remote to each repository under `repos/`.

Argo CD's Application `gitea` installs chart `gitea` 12.7.0 from `https://dl.gitea.com/charts/` with `gitea/values.yaml` (Gitea 1.27.3, rootless image), and Application `gitea-manifests` applies the perimeter `gitea/networkpolicy.yaml`. Without Argo CD, `devops k8s deploy-stack --stack gitea` (or `all`) applies the perimeter and installs the same release. The root kustomization creates namespace `gitea`, with Pod Security `restricted`.

| Client | Address | Path |
| :--- | :--- | :--- |
| Pods and Argo CD | `http://gitea-http.gitea.svc.cluster.local:3000` | the chart's Service, over plain HTTP |
| Workstations | `https://git.<domain>` | the tunnel's wildcard route, Traefik and Ingress `gitea/gitea-ingress` in `ingress/ingress-routes.yaml` |

- TLS ends at Cloudflare. From cloudflared on, a request is plain HTTP on the pod network. Flannel's `vxlan` backend carries traffic between nodes with no encryption, as it does for every host behind the tunnel.
- No value names a domain (#1290). `ROOT_URL` is the in-cluster address. Gitea builds the URLs of a request from its `Host` header and its `X-Forwarded-Proto` (`PUBLIC_URL_DETECTION = auto`). Cloudflare sets `X-Forwarded-Proto: https`, cloudflared forwards it, and Traefik's `web` entrypoint keeps it (`ingress/traefik-values.yaml`). Thus the clone URLs and the container registry's token realm of a request to `https://git.<domain>` start with `https://git.<domain>/`. Text that Gitea writes outside a request, such as the links that a push prints, uses the in-cluster address.
- deploy-stack sets the configured domain on the host of `gitea-ingress` ([Homelab Values at Deploy Time](#homelab-values-at-deploy-time)).
- Gitea has no SSH: `DISABLE_SSH` is true and `START_SSH_SERVER` is false. The chart's SSH Service stays, but nothing answers on it, and the perimeter admits only TCP 3000.
- Registration is off, every page needs a sign-in, a new repository is private, and only the API creates a repository: a push to a mistyped remote fails. Mirrors, migrations, Actions and the update checker are off, so Gitea calls nothing outside its namespace.
- Cloudflare refuses a request body over the limit of its plan (100 MB on the Free and Pro plans) with `413`. Thus a push of a larger image layer through `https://git.<domain>` fails.

### Cloudflare

Nothing new is configured in Cloudflare when the wildcard route and the wildcard Access application are in place:

- The tunnel's wildcard public hostname goes to Traefik, and the wildcard DNS record exists. `devops cloudflare tunnel routes` and `devops cloudflare dns list` show them, and `devops cloudflare tunnel sync` and `devops cloudflare dns sync` make them.
- The Access application of the wildcard has the policy `homelab-public-ip-bypass` with the current public address of the workstation. `devops cloudflare access status --json` gives the ID of the application, and `devops cloudflare access policies <app-id>` lists its policies.

Git over HTTPS cannot follow the Access login redirect, and a git credential helper gives only a user name and a password, not headers. Thus git gets through Access by the bypass policy, and then Gitea's own token authenticates the request. No Access service token goes into git config. A browser on another network signs in through Access first, and then through Gitea.

When the public address changes, git and the API get a redirect to the Access login. Set `cloudflare.access.allowed_emails` and `cloudflare.access.bypass_ips` (the new address), then run:

```bash
devops cloudflare access sync --domain '*.<domain>' --dry-run   # it must name the wildcard application and both lists
devops cloudflare access sync --domain '*.<domain>'
```

Without `--domain`, the command updates the apex application. Without the emails, it empties the allow policy. If git gets a Cloudflare challenge page instead of the reply of Gitea, the bot or WAF settings of the zone challenge the git client: exempt host `git.<domain>` from that challenge.

### Rollout

1. Store the admin password at a hidden prompt: `uv run devops config set gitea.admin_password`. The admin user is `gitea_admin`.
2. Merge. Application `base` creates namespace `gitea`, and the Applications `gitea` and `gitea-manifests` sync. The Gitea pod waits in `CreateContainerConfigError` until Secret `gitea-admin` exists.
3. Run `uv run devops k8s deploy-stack --stack gitea --context <context>`. It pushes Secret `gitea/gitea-admin` and sets the git host on Application `ingress`. Then the pod starts with no other step.
4. Set the reclaim policy of the bound volume to `Retain`, because `local-path` deletes the data with a deleted claim:
   ```bash
   kubectl patch pv "$(kubectl -n gitea get pvc gitea-shared-storage -o jsonpath='{.spec.volumeName}')" \
     -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
   ```
5. Run `uv run devops k8s doctor --stack gitea --context <context>`. Every check must pass ([Stack checks](#stack-checks)).

To change the admin password, store the new one with `uv run devops config set gitea.admin_password`, then run `uv run devops k8s push-secrets --only gitea/gitea-admin --rotate`. The push restarts Gitea, and Gitea sets the admin's password to the Secret's when it starts (`passwordMode: keepUpdated`). Then `uv run devops k8s doctor --stack gitea` signs in with the new password in its `clone-url` check.

### Stack checks

`devops k8s doctor --stack gitea` checks the live stack, and shows the result and the reason of each check. It exits 2 when a check fails. A failed check does not stop the next one. `--dry-run` lists the kubectl commands and the HTTP requests, and makes none of them. `--format json` or `yaml` gives the checks as data.

| Check | It passes when |
| :--- | :--- |
| `application-gitea`, `application-gitea-manifests` | the Application is `Synced` and `Healthy`. |
| `volume-retained` | the volume of claim `gitea-shared-storage` has the reclaim policy `Retain` ([Rollout](#rollout), step 4). |
| `pod-security-restricted` | namespace `gitea` has the Pod Security enforce level `restricted`. |
| `ingress-host` | Ingress `gitea/gitea-ingress` has a host, and the host is not `git.example.com`, the placeholder in git. The next checks send their requests to that host of the live Ingress, through the tunnel. Without it, they fail and send nothing. |
| `tunnel-host` | `GET /user/login` answers 200. A redirect to the Access login tells you that the public address changed ([Cloudflare](#cloudflare)). |
| `anonymous-read-refused` | `GET /api/v1/repos/search` with no sign-in answers 401 or 403. |
| `registry-token` | `GET /v2/` answers 401 with a Bearer challenge whose realm starts with `https://git.<domain>/`. |
| `clone-url` | a temporary private repository `devops-doctor-<random>`, which the check makes as `gitea_admin` with the password from the keyring (`gitea.admin_password`), has a `clone_url` that starts with `https://git.<domain>/`, and an `ssh_url` that does not name that host. Gitea 1.27.3 fills `ssh_url` also when SSH is off: it names the in-cluster address, where nothing answers. |
| `temporary-repository-deleted` | Gitea deleted the temporary repository. The check deletes it also when the `clone-url` check fails, and when the create gets no answer. When the delete fails, the reason names the repository to delete by hand. |
| `no-egress` | `curl https://github.com` in the Gitea container cannot connect (curl exits 7 or 28). |

The password goes only into the Authorization header of the create and the delete. It goes into no argument list, log line or output.

### Data

Gitea keeps its repositories, its packages and its SQLite database (WAL mode) on the `local-path` claim `gitea-shared-storage` on one worker node. `local-path` does not enforce the claim's 10Gi. The pod never runs on the control-plane node, and one pod runs at a time (`Recreate`). The namespace and the claim have `Prune=false,Delete=false`, and the claim has `helm.sh/resource-policy: keep`, so neither Argo CD nor `teardown-stack --stack gitea` deletes them. `teardown-stack --stack all` deletes namespace `gitea` with the root kustomization, and the data with it.

There are no backups yet. A branch that a clone pushed is also in that clone, but an issue or a pull request made in Gitea is lost with the node.

The next major version of the chart (its main branch, with Gitea 28) replaces `gitea.admin` with `secrets.admin`, turns persistence off by default and moves `strategy` under `deployment`. Change those keys in `gitea/values.yaml` in the pull request that changes the pinned version in `argocd/apps/gitea.yaml` and `_HELM_RELEASES_BY_STACK`.

## Teardown

```bash
# Teardown infrastructure stack
devops k8s teardown-stack --stack infra

# Teardown LLM stack
devops k8s teardown-stack --stack llm

# Teardown all stacks and namespaces
devops k8s teardown-stack --stack all
```

Teardown leaves the `prometheus-operator-crds` release's CRDs in the cluster. Deleting a CRD deletes every object of its kind, such as every ServiceMonitor, so remove them by hand only when nothing in the cluster uses them. The `argo-workflows` release's Workflow CRDs stay too (`crds.keep`), for the same reason: deleting them deletes every Workflow and WorkflowTemplate.

## GitOps

Argo CD maintains the declared state of the homelab cluster directly from this repository. A two-level application topology decouples cluster bootstrap from leaf applications:

1. **`bootstrap` (`k8s/argocd/bootstrap/bootstrap.yaml`)**: Tracks `main`. Syncs the root `cluster` Application.
2. **`cluster` (`k8s/argocd/bootstrap/cluster.yaml`)**: Tracks `main`. Syncs project RBAC boundaries (`k8s/argocd/apps/projects.yaml`) and all 27 leaf Applications (11 raw leaf applications and 16 multi-source Helm applications).

When the root `cluster` Application is present in the cluster, `devops k8s deploy-stack` delegates manifest and Helm reconciliation to Argo CD, and `devops k8s teardown-stack` refuses execution to prevent configuration drift.

### Homelab Values at Deploy Time

This repository is public, so it holds no homelab value. Ingress hosts sit under the placeholder domain `example.com`, and the devops-cli config holds only its template, `k8s/devops/configmap.example.yaml`. `devops k8s deploy-stack` supplies the real values from `config.yaml` and the keyring:

| Value | Source | Where it lives | Supplied by |
| :--- | :--- | :--- | :--- |
| Secrets | the OS keyring (`devops k8s push-secrets`) | Secrets in the cluster | every stack's deploy, for its Secrets |
| `service.repos`, `service.machine_account` (or `k8s.github_account`), `service.poll_interval_seconds`, `service.drain_timeout_seconds` | `config.yaml` | ConfigMap `devops-cli-config`, which no Application owns | `--stack devops` or `all` |
| Hosts under the configured domain | `--domain`, else `k8s.domain`, `cloudflare.domain`, `DEVOPS_CLI_K8S_DOMAIN` or `DEVOPS_CLI_DOMAIN` | Kustomize patches in `spec.source.kustomize` of the Applications `devops` and `ingress` | `--stack devops` or `all` (both Applications), `--stack infra` or `gitea` (`ingress` only) |

The rest of ConfigMap `devops-cli-config` (gateway URL, models, context windows, telemetry) comes from `k8s/devops/configmap.example.yaml` in the checkout deploy-stack runs from (`--k8s-dir`, default `./k8s`), so run it from a checkout of `main`, the revision the cluster runs.

Unlike the ConfigMap, the host patches do not depend on the checkout. deploy-stack derives them from what each Application renders at the revision Argo CD builds: it fetches the Application's `targetRevision` from its `repoURL` into a temporary directory and builds its path with Kustomize, whichever branch is checked out locally. `--argocd-revision <ref>` builds another revision instead, to stage hosts before a pull request merges.

The `cluster` Application ignores `spec.source.kustomize` on the two Applications in its diff. It applies the two Applications server-side, because each has the annotation `argocd.argoproj.io/sync-options: ServerSideApply=true`. Argo CD reads that annotation in every sync, automated or by hand, with any sync options. Server-side apply deletes only the fields that its own field manager, `argocd-controller`, set. The host patches belong to the field manager of deploy-stack's `kubectl patch`, and the image digest on `devops` belongs to Image Updater, so a sync of `cluster` keeps them. Do not remove the annotation. Client-side apply deletes each field that the `last-applied-configuration` annotation holds and git does not. The `RespectIgnoreDifferences=true` option of `cluster` writes the patches into that annotation, so a sync by hand without that option deletes them (#1817). The annotation `argocd.argoproj.io/client-side-apply-migration-manager: argocd-controller` on `cluster` moves the fields of the old client-side apply entry to the server-side apply entry in the first server-side sync. Thus a field that git removes from the two Applications also leaves the cluster.

Each patch names one Ingress or IngressRoute and tests the placeholder host at each position before replacing it, so a host that git reorders or removes within that object fails the Application's manifest generation instead of routing to another backend. Kustomize skips a patch whose object no longer exists, and nothing covers an object or host that git adds: run `devops k8s deploy-stack --stack devops` again once such a change reaches the Applications' revision. deploy-stack renders everything before it writes anything, so an unset setting stops it with an error naming the setting and changes nothing in the cluster. An unset service setting stops the dry run too; an unset domain stops only an Argo CD-managed deploy, and the dry run says so. A revision whose Application renders no host under the placeholder is refused rather than given an empty patch list.

These values exist only in the cluster and in `config.yaml`, until Argo CD reads the homelab's private configuration from a repository on the in-cluster Gitea (#1291). A sync keeps the host patches, but these actions remove them:

- The Application `devops` or `ingress` is deleted, and `cluster` creates it again (after `bootstrap-gitops`, for example).
- A sync of `cluster` with the Replace option and without the Respect Ignore Differences option. Argo CD then replaces each Application with its manifest from git.

The Applications then sync the placeholder hosts. When a live Ingress routes a host under the placeholder domain for 5 minutes, `IngressServesPlaceholderHost` fires (Alerting). It fires also for a host that git adds before deploy-stack sets its patch. Set the hosts again from a checkout of `main`:

```bash
# The hosts of Application ingress only. It pushes no Secret and writes no ConfigMap.
devops k8s deploy-stack --stack infra --no-push-secrets --no-wait --no-configure-urls
# The hosts of the Applications devops and ingress, and ConfigMap devops-cli-config
devops k8s deploy-stack --stack devops
```

#### When a pull request merges into `main`

1. The Applications track `main` (`tests/test_k8s_argocd_apps.py` holds them there), so a merge moves `main` forward and the host patches stay in place. Run `devops k8s deploy-stack --stack devops --argocd-revision <branch>` from a checkout of the pull request's branch, right before merging, when the pull request changes `k8s/devops/configmap.example.yaml` (the ConfigMap follows only deploy-stack) or adds, removes, renames or reorders an Ingress or IngressRoute, or a host in one. If the pull request moved a host that `main` also renders, the Application shows the ComparisonError `testing value <pointer> failed` until the merge, and its live Ingresses stay as they were.
2. Merge. Argo CD builds `main` with the staged hosts.
3. The service image changes only with a release. When a person merges the release pull request, the `Release` workflow's run on `main` builds, smoke-tests, scans, pushes and attests the service image, then tags it with the release tag and `latest` ([`RELEASE_CYCLE.md`](../RELEASE_CYCLE.md)). Within one poll of `latest` moving, Image Updater puts the `devops` Application on the new digest ([Service Image Updates](#service-image-updates)), and roadmap-service, which uses the Recreate strategy, is down only while its pod restarts. Until then both workloads keep the previous release's digest: the merge's own sync changes no image, and nothing is committed. A person who re-runs a failed publish job moves both tags when it passes, and Image Updater rolls the workloads onto the new digest.
4. Check: `devops argo cd apps status devops` and `devops argo cd apps status ingress` are Synced and Healthy, ImageUpdater `devops` is Ready and the `devops` Application's `spec.source.kustomize.images` names the digest `service:latest` points at ([Service Image Updates](#service-image-updates)), `kubectl get ingress,ingressroute -A -o yaml | grep example.com` prints nothing, and `kubectl -n devops get configmap devops-cli-config -o yaml` holds the configured repositories and the template values of `main` (gateway URL, models, context windows).

> [!NOTE]
> `k8s/coredns/` remains managed outside Argo CD to preserve cluster DNS resolution during bootstrap and recovery cycles.

### Service Image Updates

Application `argocd-image-updater` runs [Argo CD Image Updater](https://argocd-image-updater.readthedocs.io/en/stable/) in namespace `argocd`, from the argo-helm chart pinned to a version like the other chart Applications. Its one ImageUpdater, `devops` in `k8s/argocd/image-updater-values.yaml`, keeps the `devops` Application on the digest `ghcr.io/dan-petty/devops-cli/service:latest` points at:

- Every two minutes it reads that digest. When the Application runs another one, it writes `ghcr.io/dan-petty/devops-cli/service:latest@sha256:<digest>` into the Application's `spec.source.kustomize.images`, and Argo CD rolls roadmap-service and CronJob `devops-cli` onto it. Git names the image untagged, and that entry sets its tag and digest.
- It updates the image also when no pod runs it, because the image sets `forceUpdate: true`. Without it, Image Updater updates only the images that a pod in the Application's tree runs, and no such pod runs this image: CronJob `devops-cli` is a suspended template, `roadmap-service` can be at 0 replicas, and the Jobs that `devops k8s run-job` starts are outside the tree. ImageUpdater `devops` then stays Ready with `imagesManaged: 0` and updates nothing. When the Application already names the digest, it writes nothing.
- It commits nothing to git. The `cluster` Application leaves `spec.source.kustomize` on `devops` alone, as it does for the host patches, and deploy-stack's merge patch replaces only `kustomize.patches`. If the `devops` Application is re-created, it renders the untagged image (`latest`; with `IfNotPresent` a node pulls it only when missing) until the next poll writes the digest again.
- Both containers set `imagePullPolicy: IfNotPresent`, so a node pulls a digest once, and a registry outage does not block a restart onto an image the node holds.
- It acts only on Argo CD Applications, so a native `devops k8s deploy-stack` installs no release of it: a cluster without Argo CD has no Application to update, and its devops stack runs the untagged image, `latest`.

Read what it deployed:

```bash
kubectl -n argocd get imageupdater devops          # Ready, and when it last checked
kubectl -n argocd get imageupdater devops -o jsonpath='{.status.recentUpdates}'
kubectl -n argocd get application devops -o jsonpath='{.spec.source.kustomize.images}'
kubectl -n argocd logs deploy/argocd-image-updater-controller --tail=50
```

### Internal Image Registry

Gitea's container registry is the internal registry of the cluster ([Gitea](#gitea)). Pull-request images go to it, and the nodes pull them from it (#1082). Release images stay on GHCR. Until #1082, no workload pulls from it, and every workload pulls its image from a public registry.

The cluster has no `registry:2` Deployment (#1630). That registry accepted pushes and deletes over plain HTTP with no authentication, and no workload pulled from it. Application `base` prunes its Deployment and its Service. Namespace `registry` and PersistentVolumeClaim `registry-data` have `Prune=false,Delete=false`, so Argo CD keeps them. `base` shows them OutOfSync, and `ArgoCdApplicationOutOfSync` fires, until a person deletes them:

```bash
kubectl -n registry delete pvc registry-data   # reclaim policy Delete: local-path removes the data on the node
kubectl delete namespace registry
```

The AppProjects `homelab` and `homelab-system` keep `registry` in their destinations until then. Argo CD ignores a live object in a namespace that its project does not permit, so without that destination it does not prune the Deployment.

### Bootstrap & Adoption

To bootstrap GitOps on a running cluster:

```bash
# Bootstrap the two-level root app topology (defaults to k8s/argocd/bootstrap/bootstrap.yaml)
devops argo cd apps bootstrap-gitops

# Once `cluster` has created the Applications devops and ingress, set the homelab hosts and ConfigMap
kubectl -n argocd get application devops ingress
devops k8s deploy-stack --stack devops
```

### Recovery

If Argo CD itself becomes unavailable or needs to be recovered from scratch:

```bash
# 1. Recover Argo CD via Helm with pinned chart version and values
helm upgrade --install argocd argo/argo-cd --version 10.9.6 -n argocd -f k8s/argocd/values.yaml

# 2. Re-apply the bootstrap application to resume gitops reconciliation
devops argo cd apps bootstrap-gitops

# 3. Once `cluster` has recreated the Applications devops and ingress, set the homelab hosts and ConfigMap
kubectl -n argocd get application devops ingress
devops k8s deploy-stack --stack devops
```

### Drift Detection & Sync Commands

Inspect and manage GitOps state using native `devops argo` commands:

```bash
# List all managed Applications and their sync/health statuses
devops argo cd apps list

# Check detailed status of an Application
devops argo cd apps status <app-name>

# Manually trigger reconciliation / sync for an Application
devops argo cd apps sync <app-name>
```

### Pausing an Application

Every Application sets `enabled: true` under `spec.syncPolicy.automated` in git, and `tests/test_k8s_argocd_apps.py` pins it. The value is in the parent's last-applied configuration, so a different value in the cluster is drift. `cluster` is the parent of the Applications in `k8s/argocd/apps/`, and `bootstrap` is the parent of `cluster` and of itself.

- Pause an Application in git: set `enabled: false` in its manifest and merge the change. While it is paused, the `ArgoCdAutoSyncDisabled` alert fires after 15 minutes.
- Do not pause an Application in the Argo CD UI or API. Its parent shows it OutOfSync and turns automated sync on again at its next self-heal.
- For an emergency stop that cannot wait for a merge, or for a volume move (Local-Path Volume Placement), pause from the top down: `bootstrap`, then `cluster`, then the Application. A paused `bootstrap` does not revert itself. Then commit the pause, or turn `bootstrap` on again: it restores `cluster`, and `cluster` restores the others from git.

### Replaced Hand Steps

| Previous Manual Step | Replaced By Argo CD GitOps |
| :--- | :--- |
| `devops k8s deploy-stack --stack <name>` | Automated reconciliation by Argo CD leaf applications. |
| `devops k8s apply k8s/...` | Declarative raw leaf Applications (`apps/*.yaml`) with `selfHeal: true`. |
| Manual Helm release upgrades (`helm upgrade ...`) | Multi-source Helm Applications with pinned chart versions and git value files. |
| Ad-hoc ingress and domain patching | Host overrides that `devops k8s deploy-stack` sets on the Applications `devops` and `ingress` from `config.yaml` (see Homelab Values at Deploy Time). |
| Secret storage in Helm values | External secret synchronization (`devops k8s push-secrets`) decoupled from manifests. |
| Manual drift reconciliation | Automated self-healing (`automated.enabled: true`, `automated.prune: true`, `automated.selfHeal: true`). |

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
     k8s / Namespace: llm                         k8s / Namespaces: monitoring, argocd, gitea
  [chat.homelab.<domain>] ──▶ open-webui       [grafana.homelab.<domain>] ──▶ grafana
  [ai.homelab.<domain>]   ──▶ llm-gateway      [argocd.homelab.<domain>]  ──▶ argocd
                                               [git.homelab.<domain>]     ──▶ gitea-http
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

1. Create the namespaces, store the tunnel token in the keyring at a hidden prompt, then write it into the cluster (see Cluster Secrets). `push-secrets --only` fails while namespace `cloudflared` is missing; `devops k8s deploy-stack` does all three in one run.
   ```bash
   kubectl apply -f k8s/namespaces.yaml
   devops config set cloudflare.tunnel_token
   devops k8s push-secrets --only cloudflared/cloudflared-token
   ```
2. Apply the declarative tunnel manifests:
   ```bash
   kubectl apply -k k8s/cloudflared/
   ```
3. Ingress Controller (Traefik):
   Stock k3s ships its own Traefik HelmChart; ensure k3s runs with `--disable traefik` so `devops k8s deploy-stack --stack infra` deploys the pinned Traefik release with `k8s/ingress/traefik-values.yaml` (configured with `service.type: ClusterIP`).
4. Core Ingress definitions:
   `devops k8s deploy-stack --stack infra` deploys `k8s/ingress/ingress-routes.yaml` with template substitution automatically (substitutes `k8s.domain` from `config.yaml`). To apply or preview manually:
   ```bash
   devops k8s apply k8s/ingress/ingress-routes.yaml --template
   ```
   Or preview the rendered manifests before applying:
   ```bash
   devops k8s render k8s/ingress/ingress-routes.yaml
   ```

### 4. The Kubernetes API at `k8s.<domain>`

Off the home network, `kubectl` reaches the API server through the tunnel as a TCP route. An HTTP hostname cannot carry it: Cloudflare ends TLS at its edge, which drops kubectl's client certificate. `cloudflared access tcp` on the workstation carries the connection to the edge after an Access login, and TLS stays end to end between kubectl and the API server.

1. Route the hostname to the API server. `tunnel sync` merges into the tunnel's configuration and places a new hostname ahead of any wildcard rule that would take its traffic (cloudflared uses the first rule that matches). Use a hostname an Access application covers: `devops cloudflare access status` lists them, and `devops cloudflare access sync --domain k8s.<domain> -e <email>` adds one.
   ```bash
   devops cloudflare tunnel sync --subdomains k8s --service tcp://kubernetes.default.svc.cluster.local:443 --dry-run
   devops cloudflare tunnel sync --subdomains k8s --service tcp://kubernetes.default.svc.cluster.local:443
   ```
   `k8s/cloudflared/networkpolicy.yaml` lets cloudflared reach the API server on 6443.
2. On the workstation, install `cloudflared` from `tools.lock` and open the local end of the route. The first connection prints an Access login URL to open.
   ```bash
   devops install-tools --tool cloudflared
   cloudflared access tcp --hostname k8s.<domain> --url 127.0.0.1:16443
   ```
3. Add a context that reaches the API server through it, with the credentials and CA of the cluster entry you use at home (`<cluster>` and `<user>` in `kubectl config view`):
   ```bash
   kubectl config set-cluster <cluster>-tunnel --server=https://127.0.0.1:16443 --tls-server-name=kubernetes.default.svc
   kubectl config set clusters.<cluster>-tunnel.certificate-authority-data "$(kubectl config view --raw -o jsonpath='{.clusters[?(@.name=="<cluster>")].cluster.certificate-authority-data}')"
   kubectl config set-context <cluster>-tunnel --cluster=<cluster>-tunnel --user=<user>
   kubectl --context <cluster>-tunnel get nodes
   ```

## Directory Structure

```
k8s/
├── kustomization.yaml        # Root kustomize: applies namespaces, cloudflared
├── namespaces.yaml           # Namespace definitions with Prune=false,Delete=false
├── agents/                   # Agent sessions: read-only ServiceAccount and view ClusterRoleBinding under restricted Pod Security
│   ├── kustomization.yaml
│   ├── serviceaccount.yaml   # ServiceAccount devops-agent in namespace agents with automount disabled
│   └── clusterrolebinding.yaml # ClusterRoleBinding devops-agent-view bound to ClusterRole view
├── argo-workflows/           # Argo Workflows controller and the --version WorkflowTemplate (#1535); not in the root kustomization
│   ├── kustomization.yaml    # The perimeter and the template, as Application argo-workflows-manifests syncs them
│   ├── values.yaml           # Helm values for argo/argo-workflows: one namespaced controller, minimal kept CRDs, restricted pods, the executor ServiceAccount
│   ├── networkpolicy.yaml    # Default-deny perimeter: the metrics scrape in, DNS and the API server out
│   └── workflowtemplate-version.yaml # WorkflowTemplate devops-cli-version: devops --version in the Service image, with no Secret
├── cloudflared/
│   ├── kustomization.yaml    # Kustomize overlay for Cloudflare Tunnel
│   ├── deployment.yaml       # Multi-replica non-root cloudflared deployment
│   └── networkpolicy.yaml    # Network isolation for tunnel ingress and egress
├── gitea/                    # Gitea, the internal forge and container registry (#1081); not in the root kustomization
│   ├── kustomization.yaml    # The perimeter, as Application gitea-manifests syncs it
│   ├── values.yaml           # Helm values for gitea-charts/gitea: SQLite in WAL mode, rootless, no SSH, packages on, no domain
│   └── networkpolicy.yaml    # Default-deny perimeter: HTTP 3000 from Traefik, Argo CD's repo server and the namespace; DNS out
├── devops/                   # In-cluster devops-cli runtime; not in the root kustomization
│   ├── kustomization.yaml    # Its resources; Image Updater sets the service image's digest on Application devops
│   ├── serviceaccount.yaml   # devops-cli service account without an API token
│   ├── configmap.example.yaml # devops-cli config template: deploy-stack renders ConfigMap devops-cli-config from it and config.yaml
│   ├── cronjob.yaml          # Suspended CronJob devops-cli, the template of every cluster job
│   ├── networkpolicy.yaml    # Default-deny perimeter: DNS, the gateway and public HTTPS out
│   └── roadmap-service/      # Continuous roadmap service Deployment, Service, Ingress, NetworkPolicy, PVC
│       ├── kustomization.yaml
│       ├── deployment.yaml
│       ├── ingress.yaml
│       ├── networkpolicy.yaml
│       ├── pvc.yaml
│       └── service.yaml
├── ingress/
│   ├── kustomization.yaml    # Kustomize overlay for cluster ingress routes
│   ├── traefik-values.yaml   # Traefik Helm values with ClusterIP service type
│   └── ingress-routes.yaml   # Ingress rules for chat, ai, grafana, argocd, git, prometheus, qdrant
├── argocd/
│   ├── kustomization.yaml    # Kustomize overlay for Argo CD
│   ├── values.yaml           # Helm values for argo/argo-cd
│   ├── image-updater-values.yaml # Helm values for argo/argocd-image-updater: the ImageUpdater for Application devops
│   ├── bootstrap/            # Two-level bootstrap applications
│   │   ├── bootstrap.yaml    # Root app tracking main, reconciles cluster app
│   │   └── cluster.yaml      # Cluster app tracking main, reconciles projects & leaf apps
│   └── apps/                 # AppProjects and 27 leaf Applications (11 raw + 16 Helm)
│       └── projects.yaml     # AppProjects: homelab and homelab-system
├── overlays/
│   └── homelab/              # Homelab overlays the Applications devops and ingress render; hosts stay under example.com
│       ├── ingress/          # Application ingress: k8s/ingress without the roadmap-service Ingress
│       └── devops/           # Application devops: k8s/devops
├── monitoring/
│   ├── kustomization.yaml    # Kustomize overlay for monitoring: NetworkPolicy and dashboards
│   ├── networkpolicy.yaml    # Default perimeter for the monitoring namespace
│   ├── dcgm-exporter-values.yaml # Helm values for nvidia/dcgm-exporter (GPU metrics)
│   ├── grafana-values.yaml   # Helm values for grafana-community/grafana (datasources, dashboard sidecar)
│   ├── k8s-monitoring-values.yaml # Helm values for grafana/k8s-monitoring (Alloy, kube-state-metrics, node-exporter, node journals, annotation autodiscovery, CoreDNS, profiling, and the Alloy, Grafana, Loki, Tempo and DCGM integrations)
│   ├── prometheus-operator-crds-values.yaml # Helm values for prometheus-community/prometheus-operator-crds (ServiceMonitor and other monitoring.coreos.com CRDs)
│   ├── prometheus-values.yaml # Helm values for prometheus-community/prometheus (server, Alertmanager and alert rules)
│   └── dashboards/
│       ├── kustomization.yaml # configMapGenerator: sidecar-labelled ConfigMaps for four dashboard groups
│       ├── k8s-views-global.json, k8s-views-pods.json # ConfigMap grafana-k8s-global-dashboards
│       ├── k8s-views-nodes.json, k8s-views-namespaces.json # ConfigMap grafana-k8s-node-dashboards
│       ├── devops-cli.json   # devops-cli commands, reviews, RAG and spend (grafana-devops-cli-dashboards)
│       ├── ai-spend.json     # AI spend and LLM usage (grafana-devops-cli-dashboards)
│       ├── project-metrics.json # Project & engineering velocity, release cadence and CI pass rates (grafana-devops-cli-dashboards)
│       ├── coredns.json      # CoreDNS traffic, latency, forwarders and cache; provisioned in grafana-stack-dashboards
│       ├── llm-stack.json    # LiteLLM gateway, GPUs and Qdrant; provisioned in grafana-stack-dashboards
│       ├── otel-collector.json # The collector's own telemetry; provisioned in grafana-stack-dashboards
│       └── prometheus-server.json # The Prometheus server; provisioned in grafana-stack-dashboards
├── otel/
│   ├── kustomization.yaml    # Kustomize overlay for OpenTelemetry
│   ├── networkpolicy.yaml    # Perimeter NetworkPolicy for otel namespace
│   ├── tempo-values.yaml     # Helm values for grafana-community/tempo
│   └── values.yaml           # Helm values for opentelemetry-collector
├── llm/
│   ├── kustomization.yaml    # Kustomize overlay for LLM stack base
│   ├── profiles/             # Ollama per-VRAM-tier DaemonSets and ollama-<n>gib Services (applied by deploy-stack)
│   ├── valkey.yaml           # Cache Valkey: Deployment, Service, NetworkPolicy
│   ├── valkey-runs.yaml      # Run index Valkey: PVC, Deployment, NodePort Service, NetworkPolicy
│   ├── values-open-webui.yaml# Helm values for open-webui/open-webui
│   ├── values-qdrant.yaml    # Helm values for qdrant/qdrant
│   └── gateway/              # LiteLLM gateway: Deployment, NodePort Service, NetworkPolicy, ServiceMonitor, and config.yaml, from which kustomization.yaml generates the routing ConfigMap
└── README.md                 # This file
```
