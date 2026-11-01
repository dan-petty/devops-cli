# k8s/ — Local Kubernetes Infrastructure & LLM Stacks

Kustomize + Helm-based configurations for deploying infrastructure management (`infra`) and local AI/LLM (`llm`) stacks to two clusters:

- the k3s homelab, which Argo CD keeps in line with `main` ([GitOps](#gitops));
- the devcontainer's minikube cluster, which `devops devcontainer post-start` starts.

`devops k8s deploy-stack` deploys the same configurations to either cluster.

## Stacks Overview

| Stack | Components | Namespaces | Default Ports |
| :--- | :--- | :--- | :--- |
| **`infra`** *(Default)* | ArgoCD (backed by Valkey), Argo Workflows controller, Grafana k8s-monitoring (Alloy + kube-state-metrics + node-exporter), Prometheus server, Grafana, Alertmanager, Grafana Pyroscope, NVIDIA DCGM Exporter, OpenTelemetry Collector, Grafana Tempo | `argocd`, `argo-workflows`, `monitoring`, `otel` | `8080` (ArgoCD), `8030` (Grafana), `8090` (Prometheus), `4040` (Pyroscope), `3200` (Tempo) |
| **`llm`** | Ollama (per-VRAM-tier DaemonSets), LLM Gateway (LiteLLM), Open-WebUI, Qdrant Vector DB, Valkey Cache | `llm` | `11434` (Ollama), `3000` (WebUI), `6333` (Qdrant), `6379` (Valkey) |
| **`logging`** | Loki (pod and journal logs shipped by the `infra` stack's Alloy `alloy-logs` DaemonSet) | `logging` | `3100` (Loki) |
| **`gitea`** | Gitea: the internal forge and container registry ([Gitea](#gitea)) | `gitea` | `3000` (Gitea HTTP, in the cluster) |
| **`chat`** | Mattermost Team Edition on CloudNativePG ([Mattermost](#mattermost)) | `mattermost`, `cnpg-system`, `mattermost-operator` | `8065` (Mattermost HTTP, in the cluster) |
| **`all`** | All components from the stacks above, and the `devops` stack | `argocd`, `argo-workflows`, `monitoring`, `otel`, `llm`, `logging`, `gitea`, `devops`, `mattermost`, `cnpg-system`, `mattermost-operator` | All ports above |

Register each manifest, Helm release and post-Helm step that runs in the cluster in `_MANIFESTS_BY_STACK`, `_HELM_RELEASES_BY_STACK` or `_POST_HELM_BY_STACK` (`src/devops_cli/commands/k8s/stack_lifecycle.py`), so that `devops k8s deploy-stack --stack all` deploys it with the `infra`, `llm`, `logging`, `devops`, `gitea` and `chat` stacks. deploy-stack applies a file of `_MANIFESTS_BY_STACK` with `kubectl apply -f` and a kustomization directory with `kubectl apply -k`.

## Prerequisites

- A cluster:
  - the k3s homelab: its nodes run k3s with the bundled local-path storage turned off (`--disable local-storage`);
  - or minikube running (`minikube status`, or started by `devops devcontainer post-start`).
- kubectl and helm on PATH (installed by devcontainer features)
- standard Kubernetes context configuration (the CLI uses `$KUBECONFIG` or defaults to `~/.kube/config`)
- A storage layer that serves the `local-path` StorageClass, which the claims of the stacks use:
  - On the homelab, the storage layer comes from the dan-petty/homelab repository: its `make storage` applies `k8s/manifests/local-path-storage.yaml`. That manifest holds namespace `local-path-storage`, the local-path provisioner (`rancher/local-path-provisioner` v0.0.28), the default StorageClass `local-path` (reclaim policy `Delete`) and the StorageClass `fast-nvme` (reclaim policy `Retain`). This repository does not deploy them. [Local-Path Volume Placement](#local-path-volume-placement) tells where the provisioner keeps a volume.
  - On minikube, the default `storage-provisioner` addon serves only the class `standard`. The class `local-path` comes from the `storage-provisioner-rancher` addon: `minikube addons enable storage-provisioner-rancher`. `devops devcontainer` does not enable it, so without it the claims that name `local-path` stay `Pending`.

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

On the homelab, each UI and API below has an Ingress host under the configured domain (`ingress/ingress-routes.yaml`, [Cloudflare Wildcard Tunnel & Ingress Routing](#cloudflare-wildcard-tunnel--ingress-routing)). On minikube, `minikube service` prints a URL for a Service. A `minikube service` command works only on minikube. `kubectl port-forward` works on both clusters.

### Infrastructure Stack (`infra`)
```bash
# ArgoCD UI. Homelab: https://argocd.<domain> (Ingress argocd/argocd-ingress). Minikube only:
minikube service argocd-server -n argocd --url
# Shell in a pod from the UI: open its Application, select the pod, then the Terminal tab

# ArgoCD initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo

# Monitoring Stack (Alloy Metrics & Scrapes). Homelab: https://alloy.<domain> (Ingress monitoring/alloy-metrics-ingress).
# The Service is a ClusterIP, so on minikube use a port-forward:
kubectl -n monitoring port-forward svc/k8s-monitoring-alloy-metrics 12345:12345

# Pyroscope Continuous Profiling UI
kubectl -n monitoring port-forward svc/pyroscope 4040:4040
```

### LLM Stack (`llm`)
```bash
# Ollama REST API of the fast tier (a speed Service; see GPU Placement: Ollama tiers)
kubectl -n llm port-forward svc/ollama-fast 11434:11434

# Open-WebUI Web Interface. Homelab: https://chat.<domain> (Ingress llm/open-webui-ingress). Minikube only:
minikube service open-webui -n llm --url

# Qdrant Vector Database HTTP API. It requires the key of llm/qdrant-api-key (see Cluster Secrets).
# Homelab: https://qdrant.<domain> (Ingress llm/qdrant-ingress). The Service is a ClusterIP, so on minikube use a port-forward:
kubectl -n llm port-forward svc/qdrant 6333:6333

# Valkey In-Memory Cache: Open WebUI's state. It requires the password of llm/valkey-auth (see Cluster Secrets).
kubectl -n llm exec -it svc/valkey -c valkey -- sh -c 'VALKEYCLI_AUTH="$VALKEY_PASSWORD" valkey-cli ping'

# devops-cli's cache Valkey: the embeddings and threat-intelligence reads of the Service and the cluster jobs.
# It requires the password of llm/valkey-devops-auth (see Cluster Secrets).
kubectl -n llm exec -it svc/valkey-devops -c valkey -- sh -c 'VALKEYCLI_AUTH="$VALKEY_PASSWORD" valkey-cli ping'

# Valkey Run Index (Argo CD's `llm` Application deploys it on the homelab; `devops k8s deploy-stack --stack llm` deploys it on either cluster; see Cluster Secrets for its password):
# benchmark and evaluation runs shared by workstations. Its password Secret comes from the keyring (see Cluster Secrets),
# then point devops-cli at it through its NodePort.
devops k8s push-secrets --only llm/valkey-runs-auth
devops ai runs connect

# LLM Gateway: authenticated OpenAI-compatible API for every Ollama model.
# Homelab: https://ai.<domain> (Ingress llm/llm-gateway-ingress), or its NodePort (below). Minikube only:
minikube service llm-gateway -n llm --url
```

### LLM Gateway (`llm-gateway`)
The LiteLLM gateway is the single entry point to every inference server. It serves the virtual models `devops-chat`, `devops-coder`, `devops-reasoning`, `devops-review` and `devops-triage`, plus models by name (`qwen3.8:27b`, `gemma4:31b`, `deepseek-r1:70b`, `qwen3-embedding:0.6b`). It checks each prompt against the window of every deployment before it calls a backend, so a prompt never reaches a deployment that would cut it (see below). It falls back from an unavailable `devops-coder` to `devops-reasoning` before the small Ollama model, and rejects requests without its master key. `devops k8s deploy-stack` writes the key (`llm/llm-gateway-secrets`, starting with `sk-`) from the keyring before the gateway starts, adopting a live key the keyring lacks and generating one where neither has it; `devops k8s push-secrets --only llm/llm-gateway-secrets` does the same alone (see Cluster Secrets).

The routing config is `llm/gateway/config.yaml`. LiteLLM reads it only at start. The gateway kustomization (`llm/gateway/kustomization.yaml`) generates ConfigMap `llm-gateway-config-<hash>` from that file, and writes the name into the Deployment. When the config changes, the name and the pod template change, and Kubernetes rolls the gateway onto the new config. Argo CD's `llm` Application renders the kustomization when it syncs, and `devops k8s deploy-stack --stack llm` applies it with `kubectl apply -k llm/gateway`. Thus a config change needs no `kubectl rollout restart` (#1929). Argo CD prunes the ConfigMap of the old config. Without Argo CD, that ConfigMap stays until `teardown-stack` deletes the namespace.

A workstation reaches the gateway through the Cloudflare tunnel, and the Cloudflare edge cuts a request that has no data for 125 s (#2365). The CLI therefore streams every OpenAI-compatible chat call, and the gateway writes an SSE comment (`: ping`) into a streamed reply that has no data for 30 s (`litellm_settings.sse_keepalive_ping_interval_seconds`), also before its first token. Thus a long prefill, queue or reasoning does not end the call. A ping sends the status line before the gateway has routed the call, so a call whose first token comes after the first ping has no `x-litellm-*` response headers, and its spend-ledger row names no serving backend. A failure after the first ping comes as an SSE error frame under status 200, and the client reports it as the HTTP status that the frame names.

The Service is a NodePort that Kubernetes assigns; find it with `kubectl -n llm get svc llm-gateway`, then call the API from any node address:
```bash
KEY=$(kubectl -n llm get secret llm-gateway-secrets -o jsonpath='{.data.master-key}' | base64 -d)
curl -H "Authorization: Bearer $KEY" http://<node>:<node-port>/v1/models
```
Each `ollama_chat` deployment sets `max_input_tokens` in its own top-level `model_info`, equal to the `OLLAMA_CONTEXT_LENGTH` of its tier, and `devops ai gateway render` keeps the two equal. LiteLLM reads the window only from that place: a `model_info` under `litellm_params` has no effect. A deployment that sets no window reads the cost-map entry of its backend model, which the last deployment registered wrote. Thus each deployment sets its own window, and a test holds this (#2825). Ollama cuts a prompt that is longer than its window and returns no error, so the check is the only guard. The gateway sets no `context_window_fallbacks`: `devops-chat`, `devops-coder` and `devops-reasoning` run on `ollama-48gib-fast`, which has the largest window, 262,144 tokens, so none of them could take a prompt that another of them refused. A prompt longer than the window of `devops-background` (128,000) or `devops-triage` (160,000) moves on along the plain fallbacks to `qwen3.8:27b`, which has a 262,144 deployment on `ollama-48gib-fast`. A prompt fails with a context-window error only when no group of the chain holds it.

These groups route reviews, embeddings and background work:

- `devops-review` spreads one model name over three Ollama tiers: `qwen3-coder:30b` on `ollama-48gib-fast` and `ollama-64gib-standard`, and `gpt-oss:20b` on `ollama-16gib-fast`. The router sends each request to the deployment with the fewest requests in flight (`least-busy`), and pre-call checks keep a prompt off any deployment whose window it exceeds: a prompt of 140,000 tokens reaches `ollama-48gib-fast` or `ollama-64gib-standard`, and a prompt above 160,000 tokens reaches `ollama-48gib-fast` alone. No deployment is capped with `max_parallel_requests`: LiteLLM waits on the cap only after routing, so queued requests pile up behind it while larger servers idle, and the backends queue excess requests themselves.
- Ollama models are also served under their own names: `qwen3.8:27b`, `gemma4:31b`, `deepseek-r1:70b`, and the embedding model `qwen3-embedding:0.6b`. An embedding group configures `model_info.mode: embedding` so health checks embed rather than generate.
- `qwen3-embedding:0.6b` has one deployment on each serving tier, and LiteLLM's `order` sets which the router tries first. The gateway routes the embedding group with `simple-shuffle` across order 1 deployments (#2027). Order 1 is `ollama-48gib-fast` and `ollama-64gib-standard`, which embed a 32-chunk RAG batch in under 5 s beside their chat model. Order 2 is `ollama-16gib-fast`, whose chat model leaves no VRAM for the embedder, and `ollama-48gib-slow`, which takes 12 to 30 s. The router sends a request to order 2 only when every order 1 deployment fails. Each deployment sets `num_ctx` to `CONST_RAG_MAX_CHUNK_TOKENS` (8,192), so the largest RAG chunk fits. With its 32,768-token default, the embedder takes 5.2 GB, not 2.9 GB, on `ollama-64gib-standard`. These tiers keep two models loaded, so the embedder stays beside the chat model where both fit, and each must hold the model: `kubectl -n llm exec ds/<tier> -c ollama -- ollama pull qwen3-embedding:0.6b`.
- `qwen3-coder:30b` and `gpt-oss:20b` each pin one of `devops-review`'s models: the group copies that model's `devops-review` deployments with their windows, and has no fallback, so a review measured on one model is routed as the pool routes it.
- `devops-triage` is the fast triage model for candidate intake: `qwen3.8:27b` on `ollama-64gib-standard`. It serves candidate triage alone so backlog placement completes within one poll round. The router falls back to `qwen3.8:27b` if unavailable.
- `devops-background` is the background tier's one generation model: `qwen3.8:27b` on `ollama-48gib-slow`. That tier serves one request at a time, so it is in no interactive or review pool, where background work would queue in front of review calls. It keeps its embedding model and `qwen3.8:27b` loaded together and is sent no other model. The router falls back to `qwen3.8:27b` if unavailable. In-cluster services (`k8s/devops/` such as `roadmap-service` and cluster jobs) and `devops-review` fallback reach it; the pinned groups have no fallback. The client streams the call and the gateway's pings keep it open, so the client reads the reply of a `devops-review` call that falls back to this tier. Use it for `devops review path --watch`, `devops ai pipeline`, `devops ai agents` and `devops ai analyze` through environment overrides, never in workstation `config.yaml`, so no interactive run lands on it. Set `DEVOPS_CLI_AI_MAX_RETRIES=1`; the ConfigMap template of `k8s/devops/` sets `ai.max_retries: 1` for the in-cluster services, and `devops k8s deploy-stack --stack devops` applies it (Roadmap service, Go-live check). The gateway stops a call when the tier sends no token for 1,100 s, and does not retry it. The client retries a call that fails or times out before its reply starts in its HTTP transport, the single retry layer, `ai.max_retries + 1` times, and each retry waits for the same single slot. A call that fails after its reply starts is not retried. With `1` a call is sent at most two times; `0` does not stop retries, because the transport then makes five attempts:
  ```bash
  DEVOPS_CLI_AI_MAX_RETRIES=1 DEVOPS_CLI_AI_TASK_ANALYSIS_MODEL=devops-background \
    DEVOPS_CLI_AI_TASK_COMPOSE_MODEL=devops-background devops review path src --watch --concurrency 1
  DEVOPS_CLI_AI_MAX_RETRIES=1 DEVOPS_CLI_AI_TASK_CHAT_MODEL=devops-background devops ai pipeline "<goal>"
  DEVOPS_CLI_AI_MAX_RETRIES=1 DEVOPS_CLI_AI_MODEL=devops-background devops ai agents   # likewise devops ai analyze
  ```

Measure the `devops-review` backends again whenever a backend, model or node changes. `devops ai gateway tune` measures each deployment of a group on its own, from an ephemeral Python container attached to the gateway pod (`kubectl debug`), so each backend is measured over the gateway's own network path. For each deployment it reports the engine, the GPUs, the capacity (fixed-length tokens per second at the best concurrency) and the cost (the tokens the model writes per request). It changes nothing. The `least-busy` router reads none of these numbers: it sends each request to the deployment with the fewest requests in flight. Use the numbers to decide which backends a group holds. The command also prints a weight and a concurrency for each deployment. This gateway uses neither, because no deployment sets `weight` or `max_parallel_requests`:
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

Open WebUI uses the same key: on a fresh install it connects to the gateway automatically, and it sends its RAG embeddings to the gateway's `qwen3-embedding:0.6b`. An existing installation keeps the connections and the document settings stored in its database. Add `http://llm-gateway.llm.svc.cluster.local:4000/v1` under Admin Panel > Settings > Connections, and turn off the Ollama API there: Open WebUI has no connection to Ollama's native API, so each of its model calls is on the gateway's series that the AI spend dashboard reads. Under Admin Panel > Settings > Documents, set the embedding engine to OpenAI, with the gateway URL, the master key and `qwen3-embedding:0.6b`.

### GPU Placement: Ollama tiers
Ollama runs as one DaemonSet per total-VRAM tier (`ollama-16gib` … `ollama-128gib`, `llm/profiles/ollama-profiles.yaml`), each behind its ClusterIP Service `ollama-<n>gib`. The gateway reaches the tiers through aliases of those Services, `ollama-16gib-fast`, `ollama-48gib-fast`, `ollama-48gib-slow` and `ollama-64gib-standard` (`llm/gateway/config.yaml`).

The speed Services `ollama-fast`, `ollama-standard` and `ollama-slow` (`llm/profiles/services.yaml`) name no VRAM size. Clients of Ollama's native API use them: `ollama-fast` is the `ollama-ingress` backend and the CLI's default Service (`devops k8s port-forward`, `configure-urls`). Open WebUI uses none of them: it sends its chats and its RAG embeddings to the gateway. When a host changes, change the selector of the speed Service. Its clients then follow with no edit. [llm/profiles/README.md](llm/profiles/README.md) describes the profiles and their Services.

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

**Serves** says whether a node of the cluster satisfies the tier, so that the tier has a pod. Every client that names an Ollama Service names one that selects a serving tier: the CLI defaults, the `ollama-ingress` backend, the gateway's `api_base` targets and the devcontainer's `ollama.endpoint`. `tests/test_k8s_llm_gateway.py` checks this against the column. When a host goes offline or a tier gets a node, change the column. The test then names each client to move.

**What sets the labels.** The cluster's node-provisioning automation, which lives outside this repository, sets `nvidia.com/gpu.present` and `nvidia.com/gpu.architecture` on every GPU node. It sets `nvidia.com/gpu.total-vram-gib` only on a node with more than one GPU, as the sum of its GPUs' memory rounded to the nearest whole GiB. GPU Feature Discovery labels per-GPU memory and the GPU count, not a total. So a single-GPU node gets no total, and a multi-GPU total can come out as a value no tier lists, such as `47Gi`. Set the label by hand, with a value from the table:

```bash
kubectl label node <node> nvidia.com/gpu.total-vram-gib=<N>Gi --overwrite
```

`deploy-stack --stack llm` reads the nodes once, right after it checks the cluster is reachable, and warns about each GPU node no tier accepts: the missing or unaccepted `total-vram-gib` with the command above, or an `architecture` outside the accepted ones. If no node satisfies any tier, it says no Ollama pod will schedule, and if it cannot read the nodes it says it could not check the labels. It also warns on an Argo CD-managed cluster. It never stops the deploy, since the stack's other workloads need no GPU label. The accepted values are read from `ollama-profiles.yaml`, so a tier changed there is checked with no other edit.

The gateway's policy `llm-gateway-perimeter` (`llm/gateway/networkpolicy.yaml`) is applied with the llm manifests, by `deploy-stack` or Argo CD's `llm` Application. It admits TCP 4000 from any source, since LiteLLM rejects a request without the master key, and limits the gateway's egress to the pods labelled `llm.devops.io/provider: ollama` on 11434 and kube-system DNS on port 53.

The cache Valkey's policy `valkey-perimeter` (`llm/valkey.yaml`) admits Open WebUI on TCP 6379 and the `monitoring` namespace on the exporter port 9121. It allows no egress, and `llm-default-perimeter` leaves the Valkey pods out. Valkey requires the password of `llm/valkey-auth` (see Cluster Secrets). Open WebUI sends it in its Redis URL, and Valkey reads it from a quoted config line. A typed value must therefore use only letters, digits, `-`, `.`, `_` and `~`. The gateway and Portkey use no Valkey: the gateway config turns on no cache, and Portkey reads a cache only from `REDIS_CONNECTION_STRING`, which is not set.

The cache Valkey keeps at most 1536 MiB of data (`--maxmemory`), three quarters of its 2048Mi limit. The rest of the limit holds fragmentation and Valkey's own overhead. At the bound, Valkey refuses writes and evicts no key (`--maxmemory-policy noeviction`). Open WebUI keeps its session pools and token revocations there, and an evicted revocation makes a signed-out token valid again. The run index (`llm/valkey-runs.yaml`) uses the same policy with a bound of 512 MiB. `ValkeyMemoryNearBound` warns when the cache Valkey keeps its data above 80% of the bound for 10 minutes. The rule selects each exported Valkey with the policy `noeviction`, and the run index has no exporter, so the rule does not watch it.

devops-cli's cache Valkey (`llm/valkey-devops.yaml`) holds the caches of the roadmap Service and the cluster jobs: the embeddings that `EmbeddingsEngine` writes, and the threat-intelligence reads. Each round of the Service and each job is a new process with an empty memory cache, so without it intake embeds every item of the roadmap again on each round. The devops ConfigMap names it in `valkey.url`, and its password reaches the pods from `devops/devops-cli` as `DEVOPS_CLI_VALKEY_PASSWORD`, the variable of `valkey.password`. Its policy `valkey-devops-perimeter` admits namespace `devops` on TCP 6379 and the `monitoring` namespace on the exporter port 9121, and allows no egress. `llm-default-perimeter` leaves its pods out, and `devops-default-perimeter` lets namespace `devops` reach namespace `llm` on 6379 beside the gateway's 4000. It keeps at most 96 MiB of data, three quarters of its 128Mi limit, writes no RDB or AOF, and at the bound evicts the least recently used key (`--maxmemory-policy allkeys-lru`): an evicted key costs one more embedding request. It can't share the cache Valkey, which must not evict Open WebUI's state.

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
| dcgm-exporter | Its own `dcgm-exporter` chart (`monitoring/dcgm-exporter-values.yaml`) | k8s-monitoring's dcgm-exporter integration scrapes the exporter but ships none, so the chart deploys it on every GPU node; the chart's own ServiceMonitor stays off. The exporter collects the fields that `customMetrics` lists, and `podAnnotations` holds the checksum of that list, so a changed list restarts the pods |
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

The AI spend dashboard counts every caller of the gateway, not only devops-cli. AI Requests in Range and Tokens Processed in Range take a call through the gateway from the gateway's own series (`litellm_proxy_total_requests_metric_total` with a 2xx `status_code`, and `litellm_total_tokens_metric_total`), and add from devops-cli's series only its calls that bypassed the gateway. The Gateway Traffic from Every Caller row shows the gateway's attempts by status, so a 408 or a 5xx is visible, and its requests and tokens by `end_user`. Every caller sends the gateway's one master key, so the gateway tells callers apart by the end-user id that a request names: devops-cli sends its OTel service name (`devops-cli`, `devops-cli-job` or `roadmap-service`) in `x-litellm-end-user-id`, and the gateway config sets `enable_end_user_cost_tracking_prometheus_only` to put it on the `end_user` label. A caller that names no end user, such as Open WebUI, shows as `unnamed`. The coverage stat is devops-cli's own count of its replied gateway calls over the gateway's count.

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

Both volumes use the `local-path` class. It keeps a volume in a directory on one node ([Local-Path Volume Placement](#local-path-volume-placement)), does not hold the volume to its claimed size, and cannot expand a claim in place. Loki's claim comes from its StatefulSet's `volumeClaimTemplates`, which Kubernetes does not let an upgrade change, so a new `singleBinary.persistence.size` needs the StatefulSet deleted with `--cascade=orphan` and the volume rebound to the new claim before the upgrade.

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

The StorageClasses `local-path` and `fast-nvme` use the local-path provisioner ([Prerequisites](#prerequisites)). It keeps a volume in a directory on one node, and it binds the volume on the node where the first pod of the claim runs (`WaitForFirstConsumer`). The volume then keeps each later pod of the claim on that node. The root disk of the control-plane node is the smallest in the cluster, and it also holds the model store of the slow Ollama tier (GPU Placement, above). So each pod that mounts a claim has this required node affinity:

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

`tests/test_k8s_local_path_placement.py` fails when a pod that mounts a claim has no such affinity, in a chart values file or in a manifest under `k8s/`. It also fails when an Argo CD Application installs a chart that the test does not know, because each chart keeps its claims and its affinity at different values. A pod that must stay on the control-plane node is in `_CONTROL_PLANE_CLAIM_EXEMPTIONS` of the test, with its reason. Grafana (claim `grafana`), the Prometheus server (`prometheus-server`) and Loki (`storage-loki-0`) are in it, because their volumes are on the control-plane node, and with the affinity their pods cannot start. Move each volume as below, then remove its exemption and add the affinity to its values in one pull request.

On the homelab, the provisioner's config (ConfigMap `local-path-config` in namespace `local-path-storage`) gives each node two base directories, one under `/var` and one under `/mnt`. Neither StorageClass names one of them (`parameters.nodePath`), so the provisioner (v0.0.28, `getPathOnNode`) puts each new volume under one of the two at random. Thus `fast-nvme` differs from `local-path` only by its reclaim policy, `Retain`: it does not keep a volume on a faster disk.

`LocalPathNodeDiskHigh` (Alerting, below) warns when the root filesystem of a node that runs a pod on a `local-path` claim is over 85% used. At 85% the kubelet starts to delete unused images. Under DiskPressure it evicts pods, and a pod on a local-path volume cannot start on another node. The alert reads only the root filesystem (`mountpoint="/"`). When the `/mnt` base directory is on another filesystem, `HostFilesystemSpaceLow` watches that filesystem.

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

## Service Account Tokens

Kubernetes mounts a token of the pod's ServiceAccount into each pod. A process in the pod can then call the Kubernetes API as that ServiceAccount. The pod field `automountServiceAccountToken: false` stops the mount. When the pod does not set the field, the field of the ServiceAccount applies. A volume can also give the pod a token, whatever the field says: a projected `serviceAccountToken` source, or a Secret of type `kubernetes.io/service-account-token`. A pod that does not call the API mounts no token (#1652):

- The manifests set the field to `false` on the pod template of each workload that does not call the API. Examples are `cloudflared`, `gpu-feature-discovery`, `llm-gateway`, `portkey`, `valkey`, `valkey-runs` and the Ollama tiers.
- The chart values turn the token off for Loki (`defaults` and `serviceAccount`), Tempo and the OpenTelemetry collector (`serviceAccount`). They also turn it off for Alertmanager (`alertmanager`), and for the Argo CD repo server and Redis (`repoServer` and `redis`). Gitea gets its own ServiceAccount (`serviceAccount.create: true`), which has no token.
- A pod that calls the API keeps its token, and a Role or ClusterRole binds its ServiceAccount. Examples are Argo CD, Argo Workflows, Grafana, the k8s-monitoring collectors, the Prometheus server, Pyroscope and Traefik.

`tests/invariants/test_k8s_manifests.py` reads the manifests under `k8s/` and the values of each chart that an Argo CD Application installs. It fails in these cases:

- A pod mounts a token, and no Role or ClusterRole binds its ServiceAccount.
- An Application installs a chart, or a chart version, that the test does not know. Each chart keeps the field at different values, and a chart release can move it. When you change the version of a chart, read its token values again with `helm template`. Then change the entry of the test.
- An Application gives a chart values that are not in its values files. The test reads the files only.
- A kustomization patches a workload, a ServiceAccount, a Secret, a binding or a claim.

A pod that keeps a token with no binding is in `_TOKEN_EXCEPTIONS` of the test, with its reason:

- Qdrant: chart 1.19.1 has no value for the field. qdrant/qdrant-helm#506 asks for the value. When a chart release adds it, set the value and remove the exception in one pull request.
- The CoreDNS patch (`coredns/deployment-patch.yaml`): k3s makes the CoreDNS Deployment, its ServiceAccount and its binding. CoreDNS reads Services and EndpointSlices through the API.

`kubectl get pods -A -o json` shows a `kube-api-access-*` volume only on the pods that keep a token.

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

Alertmanager runs from the prometheus chart (`alertmanager` in `monitoring/prometheus-values.yaml`), and Grafana reads it as the `Alertmanager` datasource. The rules are in the same file, under `serverFiles.alerting_rules.yml`; `tests/test_k8s_monitoring_alerting.py` pins them and checks that each selects only series that a scrape or the OpenTelemetry collector in `k8s/` serves. No rule watches the controller manager, scheduler or proxy: k3s runs them inside its server process, so nothing scrapes them and such a rule would fire on the missing target.

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
| `OtelCollectorExportFailing` | An exporter of the OpenTelemetry collector failed to send spans, metric points or log records to Tempo, Prometheus or Loki in each of two 15-minute periods in a row; it names the exporter and the signal | 15m | warning |
| `OtelCollectorExportQueueFull` | An exporter queue of the OpenTelemetry collector is at 90% or more of its capacity; a full queue drops new data | 15m | warning |
| `ArgoCdApplicationOutOfSync` | An Argo CD Application's `sync_status` is not `Synced` | 15m | warning |
| `ArgoCdApplicationUnhealthy` | An Argo CD Application's `health_status` is neither `Healthy` nor `Progressing` | 15m | warning |
| `ArgoCdAutoSyncDisabled` | An Argo CD Application's `autosync_enabled` is `false` | 15m | warning |
| `ArgoCdSyncOperationStuck` | An Argo CD Application has a sync operation running | 1h | warning |
| `IngressServesPlaceholderHost` | An Ingress routes a host under the placeholder domain of git (`kube_ingress_path`), so Traefik returns 404 for its real host; see Homelab Values at Deploy Time | 5m | critical |
| `CloudflareTunnelDegraded` | Total Cloudflare Tunnel HA connections across `cloudflared` replicas are under 2 | 5m | warning |
| `CoreDnsServfailResponses` | Over 5% of CoreDNS responses return `SERVFAIL` | 5m | warning |
| `ValkeyCacheErrors` | A Valkey exporter reports `redis_up == 0` or rejected client connections | 5m | warning |
| `ValkeyMemoryNearBound` | A Valkey with the policy `noeviction` and a bound keeps its data above 80% of its `maxmemory`; at the bound it refuses each write | 10m | warning |
| `RoadmapServiceIdentityRefused`, `RoadmapServiceGitHubThrottled` | GitHub refused the identity of the roadmap Service, or throttled its requests; see Roadmap service, Alerts | — | critical |
| `RoadmapServiceJobsFailing` | All jobs of one repository and lane failed in 1 hour | 30m | warning |
| `RoadmapServiceLaneStalled`, `RoadmapServiceRestarted`, `RoadmapServiceUnavailable`, `RoadmapServiceGitHubRequestsHigh`, `RoadmapServiceModelRequestsHigh` | The roadmap Service stalls, its pod restarts or is unavailable, or its GitHub or model requests in an hour are high; see Roadmap service, Alerts | 0–10m | warning |
| `RoadmapServiceWebhooksRejected` | The webhook route of the roadmap Service rejected more than 20 deliveries in 15 minutes; see Roadmap service, Alerts | — | warning |
| `ClusterMetricsMissing` | `kube_node_status_condition` is absent, so the node rules cannot fire | 10m | critical |
| `PrometheusConfigReloadFailed`, `PrometheusRuleEvaluationFailures`, `PrometheusNotConnectedToAlertmanager`, `PrometheusDroppingAlerts`, `PrometheusCompactionsFailing` | Prometheus's own health | 0–15m | warning |
| `AlertmanagerConfigReloadFailed`, `AlertmanagerNotificationsFailing` | Alertmanager's own health; the second only once the alertmanager-mattermost Secret exists | 10m, 15m | warning |

Retention, volume sizes and what `LogOrMetricVolumeDiskLow` and `PrometheusNearRetentionSizeCap` watch are in Log and Metric Retention, above.

The local-path volumes are host directories. They report no kubelet volume stats and do not enforce their claim's size, so the host filesystem under them is what fills. `HostFilesystemSpaceLow` watches every filesystem of every node; `LogOrMetricVolumeDiskLow` watches the same 10% on the root filesystem of the node holding Loki's and Prometheus's claims and names the claim at risk, so on that node both fire. For Prometheus, `PrometheusNearRetentionSizeCap` warns before its size cap deletes anything, `PrometheusSizeLimitCutHistory` once it has, and `PrometheusStorageNearClaim` if the data outgrows the claim with no cap holding it.

The GPU power budget is one number for the whole site, from the GPUs' draw before a breaker trip on the circuit every node shared. Once the power layout is settled, it should become one budget per circuit.

### Receiver

Alerts without a routed severity go to the `null` receiver, which sends nowhere. `critical` and `warning` alerts go to `mattermost`, which posts to Mattermost's incoming webhook using the URL in the `url` key of the Secret `alertmanager-mattermost` in `monitoring`. The Secret is mounted optional, as a directory, at `/etc/alertmanager-mattermost`, so Alertmanager starts without it and the running pod sees the file about a minute after the Secret is created. Until then each notification fails, Alertmanager logs the failure, and nothing leaves the cluster. No alert arrives while Mattermost, Alertmanager, or the node under either is down (#1390).

To wire the channel:

1. Create the incoming webhook in Mattermost for `alerts`, with "Lock to this channel" selected.
2. Store the webhook token in the keyring:
   ```bash
   uv run devops config set mattermost.alerts_hook
   ```
3. Push the Secret to the cluster:
   ```bash
   uv run devops k8s push-secrets --only monitoring/alertmanager-mattermost --context <context>
   ```

The monitoring perimeter allows Alertmanager egress to namespace `mattermost` on TCP port 8065, and ports 80 and 443 outside the cluster.

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
| `llm/valkey-devops-auth` | `password` | keyring `valkey_devops_password` | yes | adopt the live value; else generate 64 hex | llm | `deployment/valkey-devops` |
| `cloudflared/cloudflared-token` | `token` | keyring `cloudflare_tunnel_token` | no | adopt the live value; else skip with a warning | base | `deployment/cloudflared` |
| `devops/devops-cli` | `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` | keyring `service_github_app_private_key` | yes | adopt the live value; else fail | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_AI_API_KEY` | keyring `llm_gateway_master_key` | yes | adopt from `llm/llm-gateway-secrets master-key`; else fail | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS` | keyring `service_webhook_secrets` | no | adopt the live value; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_FIRECRAWL_API_KEY` | keyring `firecrawl_api_key` | no | adopt the live value; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_VALKEY_PASSWORD` | keyring `valkey_devops_password` | yes | adopt from `llm/valkey-devops-auth password`; else generate 64 hex | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN` | keyring `mattermost_command_token` | no | adopt the live value; else skip with a warning | devops | `deployment/roadmap-service` |
| `monitoring/grafana-admin` | `admin-user` | literal | yes | fail | infra | `deployment/grafana` |
| `monitoring/grafana-admin` | `admin-password` | keyring `grafana_password` | yes | adopt from `monitoring/grafana admin-password`; else generate `token_urlsafe(32)` | infra | `deployment/grafana` |
| `monitoring/alertmanager-mattermost` | `url` | derived from keyring mattermost_alerts_hook | no | skip with a warning | infra | none |
| `argocd/argocd-notifications-secret` | `github-appID` | setting argocd.github_app_id | no | skip with a warning | infra | none |
| `argocd/argocd-notifications-secret` | `github-installationID` | setting argocd.github_app_installation_id | no | skip with a warning | infra | none |
| `argocd/argocd-notifications-secret` | `github-privateKey` | keyring `argocd_github_app_private_key` | no | adopt the live value; else skip with a warning | infra | none |
| `argocd/argocd-notifications-secret` | `mattermost-deploys-url` | derived from keyring mattermost_deploys_hook | no | skip with a warning | infra | none |
| `gitea/gitea-admin` | `username` | literal | yes | fail | gitea | `deployment/gitea` |
| `gitea/gitea-admin` | `password` | keyring `gitea_admin_password` | yes | adopt the live value; else fail | gitea | `deployment/gitea` |
| `mattermost/mattermost-db` | `username` | literal | yes | fail | chat | none |
| `mattermost/mattermost-db` | `password` | keyring `mattermost_db_password` | yes | adopt from `mattermost/mattermost-db password`; else generate `token_urlsafe(32)` | chat | none |
| `mattermost/mattermost-db` | `DB_CONNECTION_STRING` | derived from literal, keyring mattermost_db_password | yes | fail | chat | none |

- The keyring must be unlocked (`devops devcontainer unlock-keyring`); a locked or missing keyring stops the push before anything is read or written, and stops deploy-stack before it applies anything.
- A value the keyring lacks but the cluster holds is adopted into the keyring, so a first push changes nothing live. Only values nobody types are generated, and each is stored in the keyring before it is pushed.
- Typed values are stored at a hidden prompt: `devops config set cloudflare.tunnel_token` or `devops config set gitea.admin_password`.
- A derived entry is built from other values of the same push, such as a connection string from a user and a password. The push resolves every other entry first, then fills each field of the entry's template with the value of its input, quoted with `urllib.parse.quote(..., safe="")`. It never adopts, generates or stores a derived value, and a live value that differs needs `--rotate`. `--plan` names the source as `derived from` and its inputs, and `--dry-run` shows a placeholder.
- A row may name its Secret type, such as `kubernetes.io/basic-auth`. The default is `Opaque`. Kubernetes cannot change the type of an existing Secret, so a row names its type before its first push.
- `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` is the private key of GitHub App `devops-cli-service`, which the roadmap Service and the cluster Jobs act as ([ADR 0015](../docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md)). Store it with `devops config set service.github_app.private_key --from-file <key.pem>`. A pod whose environment holds the key acts as the App: it mints an installation token, mints a new one before the token expires, and gives the current token to each gh and git child as GH_TOKEN. A workstation keeps the key only in the keyring, so a workstation run keeps the gh login of its person.
- `argocd/argocd-notifications-secret` holds the GitHub App that Argo CD's GitHub notifier acts as, and the webhook URL for Mattermost deploys. Its `service.github` refers to the keys as `$github-appID`, `$github-installationID` and `$github-privateKey`, and `service.webhook.mattermost` refers to `$mattermost-deploys-url`. Store the values with `devops config set argocd.github_app_id <id>`, `devops config set argocd.github_app_installation_id <id>`, `devops config set argocd.github_app_private_key --from-file <key.pem>`, and `devops config set mattermost.deploys_hook`, then run `devops k8s push-secrets --only argocd/argocd-notifications-secret`. The Argo CD values set `notifications.secret.create: false`, so the chart never creates a Secret of the same name, and the `homelab` project ignores the pushed Secret as an orphan.
- `monitoring/alertmanager-mattermost` holds the incoming webhook URL that Alertmanager uses to post critical and warning alerts to Mattermost. Store the webhook token with `devops config set mattermost.alerts_hook`, then push with `devops k8s push-secrets --only monitoring/alertmanager-mattermost`. The `homelab` project ignores the Secret as an orphan.
- `DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN` holds the authentication token that verifies `/roadmap` slash command requests from Mattermost to the Service's webhook router. Store the token with `devops config set mattermost.command_token`, then push with `devops k8s push-secrets --only devops/devops-cli`.
- `devops` rows are pushed wherever namespace `devops` exists, also by every deploy-stack run. `devops k8s deploy-stack --no-push-secrets` skips the push on a cluster without a keyring.
- `gitea` rows are pushed by `push-secrets` with no `--stack` or with `--stack gitea`, and by `deploy-stack --stack gitea` or `all`. The root kustomization creates namespace `gitea` on every cluster, so these pushes need the Gitea admin password in the keyring. A deploy of another stack never reads it.
- `chat` rows are pushed by `push-secrets` with no `--stack` or with `--stack chat`, and by `deploy-stack --stack chat` or `all`. The database password is generated or adopted, and `DB_CONNECTION_STRING` is derived from it. The `homelab` project ignores the Secret as an orphan.
- Secrets are server-side applied from stdin under field manager `devops-cli`, labelled `app.kubernetes.io/managed-by: devops-cli`, with values in `data`: never in argv, a file, an annotation or the output. A Secret still carrying a client-side apply's `kubectl.kubernetes.io/last-applied-configuration` loses it.
- `--plan` reads the keyring and the live Secrets, says so, and prints each key's state (`would adopt`, `unchanged`, `differs`, ...) and the workloads a change would restart, writing nothing. `--dry-run` makes no request at all, not even those reads: it prints the requests a push would make, in order, with `<placeholders>` for every value and the condition under which each later request runs.
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
devops config set service.github_app.app_id <app-id>    # the GitHub App the jobs act as (ADR 0015)
devops config set service.github_app.installation_id <installation-id>
devops config set service.github_app.slug devops-cli-service
devops config set service.github_app.private_key --from-file <key.pem>
devops k8s deploy-stack --stack devops --context <context>
devops k8s push-secrets --context <context> --plan       # reads the keyring and the cluster: key names and states, never a value
devops k8s push-secrets --context <context>
devops k8s run-job --context <context> -- --version      # follows the log, exits with the Job's exit code
devops k8s run-job --context <context> --no-wait -- ai gateway status --format json
```

`run-job --dry-run` reads nothing, not even the CronJob, and prints the kubectl requests a run would make. `run-job` creates the Job from suspended CronJob `devops-cli` (`--template default`) or, with `--template runner`, from suspended CronJob `devops-cli-runner` (Runner Jobs), changing only the container's args, the name (`devops-cli-<UTC time>-<hex>`, and `devops-cli-runner-<UTC time>-<hex>` for a runner Job) and the label `app.kubernetes.io/name: devops-cli-job`. A Job never retries (`backoffLimit: 0`), stops after two hours and is deleted a day after it finishes. Follow or clean up Jobs with kubectl:
```bash
kubectl -n devops get jobs -l app.kubernetes.io/name=devops-cli-job
kubectl -n devops logs -f job/<name>
```

### Roadmap service

`deployment/roadmap-service` runs one replica. The Service acts as GitHub App `devops-cli-service`, which the personal account owns ([ADR 0015](../docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md)), on each repository in `service.repos`. Labels and milestones hold the roadmap state ([ADR 0016](../docs/adr/0016-labels-hold-the-roadmap-items-fields.md)). Argo CD self-heals the deployment, so only a change in git changes its replica count. A scale by hand stays only after the stop switch turns off automated sync.

1. Create the GitHub App on the personal account (Settings > Developer settings > GitHub Apps > New GitHub App): name `devops-cli-service`, webhook off, "Only on this account". The roadmap jobs need these repository permissions: Issues read and write, Pull requests read and write, Contents read and write, Checks read, Actions read, Metadata read. The owner's App has read and write on every repository permission ([ADR 0015](../docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md) records the risk). Each installation token that the Service and the Jobs mint is scoped to the permissions above, whatever the App grants, so the App must grant at least those: GitHub refuses a token with HTTP 422 when the installation does not grant one of them. Install it on each managed repository, and generate a private key. The App page shows the App ID, and the installation's settings page has the installation ID at the end of its URL.
2. `uv run devops config set service.repos <owner/name>` (each repository the service works for), then `uv run devops config set service.webhook_secrets` (hidden prompt; a JSON object mapping `owner/name` to its secret). Set the App with `uv run devops config set service.github_app.app_id <app-id>`, `service.github_app.installation_id <installation-id>`, `service.github_app.slug devops-cli-service` and `service.github_app.private_key --from-file <key.pem>`, then delete the downloaded key file. deploy-stack refuses the devops stack until `service.repos` and the App's settings are set.
3. `uv run devops k8s push-secrets --stack devops`. It writes the App's private key to Secret `devops/devops-cli`. deploy-stack also pushes it once namespace `devops` exists.
4. Check that the GHCR `service` package is public (#741 made it so): `DOCKER_CONFIG=$(mktemp -d) docker pull ghcr.io/dan-petty/devops-cli/service:<tag>`.
5. `devops cloudflare tunnel routes`. If no route covers the webhook host, add one in the dashboard, not with `tunnel sync` (#794).
6. `devops cloudflare access status`, then add a Bypass application for `hooks.<domain>/webhooks/github`.
7. `devops k8s deploy-stack --stack devops` (or `--stack all`).
8. Add each repo's webhook: `https://hooks.<domain>/webhooks/github`, `application/json`, that repo's secret, and only the Issues event. The roadmap consumer takes the Issues event. An issue that opens, edits or reopens runs intake of that one issue on the model lane at once and queues no full round ([ADR 0017](../docs/adr/0017-each-subscribed-webhook-event-runs-the-update-scoped-to-it.md), #1533). The 5-minute poll reconciles board edits and lost deliveries. The Service acknowledges an event with no subscriber, a push included, and starts no round for it, but each such delivery uses the rate limit of the route (Webhook route) and writes a log line. Check the hooks of each repository: `uv run devops gh api repos/<owner>/<name>/hooks --jq '.[]|{id,active,events,code:.last_response.code}'`. Each hook must be `active`, its `events` must be `["issues"]`, and after its first delivery its `code` must be 200 or 202. Change a hook in the repository's settings (Settings > Webhooks). `devops` has no command that changes a hook.
9. To rotate a credential, update it in the keyring: `uv run devops config set service.webhook_secrets`, or, for the App, generate a new private key and run `uv run devops config set service.github_app.private_key --from-file <key.pem>`. Then run `uv run devops k8s push-secrets --only devops/devops-cli --rotate`. It restarts `roadmap-service`. Delete the old private key on the App's page after the restart.
10. Run one service per set of repos. While it runs, use `devops roadmap run --dry-run` (#981).
11. The Service keeps three files in `/home/devops/.data/roadmap/` on volume `roadmap-service-home`, beside the `schedule.json` of each repository: `service-halt.json` (GitHub refused the identity), `service-budget.json` (the GitHub requests of the last hour) and `service-failures.json` (the jobs that failed rounds in a row). A restart reads them back, so a restart does not clear a halt, the budget or a suspended job. A round that ends because the Service is stopping, for example in a rollout, does not count as a failed round: the count of its job stays as it was. The log line that suspends a job names the class of the error of each of its failed rounds in a row; the file keeps only the count, so a round that an earlier process counted reads as `unknown`. A rate limit that one request gets stops the requests of all workers until its wait ends. When GitHub refuses the identity, for example because the App's installation is suspended, the Service halts and logs `GitHub refused the identity`. To clear the halt after you fix the cause, remove the file and restart the Service: `kubectl -n devops exec deploy/roadmap-service -- rm /home/devops/.data/roadmap/service-halt.json`, then `kubectl -n devops delete pod -l app.kubernetes.io/name=roadmap-service`.
12. The Service's `/metrics` shows the budget and the suspended jobs (#2475): `devops_cli_service_budget_limit_requests` (the hourly budget), `devops_cli_service_budget_spent_requests` (the GitHub requests of the last hour), `devops_cli_service_budget_holds_total` (one count each time a hold begins) and `devops_cli_service_job_suspended` (1 while a job of a repository, by `repo` and `row`, waits for new input after it failed 3 rounds in a row). Each GitHub request counts in `devops_cli_github_requests_total` under its `method`, the `repo` of the worker that sent it and the job `row` (`metrics`, `intake`, `refine`, `stage`, `implement`, `stage_ready` or `alternatives`); a request outside a worker or a row counts as `other`. To find what spent the budget, run `sum by (repo, row, method) (increase(devops_cli_github_requests_total{job="roadmap-service"}[1h]))` in Grafana Explore. A delivery of the App bot's own write counts as outcome `self` in `devops_cli_service_webhook_deliveries_total`.
13. A refine round writes at most 2 comments on one item in 24 hours. A round that finds 2 refine comments of the last 24 hours on an item leaves the item alone, with no model call and no comment. The item waits on a person and takes no place under the round's limit, so the round refines the next item. For each newest comment on the item that the cap leaves with no answer, the round records the time of that comment in the item's job record (`refine.capped_after`), logs `Refine left #<number> alone and wrote no comment`, and adds 1 to `devops_cli_roadmap_refine_comments_capped_total`. A later round that finds no newer comment does not log or count the item again. A person refines the item at the cap with `devops roadmap refine --item <number> --confirm`. Each Firecrawl search counts in `devops_cli_firecrawl_searches_total` by `result`: `ok`, the HTTP status of a refused search, or `error`. A failed search logs `A Firecrawl web search failed` with the status or the error class, and never the key or the query.
14. The row `alternatives` of the model lane runs after `refine`: on a first run, and 719 minutes after its last success. It runs `devops roadmap alternatives --confirm` for the repository. A round checks at most `roadmap.alternatives.limit` items (5 by default): first the items with no check, then the items whose check is older than `roadmap.alternatives.recheck_days` (30 by default) or whose text changed. A webhook makes the row due at no other time. The row changes no label and closes no issue. It does nothing, and logs `The alternatives check of <repo> is off`, for a private repository and when no Firecrawl key is set. If the check of an item fails, the row records the failure in the item's job record (`alternatives.failed_at` and `alternatives.failed_error`, the class of the error), writes the other checks and succeeds. The row fails, and counts toward the suspension after 3 failed rounds, only when it tried items and checked none. A round takes a failed item again after `roadmap.alternatives.retry_days` (3 by default). Each written check adds 1 to `devops_cli_roadmap_alternatives_total` by `verdict`: `covers`, `partly`, `none` or `not-applicable`. An item of the type `test`, `docs`, `refactor`, `chore`, `ci` or `perf`, and a `fix` with a Python traceback in its body, gets `not-applicable` with no model call; every other item must run a search before the check accepts a verdict, and gets one more turn to search. A `covers` verdict makes refine ask a person to adopt the tool or to keep the item with a reason. The item waits on a person until a reply answers the question, and Ready items with a new covering tool go back to New. Refine records the tool it asked about in the job record (`refine.alternatives_asked`). `devops roadmap run --dry-run` lists the row when it is due.
15. The row `stage` follows `refine` on the model lane (#2659). It runs `devops roadmap stage --confirm` in the model clone: it is due every 37 minutes, on a first run, and in a round where `refine` set an item Ready. It stages the Ready items that `roadmap.stage.filter` names, at most `roadmap.stage.limit` in a round, and splits a task group over `roadmap.stage.step_tokens`. Each task group has a kind (#3005): a `behavior` group has a failing test, and an `other` group has no test but a command or the steps of a manual check that prove it. The job sends a reply that breaks this rule back to the model once. It leaves out an item whose change folder is on the default branch or in its archive (#2714): a round reads that tree once with `git ls-tree`, so a merged staging pull request never makes a second one. The pull request it opens is a draft with the title `docs(openspec): plan #<issue> <summary>`. The job does not mark it ready: the row `stage_ready` does (step 18). Before it opens one, it checks each path of the plan (`reads`, `changes`, the code spans of the tasks and `verify`) against the tracked files of the commit it plans, read with one `git ls-files` for the round (#3010). A path that is no file there, and that no group up to its own creates, goes back to the model once with the files of the same name. A second reply with a missing path stops the item, so no draft opens and the implement Job never meets a wrong path. `k8s/devops/configmap.example.yaml` holds the three settings, and `devops k8s deploy-stack --stack devops` applies them; each also has a variable, `DEVOPS_CLI_ROADMAP_STAGE_FILTER`, `DEVOPS_CLI_ROADMAP_STAGE_LIMIT` and `DEVOPS_CLI_ROADMAP_STAGE_STEP_TOKENS`. Each item of a round counts once in `devops_cli_roadmap_stage_total` by its `result`: `staged`, `skipped`, `needs_split` or `failed`. The image carries the pinned OpenSpec and a Node runtime, so the job validates each change before it pushes: `kubectl -n devops exec deploy/roadmap-service -- openspec --version` prints the locked version.
16. The row `implement` follows `metrics` on the status lane (#2667, #2757). It calls no model, so a model-lane round that has not ended never delays it. It is due every 7 minutes and on a first run, in the clone of the status lane. The Service runs no step: a round only talks to the Kubernetes API, in three moves. It reports each Job that ended, with a comment on the item that holds the state and the last 40 lines of the log of the Job's pod, masked of secrets, and records `implement.job_state` as `succeeded`, `failed` or `gone`. It waits while a Job of the repository has not ended. Else it makes one Job from CronJob `devops-cli-runner` for the first Staged or Planned item that the default filter names (a Planned item has its change folder on the default branch and no branch: a person merged the staging pull request, and the job makes the branch and the draft itself), with the args `roadmap implement --repo <repo> --item <number> --confirm` and the item's number as the only item text, and records the name of the Job in `implement.job`, and the digest of the runner image that the CronJob template names in `implement.job_digest`. The same write sets the label `owner/service` on the item (#2910), and the report of the Job removes it. The comment that reports the Job names the digest. The Service makes no Job for an item that an agent or a person claimed, and a claim of an agent or a person ends a running Job at its next group boundary, with no push and no pull request. A round also sets the Status label of the items from their record (`status_sync.py`): it reads the plans on the default branch once for the sweep and for the plan, writes `status/planned` once a plan is merged, and writes `status/in-progress` as soon as the record names a Job, and again after it makes one. It writes only an open item that holds Ready or Planned with the label that a job last recorded, so a label that a person set stays. The rows `stage` and `stage_ready` use the same function. The Jobs of a repository carry the label `implement-repo`, whose value is a digest of the repository name, so the API is the lock and a restart of the Service loses nothing. A Job that leaves its item In Progress, or Ready or Planned with no stop, is a stop that the runner could not write, such as a pod that the kernel killed for its memory, unless an agent or a person claimed the item. The round then sets the item Blocked (`status/blocked`) and records `implement.stopped` as `job`, so that no Job is made for it again. A stop that the runner writes sets Blocked in the same way, with the step in `implement.stopped`. After the report, the round clears the stop of each item that it set Blocked, by one of two rules, and a comment names the rule that ran. Rule `retry`: a comment `implement: retry`, made after the report by the owner, a member or a collaborator, clears the stop at once, whatever the image. Rule `digest`: the digest in the template of CronJob `devops-cli-runner` is not `implement.job_digest`, so a new runner image has rolled out since the stop, and the round clears the stop one time. A clear sets Ready or Planned and removes `implement.stopped`, and the same round can make a Job for the item. The new Job overwrites `implement.job_digest`, so a second stop on the same image waits for a retry, and the round makes no Job in a loop. A stop with no digest on record is cleared by a retry only. A Blocked stop that no rule clears costs one request in each round, the listing of its comments (6 an hour of `service.github_requests_per_hour`); the round reads the issue again only when a rule holds, and reads the template at most one time. The round clears no item that a Job holds, that an agent or a person claimed, or that a person labeled Blocked by hand. The failures ledger is unchanged: three failed rounds on the same input still suspend the row. If CronJob `devops-cli-runner` does not exist, the round fails with a message that names it: run `devops k8s deploy-stack --stack devops`, or wait for Argo CD. A Job that cannot pull its image (the package `runner` is not public, or no release published it) ends by its deadline after two hours, and the next round records the stop. Read the Jobs with `kubectl -n devops get jobs -l implement-repo`.
17. Each repository has three lanes, and each lane runs one round at a time in its own clone (#1532, #1534). The status lane runs the rows `metrics`, `implement` and `stage_ready` in the clone `clone`. The triage lane runs the row `intake` on the `devops-triage` model in the clone `triage-clone`. The model lane runs the rows `refine`, `stage` and `alternatives` on `devops-background` in the clone `model-clone`. A poll and a webhook go to all three lanes. The lanes share the file `schedule.json` of the repository, the ledger `service-failures.json` and the lock that each write of an item's job record takes (#2757). When intake places a critical fix or P0 item, it writes a `refine_due` timestamp to `schedule.json` so refinement becomes due in the next model-lane round. The label `lane` of `devops_cli_service_jobs_total`, `devops_cli_service_job_seconds_total` and `devops_cli_service_queue_depth` is `status`, `triage` or `model`. The label `row` of `devops_cli_github_requests_total` and `devops_cli_service_job_suspended` is the name of the row. A model-lane round that has not ended does not delay a status-lane or triage-lane round.
18. The row `stage_ready` follows `implement` on the status lane (#2865). It calls no model and needs no clone. It is due every 3 minutes and on a first run. A round reads the open items whose record holds `stage.pr` and no `stage.ready` of the same number and no `implement.job`; with no such item it sends no request of its own, since the listing of the issues is the one that `metrics` and `implement` read in the round. For each such item it reads the pull request (`GET pulls/<n>`). A pull request that is not an open draft is only recorded in `stage.ready`. An open draft goes to the function `ready_to_mark` with its check runs (`GET commits/<sha>/check-runs`): when every check ended and passed, the row marks the pull request ready with `gh pr ready` (the same function as the implement job) and records `stage.ready`. A draft with a failed, cancelled or running check, or with no check, stays a draft, and the row does not retry a check. The row reads only the pull request that the stage job recorded, and never the draft of a person. It reads the check runs and not the commit statuses, because the App token holds `checks: read` and no `statuses` permission. A draft that waits for its checks costs 2 requests a round (12 an hour) of `service.github_requests_per_hour`; a pull request that the row marks costs 2 more for `gh pr ready` and 2 to record it, once. A refusal of `gh pr ready` fails the round, names the item, and the ledger of failed rounds suspends the row after three rounds in a row: check that the App holds `pull_requests: write` and `contents: write` (ADR 0015). A pull request that the row marked ready is no longer a draft, so the implement job leaves its item until a person merges the plan and the item is Planned. The row counts under `row="stage_ready"` in `devops_cli_github_requests_total`.

#### Runner Jobs

The implement job runs tests, `ruff`, `mypy` and OpenSpec, which the Service image does not hold. A step runs `ruff check` on every changed Python file. It runs `mypy` with the options of `devops ci typecheck` on the changed files under `src/`, and no type check on a test file, because the gate checks `src` only (`src/devops_cli/ci/typecheck.py` is the one definition). Its steps run in a runner Job (#2667). `devops roadmap implement --item <number> --confirm`, run on a workstation, makes one by hand for that item and follows its log (`--no-wait` prints the Job's name, `--dry-run` prints the Job). It refuses an item that an agent or a person claimed, an item that is neither Ready nor Planned, and a repository that has a runner Job that has not ended. It makes the Job with the code of `devops k8s run-job --template runner --repo <owner/name> -- roadmap implement --repo <owner/name> --item <number> --confirm`, which is the way to pass `--filter` or `--limit` to the job. Both commands label the Job and its pod `implement-repo=<digest of the repository>`, the label that the row `implement` lists its Jobs by, and make no Job while a Job with that label has not ended. The label is a digest of the lower-case repository name. The lock is best effort: each command lists the Jobs just before it creates one, so a Job that starts between the two calls is not seen. If the App is not installed on the repository, the Job fails in its pod, and the error in its log names the repository. `--repo` is required with the runner template: it sets `service.github_app.token_repository` on the Job, and the job runs no step unless that setting equals the repository it acts on. The Service makes one for each Staged or Planned item in the row `implement` (Roadmap service, step 16).

- **Image.** Stage `runner` of the `Dockerfile` is the `builder` stage with git, the dev dependencies of `uv.lock` (pytest, ruff, mypy, bandit, deptry, ast-grep, zizmor, pre-commit), and the tools that the gate and the hooks need (#3072): `curl` and `jq` from apt, and promtool at the pin of `tools.lock`, installed with `devops install-tools`. The table `RUNNER_TOOLS` in `src/devops_cli/roadmap/runner_tools.py` lists every tool with the reason it is there and its version command, and `NOT_IN_RUNNER` lists each program that the image leaves out, with the reason (no cluster tool, no scanner that the gate does not install, no npm, no tool that fails the image scan). The image holds neither `actionlint` nor `shellcheck` nor Trivy: the image scan fails on the newest release of each (Go standard library 1.27.0 in `actionlint` 1.17.0, go-jose 4.1.5 in Trivy 0.76.1), so a Job cannot run the `actionlint` row or the IaC scan, and without npm it cannot run the `audit` row. The pull request runs them. #3108 tracks their return. The apt tools have no pin, because Debian gives the version and a pin would fail the build on each security update; the image holds `git` 2.47.3, `curl` 8.14.1 and `jq` 1.7. The last step of the stage runs `python -m devops_cli.roadmap.runner_tools`, so an image that lacks a tool or holds it at another version than its pin does not build. Tests fail when a `devops ci` row, a hook of `.pre-commit-config.yaml`, a required job of `ci.yml`, a live-marked test or an entry of `tools.lock` needs a program that is in neither table, and when a pin of the table differs from a Dockerfile. The Service image holds none of the added tools. `trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 --ignorefile .trivyignore` on the built stage exits 0. The measured growth is 56 MB compressed (522 MB to 578 MB, as `docker save` output through `gzip -1`) and about 70 MB in the new layers, which adds the transfer of those layers to the first pull on a node (about 5 s on 100 Mbit/s). The promtool step of the build takes 19 s. The smoke test of `ci.yml` and `release.yml` runs the same check on the loaded image and fails when `docker image inspect` reports more than 3000000000 bytes (2.51 GB measured). The release publishes the image as `ghcr.io/dan-petty/devops-cli/runner`, next to the Service image, and Image Updater keeps it on the digest of `latest` (Service Image Updates). Each Job runs `uv run` in its own worktree, with the uv cache on the home volume.
- **Template.** Suspended CronJob `devops-cli-runner` has 2 CPU, 4 Gi of memory requested and 8 Gi at most, an `emptyDir` home of 4 Gi, an `emptyDir` `/tmp` of 1 Gi, `ephemeral-storage` of 2 Gi requested and 6 Gi at most, `activeDeadlineSeconds: 7200` and `backoffLimit: 0`. It sets `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER=true`, which no other pod sets, and `PYTEST_XDIST_AUTO_NUM_WORKERS=2`, the CPU limit, because `pytest-xdist` counts the CPUs of the node and not of the pod (about 280 MB for each worker). It uses ServiceAccount `devops-cli`, which mounts no token, and the Secret `devops-cli` through `envFrom`. A Job is made from the template and changes only the args, the name, the labels and the environment value `DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY`.
- **Role.** ServiceAccount `roadmap-service` is the account of the Service pod. Role `roadmap-service-jobs` in namespace `devops` allows `create`, `get` and `list` on `jobs`, `get` on CronJob `devops-cli-runner`, `list` on `pods` and `get` on `pods/log`, and nothing else. Kubernetes cannot limit `create` and `list` to a name, so those two cover the namespace. A holder of the Role can make any pod that Pod Security `restricted` admits in namespace `devops`, and such a pod can take Secret `devops-cli`. The Service pod holds that Secret already, so the Role gives no new secret. That holds only while namespace `devops` holds no Secret but `devops-cli`, so the admission policy below pins the Jobs of the Service. The Service pod mounts a projected token that expires after one hour; the client reads it again as the kubelet renews it. A Job pod mounts no token.
- **Admission policy.** ValidatingAdmissionPolicy `roadmap-service-jobs` and its binding (`k8s/devops/roadmap-service/admissionpolicy.yaml`, #2696) refuse a `CREATE` or an `UPDATE` of a Job in namespace `devops` unless the Job has: one container and no init container, with no `command`; the image `ghcr.io/dan-petty/devops-cli/runner`, alone or followed by `:` or `@`; ServiceAccount `devops-cli` with `automountServiceAccountToken: false`; only Secret `devops-cli` in `envFrom` and no `valueFrom` in `env`; only the volumes `tmp`, `home` and `config` of the template; no `hostNetwork`, `hostPID` or `hostIPC`; no `priorityClassName`, `nodeName`, `imagePullSecrets` or `manualSelector`; the pod label `app.kubernetes.io/name: devops-cli-job`, because the NetworkPolicies select pods by that label and a Job pod with the label of the Service would take its egress to the API server; `completions` and `parallelism` of 1 or not set; `backoffLimit: 0`; and an `activeDeadlineSeconds` of 7200 at most. The policy applies only to the user `system:serviceaccount:devops:roadmap-service`. It never evaluates a Job of another identity, such as the CLI user (`devops k8s run-job`), Argo CD or the CronJob controller. It runs in the API server, so no webhook can be down. `failurePolicy` is `Fail`: if an expression errors, the Job of the Service is refused, the create raises an error, and the next round tries again. Argo CD syncs the policy with the other manifests of the stack, and AppProject `homelab` already admits the two cluster-scoped kinds. The test `tests/test_k8s_job_admission_policy.py` runs the expressions against the Job that CronJob `devops-cli-runner` makes, so a change of the template that the policy refuses fails in CI. To check the live policy, make a Job as the Service with `kubectl --as=system:serviceaccount:devops:roadmap-service create --dry-run=server -f <job>`. These are not pinned: the tag or digest of the image, the `args`, the plain `env` values, the resources, `nodeSelector`, `tolerations`, `hostUsers`, the security context (Pod Security `restricted` checks the pod) and the number of Jobs. A person with an admin role can delete the policy, and Argo CD restores it.
- **Network.** Policy `roadmap-service-egress` admits the Service pod, and no other pod, to TCP 6443, with the cloud metadata address excluded. A Job pod keeps the egress of `devops-default-perimeter`: DNS, the gateway, the cache, the OTLP collector and public HTTPS. No policy admits it to the API server.
- **Guarantees.** The shell of a step has none of the variables of the job, except the uv paths and the worker bound of the test runner. A step cannot read the environment or the memory of the job process, because the job clears its dumpable flag. The installation token of the job names one repository (`service.github_app.token_repository`), and the job runs no step unless that setting equals its repository and the process acts as the GitHub App. A Job ends after 7200 s at most and is not retried. The token is in the environment of a `git` or `gh` child of the job while that child runs, and a process of the same user can read it through `/proc`. A pod cannot hide it: the default seccomp profile refuses the user namespace that a sandbox for the shell needs. So the job guarantees an order: it adopts the orphans of its children, and when a step ends it kills every process the step left, also a daemon in a session of its own, before it runs any `git` or `gh`. A process that survives stops the item. These properties are not guaranteed: public HTTPS is open, so a step can send the clone to a public host; and a step runs as the same user as the job, so it can change the files that the job reads later, such as the clone, `.git/config` and the hooks of the worktree. A hook runs inside a `git` child of the job, with the token in its environment. The token limits the harm to one repository, to the permissions of ADR 0015 and to one hour. A real sandbox for the shell is planned (see Person steps). A person merges every pull request.
- **Person steps.** After the first release that publishes the runner image, a person makes the GHCR package `runner` public, as the package `service` is. The Job takes the whole Secret `devops-cli`. A narrower Secret for the runner is the better end state, and a person makes secrets. A follow-up is filed: a real sandbox for the shell of a step ([#2695](https://github.com/dan-petty/devops-cli/issues/2695)). After the first sync of the admission policy, a person checks once that the Service's Job passes it, with the `kubectl --as` command of the policy above.

#### Webhook route

The Ingress `devops/roadmap-service` publishes `POST /webhooks/github` at `https://hooks.<domain>`.

Traefik limits the requests to the route before they get to the Service. The Ingress names the Middleware `devops/roadmap-service-rate-limit` (`roadmap-service/middleware.yaml`), which lets 60 requests a minute through, with a burst of 60, in one bucket for the host. Traefik answers a request above the limit with HTTP 429. GitHub does not send a failed delivery again, but the next poll starts the round that the delivery would have started. To see the answers of the route, the 429 of the rate limit included, use `sum by (code) (increase(traefik_router_requests_total{service="devops-roadmap-service-8000@kubernetes"}[15m]))`. Traefik counts `traefik_service_requests_total` only for the requests that get to the Service, so that series does not show a 429 of the rate limit.

The route refuses a delivery before it reads the body when:

- the Service drains: 503;
- the content type is not `application/json`: 415;
- the `X-GitHub-Event` or `X-GitHub-Delivery` header is missing: 400;
- the `X-Hub-Signature-256` header is missing or empty: 401 `missing signature`;
- the `Content-Length` is more than 25 MiB: 413.

Then the route reads the body. It refuses a body of more than 25 MiB (413), a signature that no secret in `service.webhook_secrets` made (401 `invalid signature`), a payload that does not validate (400), and a repository that is not in `service.repos` or that did not sign the body (401). Each refusal counts under the outcome `rejected` of `devops_cli_service_webhook_deliveries_total`. `RoadmapServiceWebhooksRejected` fires when the route rejects more than 20 deliveries in 15 minutes (Alerts).

#### Mattermost slash command

The `/roadmap` slash command in Mattermost inspects each repository's roadmap service state, answered in-cluster through the service's webhook router (#1395).

1. In Mattermost, add a custom slash command (System Console > Integrations > Slash Commands):
   - Command Trigger Word: `roadmap`
   - Request URL: `http://roadmap-service.devops.svc.cluster.local:8000/webhooks/mattermost`
   - Request Method: `POST`
2. Save the command and copy the generated token.
3. Save the token in the workstation keyring:
   ```bash
   uv run devops config set mattermost.command_token
   ```
4. Push the secret to the cluster:
   ```bash
   uv run devops k8s push-secrets --stack devops
   ```
   Or update only the devops secret:
   ```bash
   uv run devops k8s push-secrets --only devops/devops-cli
   ```
5. In Mattermost, run `/roadmap` or `/roadmap status` to show the state of all repositories and lanes, or `/roadmap status <repo>` for one repository. The Service answers with an ephemeral reply.

#### Alerts

The rule group `roadmap-service` in `monitoring/prometheus-values.yaml` watches the Service (#2472), and the rule group `roadmap-service-webhooks` watches its webhook route (#2476). Each description of a rule points to this section. Each `devops_cli_` series is selected with `job="roadmap-service"`: the scrape of the pod's `/metrics` and the OTLP export both give the Service's series that job, so the same series of a workstation (`job="devops-cli"`) does not count. The failed jobs and the GitHub and model requests of the last hour count a series that starts in the hour from zero, so they also count its first sample (#2505). kube-state-metrics gives the restarts and the replicas.

| Alert | Fires when | For | Severity | Do this |
| :--- | :--- | :--- | :--- | :--- |
| `RoadmapServiceIdentityRefused` | GitHub refused the identity of the Service. The Service stopped all rounds and starts no round, also after a restart, until a person removes its halt record, and `/healthz` stays healthy. A start that finds the halt record counts the refusal again, so the alert holds through a restart. | — | critical | Read the refusal in the Service log. Repair the App or its installation (step 1), or rotate its private key (step 9). Then remove the halt record and restart the Service (step 11). |
| `RoadmapServiceGitHubThrottled` | GitHub refused a request of the Service with a rate limit, or gave a 5xx for a read, in the last 15 minutes | — | critical | Read the GitHub API panels of the `devops-cli Telemetry` dashboard. Lower `service.github_requests_per_hour` or remove a repository from `service.repos`, then run `devops k8s deploy-stack --stack devops`. |
| `RoadmapServiceJobsFailing` | All jobs of one repository and lane failed in 1 hour (increase in errors is greater than zero, and increase in successes is zero). | 30m | warning | Read the errors of that repository in the Service log: `kubectl -n devops logs deployment/roadmap-service`. Repair the cause, for example the repository's `.github/roadmap.toml`. |
| `RoadmapServiceLaneStalled` | No job of a repository and lane started in 2 hours while the deployment has an available replica. In a new pod, the 2 hours start when the worker of the lane starts. | 10m | warning | Find in the Service log a pause of the rounds, a spent request budget, or a job that does not end. If a job does not end, restart the deployment. |
| `RoadmapServiceRestarted` | The `service` container restarted in the last hour | — | warning | Read the log before the restart: `kubectl -n devops logs deployment/roadmap-service --previous`. |
| `RoadmapServiceUnavailable` | The deployment has an unavailable replica. A rollout stops the old pod before it starts the new one, so the rule waits 10 minutes. | 10m | warning | Read the events: `kubectl -n devops describe deployment/roadmap-service` and `kubectl -n devops get events --sort-by=.lastTimestamp`. |
| `RoadmapServiceGitHubRequestsHigh` | The Service sent more GitHub requests in 1 hour than 90% of the budget it reports in `devops_cli_service_budget_limit_requests` (`service.github_requests_per_hour`, 500 by default) | — | warning | Read the GitHub Requests by Resource panel of the `devops-cli Telemetry` dashboard, and find the repository in the Service log. Lower the budget or remove a repository from `service.repos`, then run `devops k8s deploy-stack --stack devops`. |
| `RoadmapServiceModelRequestsHigh` | The Service sent more than 352 model requests in 1 hour. A request that the cache answered does not count. | — | warning | Find the model on the `AI Spend & LLM Usage Telemetry` dashboard, and the repository in the Service log. Remove the repository from `service.repos` until the cause is known, then run `devops k8s deploy-stack --stack devops`. |
| `RoadmapServiceWebhooksRejected` | The webhook route rejected more than 20 deliveries in 15 minutes (Webhook route). A label set that starts in the 15 minutes counts from zero. | — | warning | Check the last response of each hook (step 8). A hook whose last `code` is 401 has a secret that is not the one in `service.webhook_secrets`: set the same secret on both sides (step 9). If each hook gets 200 or 202, the deliveries are forged: read them in the Service log (`kubectl -n devops logs deployment/roadmap-service \| grep rejected`), and the 429 answers of Traefik (Webhook route). |

The rule group `roadmap-service-activity` watches what the Service writes, the deliveries of its own writes, and its web search (#2475). Its rules count the series of the last hour as the group `roadmap-service` does.

| Alert | Fires when | For | Severity | Do this |
| :--- | :--- | :--- | :--- | :--- |
| `RoadmapServiceGitHubWritesHigh` | The Service sent more than 300 GitHub writes in 1 hour: REST requests with the method POST, PUT, PATCH or DELETE, such as comments, labels and issue edits. GraphQL sends a read as a POST too, and the roadmap jobs write only through REST, so GraphQL does not count. A series with no `method` label, such as one of an image from before the label, does not count: the rule names each write method, because PromQL reads an absent label as the empty string (#2574). | — | warning | Find the repository and the row with `sum by (repo, row, method) (increase(devops_cli_github_requests_total{job="roadmap-service", method=~"POST\|PUT\|PATCH\|DELETE", resource!="graphql"}[1h]))` (step 12), and read the bot's comments and events on that repository. If a loop writes, do the stop switch. Else remove the repository from `service.repos`, then run `devops k8s deploy-stack --stack devops`. |
| `RoadmapServiceSelfDeliveriesHigh` | The Service got more than 150 webhook deliveries of its own writes in 1 hour. Each write can come back as one delivery, so another bot or workflow can answer each write of the Service. | — | warning | Find the repository in the delivery log lines of the Service (`outcome` `self`), and find the bot or workflow that writes after the Service on it. Turn that repository's webhook off (stop switch, step 5) until the loop is broken. |
| `RoadmapServiceFirecrawlRefused` | Firecrawl refused a web search of the Service in the last hour: HTTP 402 when the account has no credits, HTTP 429 at its rate limit. Refine goes on without the search results. | — | warning | Read the usage page of the Firecrawl account. Add credits or wait for the rate limit to end. To stop the searches, a person removes the key `DEVOPS_CLI_FIRECRAWL_API_KEY` from Secret `devops/devops-cli`, then restarts the Service. |

No alert leaves the cluster until the Secret `monitoring/alertmanager-mattermost` exists (Alerting, Receiver). Creating it is a step for the owner, who chose Mattermost as the route for the alerts (#1391, #1392). Until then, read the alerts in Grafana (Alerting, with the `Alertmanager` datasource) or on the Alerts page of Prometheus.

`tests/test_k8s_monitoring_alerting.py` pins each rule and runs the pinned promtool (`devops install-tools --tool promtool`) on it. `promtool test rules` runs the unit tests of each group, in `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, `roadmap_service_webhooks_tests.yaml` and `roadmap_service_activity_tests.yaml`: each alert fires on a sample series with the labels and annotations that the tests pin, and stays quiet on a normal series and on the same series of another job. To run them by hand, write the group to the file that the tests' `rule_files` names, then run `promtool test rules <tests-file>` in that directory.

#### Go-live check

Argo CD applies the deployment, but not ConfigMap `devops-cli-config`. Only `devops k8s deploy-stack --stack devops` renders that ConfigMap, from `k8s/devops/configmap.example.yaml` and the active config. On a cluster that Argo CD manages, deploy-stack applies the ConfigMap but does not restart the pod. Until a pod reads the ConfigMap of the current template, it can send each model call five times, not two (LLM Gateway). So when Argo CD has synced the deployment, do these steps from a checkout of `main`. Do them again each time a change to the template merges.

```bash
uv run devops k8s deploy-stack --stack devops
kubectl -n devops get cm devops-cli-config -o jsonpath='{.data.devops-cli\.yaml}' | grep max_retries   # max_retries: 1
kubectl -n devops rollout restart deployment/roadmap-service
```

Then do these checks, and do them again every 15 minutes for the first 2 hours. If a check fails, do the stop switch. If an alert of the rule group `roadmap-service` or `roadmap-service-webhooks` fires, do what its row in Alerts says. Select each series of the Service with `job="roadmap-service"`, as the alert rules do.

1. The pod runs: `kubectl -n devops get pod -l app.kubernetes.io/name=roadmap-service` shows one pod `Running`, with no restart and no `OOMKilled`.
2. Prometheus scrapes the pod: `up{job="roadmap-service"}` is 1.
3. A test delivery gets to the Service. Get each hook's ID with `uv run devops gh api repos/<owner>/<repo>/hooks --jq '.[]|{id,active,events}'`, then send a ping with `uv run devops gh api -X POST repos/<owner>/<repo>/hooks/<id>/pings`. `uv run devops gh api repos/<owner>/<repo>/hooks/<id> --jq .last_response` shows code 200, and `devops_cli_service_webhook_deliveries_total{job="roadmap-service",event="ping"}` counts one `ignored` delivery. Code 401 tells you that the hook's secret is not the one in `service.webhook_secrets`.
4. The first rounds stay inside the budget: `sum(increase(devops_cli_github_requests_total{job="roadmap-service"}[1h]))` has a value within 15 minutes and stays below `devops_cli_service_budget_limit_requests{job="roadmap-service"}`, the budget `service.github_requests_per_hour` (500 by default). At the start, each lane that is due runs, so the first hour costs the most.

#### Stop switch

Do these steps in this order. Step 1 does not need the cluster.

1. Suspend the App's installation. Only a person can do this, and only in the web interface: open https://github.com/settings/installations, select `devops-cli-service`, select Configure, then select Suspend. The next token mint fails, and the Service halts as a refused identity. Until that mint, GitHub refuses each request, but the Service does not halt.
2. Turn off automated sync from the top down (Pausing an Application): `bootstrap`, `cluster`, then `devops`. All three self-heal, so without this step Argo CD sets the replica count back to the value in git. `ArgoCdAutoSyncDisabled` fires after 15 minutes, which is expected.
   ```bash
   for app in bootstrap cluster devops; do
     kubectl -n argocd patch application "$app" --type merge -p '{"spec":{"syncPolicy":{"automated":{"enabled":false}}}}'
   done
   ```
3. Stop the pod: `kubectl -n devops scale deployment roadmap-service --replicas=0`.
4. Stop the cluster Jobs, which use the same key: `kubectl -n devops get jobs -l app.kubernetes.io/name=devops-cli-job`, then `kubectl -n devops delete job <name>` for each Job that runs.
5. Turn off each repository's webhook: `uv run devops gh api -X PATCH repos/<owner>/<repo>/hooks/<id> -F active=false`.
6. If the private key leaked, generate a new key and delete the old one (step 9). A token minted with the old key stays valid until it expires, up to one hour after its mint.
7. To keep the Service stopped, open a pull request that sets `replicas: 0` in `k8s/devops/roadmap-service/deployment.yaml`. After a person merges it, turn on automated sync for `bootstrap` again: it restores `cluster`, and `cluster` restores `devops` from git.

Do not restart the pod to clear a halt before you know its cause. A restart clears the halt, the hourly budget and the count of failed rounds.

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
kubectl -n devops get deploy roadmap-service           # unchanged: the replicas that git sets for it
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

## Mattermost

Mattermost Team Edition runs under Argo CD from the Mattermost Operator on CloudNativePG PostgreSQL 17.

### What runs where

- **Operator**: `mattermost-operator` runs in namespace `mattermost-operator`.
- **Database Operator**: `cloudnative-pg` runs in namespace `cnpg-system`.
- **Workload**: `Mattermost` runs in namespace `mattermost`.
- **Database**: CloudNativePG `Cluster` named `mattermost-db` runs in namespace `mattermost`.
- **Volume**: PVC `mattermost-files` stores uploaded files on `local-path`.

| Consumer | Address | How it reaches Mattermost |
| :--- | :--- | :--- |
| In-cluster pods | `http://mattermost.mattermost.svc.cluster.local:8065` | the service on TCP 8065 |
| Workstations and browsers | `https://mattermost.<domain>` | Cloudflare Tunnel, Traefik and Ingress `mattermost/mattermost` |

### Rollout

1. Merge the pull request. Argo CD creates the namespaces and objects. The database waits for Secret `mattermost/mattermost-db`. Alert `MattermostDatabaseDown` fires until step 2 completes.
2. Run `uv run devops k8s deploy-stack --stack chat --context <context>`. Always keep the default `--wait`: CloudNativePG's admission webhook refuses the `Cluster` until its operator is ready. The deploy pushes Secret `mattermost/mattermost-db` and sets the host on Application `mattermost`.
3. The owner signs up first from the bypassed network address. Cloudflare Access admits only the owner, so nobody else can claim the administrator account.
4. Set both persistent volumes to Retain:
   ```bash
   kubectl patch pv "$(kubectl -n mattermost get pvc -l cnpg.io/cluster=mattermost-db -o jsonpath='{.items[0].spec.volumeName}')" -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
   kubectl patch pv "$(kubectl -n mattermost get pvc mattermost-files -o jsonpath='{.spec.volumeName}')" -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
   ```
5. Create the primary team and the channels `alerts` and `deploys`. Create each incoming webhook with "Lock to this channel" (#1390).

### Operations

- **Backups**: The homelab has no backup mechanism for Mattermost yet (#1081). If a worker node fails, unbacked data on `local-path` is lost.
- **Upload limits**: The upload limit is 99 MB (`MM_FILESETTINGS_MAXFILESIZE=99000000`). Cloudflare enforces a 100 MB request ceiling, so 99 MB prevents edge 413 errors before Mattermost sees the payload. The mobile app has the same limit.
- **Upgrades**: Change `version` in `k8s/mattermost/mattermost.yaml`. With `Recreate` deployment strategy, an upgrade causes a brief outage while the old pod terminates and the new pod mounts the volume.
- **Password reset without email**:
  ```bash
  kubectl -n mattermost exec deploy/mattermost -- mmctl --local user change-password <user> --password <new>
  ```
- **Teardown**: On a cluster without Argo CD, `teardown-stack --stack chat` deletes the database and the files claim.

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
| `service.repos`, `service.github_app.app_id`, `service.github_app.installation_id`, `service.github_app.slug`, `service.poll_interval_seconds`, `service.drain_timeout_seconds` | `config.yaml` | ConfigMap `devops-cli-config`, which no Application owns | `--stack devops` or `all` |
| `service.github_requests_per_hour`, only when a source sets it | `config.yaml` or `DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR` | ConfigMap `devops-cli-config`. With no value set, the ConfigMap holds none, and the Service uses its default of 500 | `--stack devops` or `all` |
| Hosts under the configured domain | `--domain`, else `k8s.domain`, `cloudflare.domain`, `DEVOPS_CLI_K8S_DOMAIN` or `DEVOPS_CLI_DOMAIN` | Kustomize patches in `spec.source.kustomize` of the Applications `devops` and `ingress` | `--stack devops` or `all` (both Applications), `--stack infra` or `gitea` (`ingress` only) |

To change the hourly GitHub request budget of the Service, run `devops config set service.github_requests_per_hour <n>`, then `devops k8s deploy-stack --stack devops`. The Service shows the budget it runs with in `devops_cli_service_budget_limit_requests{job="roadmap-service"}`, and the alert `RoadmapServiceGitHubRequestsHigh` follows that value.

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
4. Check: `devops argo cd apps status devops` and `devops argo cd apps status ingress` are Synced and Healthy and exit 0. For `devops`, the command also reads the digest that `service:latest` names in GHCR and exits 1 when the Application's `spec.source.kustomize.images` pins another one, so ImageUpdater `devops` stopped updating ([Service Image Updates](#service-image-updates)). `kubectl get ingress,ingressroute -A -o yaml | grep example.com` prints nothing, and `kubectl -n devops get configmap devops-cli-config -o yaml` holds the configured repositories and the template values of `main` (gateway URL, models, context windows).

> [!NOTE]
> `k8s/coredns/` remains managed outside Argo CD to preserve cluster DNS resolution during bootstrap and recovery cycles.

### Image Pins

`devops k8s image-pins` renders each Argo CD Application as Argo CD does, and resolves each image that the rendered objects name in its registry, as an anonymous client, without pulling it. A path source renders with `kubectl kustomize`, and a chart source with the pinned `helm` and the value files of this repository, so a tag that a value file sets is checked too. The chart render leaves out the chart's test manifests (`--skip-tests`), because Argo CD does not apply a Helm test hook. It does not resolve the images that an `ImageUpdater` object names, because Image Updater moves them ([Service Image Updates](#service-image-updates)), or the images of a registry that only the cluster or the host reaches. Before it resolves an image, it fails on each image that has no digest and the `latest` tag or no tag, unless an `ImageUpdater` object names it: each pull of such an image can get a different image. The CI job `image-pins` runs it on each pull request that changes `k8s/`, so a wrong tag fails the pull request and not the sync. Docker Hub counts each read of a Docker Hub image as an anonymous pull of the network's public address. On the home network the cluster's nodes share that allowance, so let the CI job run the check.

### Service Image Updates

Application `argocd-image-updater` runs [Argo CD Image Updater](https://argocd-image-updater.readthedocs.io/en/stable/) in namespace `argocd`, from the argo-helm chart pinned to a version like the other chart Applications. Its one ImageUpdater, `devops` in `k8s/argocd/image-updater-values.yaml`, keeps the `devops` Application on the digests that `ghcr.io/dan-petty/devops-cli/service:latest` and `ghcr.io/dan-petty/devops-cli/runner:latest` point at. The text below describes the Service image; the runner image of CronJob `devops-cli-runner` is handled in the same way:

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
devops argo cd apps status devops                   # exits 1 when the pinned digest is not the one latest names
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

# Once the Applications have synced, retire the Helm release records of the charts they adopted
devops argo cd apps retire-helm-records            # the plan: it reads only
devops argo cd apps retire-helm-records --confirm
```

A chart that `helm upgrade --install` deployed before Argo CD adopted it keeps its Helm release records: Secrets labelled `owner=helm`, such as `sh.helm.release.v1.prometheus.v48`. Argo CD only renders a chart with `helm template`, so `helm list` still shows the release as `deployed`, and `helm rollback` or `helm uninstall` would act on objects that Argo CD owns. `retire-helm-records` deletes the records of a release when an Application renders it and Argo CD applied each of its top-level objects: the object carries the Application's tracking id, or names the field manager `argocd-controller` (Argo CD writes no tracking id on a CustomResourceDefinition). Every object stays. For a release that does not qualify, the plan names each object that Argo CD did not apply; sync that Application, then run the command again. A record with an owner reference, such as those of the Alloy operator, stays. AppProject `homelab` does not ignore `sh.helm.release.v1.*` Secrets, so Argo CD shows a record that is left over as an orphaned resource.

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

# 4. Once Application argocd has synced, retire the release record that step 1 wrote
devops argo cd apps retire-helm-records --confirm
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

### Notifications

Argo CD delivers notifications to Mattermost when the `devops` application deploys successfully and when any application sync fails.

1. **Create an Incoming Webhook in Mattermost**:
   - In Mattermost, open Main Menu > Integrations > Incoming Webhooks > Add Incoming Webhook.
   - Enter a title (such as `Argo CD Deploys`), select channel `deploys`, and enable "Lock to this channel".
   - Copy the generated webhook token (the string after `/hooks/`).

2. **Store the Credential in Keyring**:
   ```bash
   devops config set mattermost.deploys_hook
   ```

3. **Push the Cluster Secret**:
   ```bash
   devops k8s push-secrets --only argocd/argocd-notifications-secret
   ```

The notifications controller reads the derived URL from `argocd/argocd-notifications-secret` and delivers events to Mattermost on TCP port 8065:
- **Application deploys**: When the `devops` application finishes a sync and reaches Healthy status (`on-deployed`), a notification posts to the deploys channel. Other applications do not trigger deploy posts to prevent notification clutter.
- **Application sync failures**: When any application sync fails (`on-sync-failed`), a failure notification posts to the deploys channel with the error message.
- **Persistent OutOfSync or Degraded states**: Not handled by this webhook; issue #551 monitors lasting conditions through Prometheus metrics and Alertmanager alerts.
- **GitHub deployment status tracking**: Owned separately by issue #1387.

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
                 ┌─────────────────┘           └─────────────────────────────────┐
                 ▼                                                               ▼
     k8s / Namespace: llm                         k8s / Namespaces: monitoring, argocd, gitea, mattermost
  [chat.homelab.<domain>] ──▶ open-webui       [grafana.homelab.<domain>]    ──▶ grafana
  [ai.homelab.<domain>]   ──▶ llm-gateway      [argocd.homelab.<domain>]     ──▶ argocd
                                               [git.homelab.<domain>]        ──▶ gitea-http
                                               [mattermost.homelab.<domain>] ──▶ mattermost
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
   The two replicas prefer different nodes: a preferred `podAntiAffinity` term on `kubernetes.io/hostname` places them apart when it can, and still starts a replica while only one node can take it. PodDisruptionBudget `cloudflared` (`minAvailable: 1`) keeps one replica up through a drain. A pod that is not ready never blocks a drain (`unhealthyPodEvictionPolicy: AlwaysAllow`).
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
2. On the workstation, install `cloudflared` from `tools.lock`, set the hostname of the route, and start the forward. `devops k8s tunnel start` runs `cloudflared access login` first: it opens a browser for the Access login or prints the login URL, and stores the token without printing it. Then it starts `cloudflared access tcp` in the background on `127.0.0.1:16443` (`--port` sets another port), records it under the data directory and waits until the port accepts connections. When a forward already runs, it reports that forward and starts no other. `--context` adds or updates the kubeconfig cluster and context `<cluster>-tunnel`, with the cluster, the user and the CA data of the home context (`k8s.context`, or `--from-context`), the server `https://127.0.0.1:16443` and the TLS server name `kubernetes.default.svc`.
   ```bash
   devops install-tools --tool cloudflared
   devops config set k8s.tunnel_host k8s.<domain>
   devops k8s tunnel start --context
   kubectl --context <cluster>-tunnel get nodes
   ```
3. `devops k8s tunnel status` shows the forward, whether its port accepts connections, and whether the API server of the tunnel context answers. A 401 or a 403 counts as an answer, because the request reached the API server. `devops k8s tunnel stop` stops the forward and its process group. `devops k8s switch-context <cluster>-tunnel` makes the tunnel context the one that `devops k8s` commands use.

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
│   ├── pdb.yaml              # PodDisruptionBudget: a drain keeps one tunnel replica up
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
│   ├── cronjob-runner.yaml   # Suspended CronJob devops-cli-runner, the template of the implement job's runner Job
│   ├── networkpolicy.yaml    # Default-deny perimeter: DNS, the gateway and public HTTPS out
│   └── roadmap-service/      # Continuous roadmap service Deployment, Service, Ingress, rate-limit Middleware, NetworkPolicies, PVC, ServiceAccount and Role
│       ├── kustomization.yaml
│       ├── admissionpolicy.yaml
│       ├── deployment.yaml
│       ├── ingress.yaml
│       ├── middleware.yaml
│       ├── networkpolicy-egress.yaml
│       ├── networkpolicy.yaml
│       ├── pvc.yaml
│       ├── role.yaml
│       ├── service.yaml
│       └── serviceaccount.yaml
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
