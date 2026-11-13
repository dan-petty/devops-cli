# k8s/ — Local Kubernetes Infrastructure & LLM Stacks

Kustomize + Helm-based configurations for deploying infrastructure management (`infra`) and local AI/LLM (`llm`) stacks to two clusters:

- the k3s homelab, which Argo CD keeps in line with `main` ([GitOps](#gitops));
- the devcontainer's minikube cluster, which `devops devcontainer post-start` starts.

`devops k8s deploy-stack` deploys the same configurations to either cluster.

This folder is the environment tree of the homelab: what one cluster runs. `k8s/devops/` is the product base that devops-cli ships. A command that reads the environment tree (`deploy-stack`, `teardown-stack`, `bootstrap`, `image-pins`, `lint`, `check-deprecated`, `ollama prune`, `devops grafana dashboards`, `devops ai gateway render`, `devops argo cd apps bootstrap-gitops` and `devops argo gitops`) takes its root from `--k8s-dir`, else from the project profile fact `kubernetes.dir` of the repository of the current folder (`.devops/project.toml` of this repository declares `k8s`), else from the one entry of `infra.repos` whose checkout gives `kubernetes.dir`. `deploy-stack` and `teardown-stack` read the product base from `--product-dir`, else from `k8s/devops` of the repository of the current folder. A path in the tree is relative to its root, such as `llm/gateway/config.yaml`.

## Stacks Overview

| Stack | Components | Namespaces | Default Ports |
| :--- | :--- | :--- | :--- |
| **`infra`** *(Default)* | ArgoCD (backed by Valkey), Argo Workflows controller, Grafana k8s-monitoring (Alloy + kube-state-metrics + node-exporter), Prometheus server, Grafana, Alertmanager, Grafana Pyroscope, NVIDIA DCGM Exporter, OpenTelemetry Collector, Grafana Tempo, CloudNativePG operator, cert-manager and the Barman Cloud plugin ([CloudNativePG Backup Plugin](#cloudnativepg-backup-plugin)) | `argocd`, `argo-workflows`, `monitoring`, `otel`, `cnpg-system`, `cert-manager` | `8080` (ArgoCD), `8030` (Grafana), `8090` (Prometheus), `4040` (Pyroscope), `3200` (Tempo) |
| **`llm`** | Ollama (per-VRAM-tier DaemonSets), LLM Gateway (LiteLLM) with its CloudNativePG database, Open-WebUI, Qdrant Vector DB, Valkey Cache | `llm` | `11434` (Ollama), `3000` (WebUI), `6333` (Qdrant), `6379` (Valkey) |
| **`logging`** | Loki (pod and journal logs shipped by the `infra` stack's Alloy `alloy-logs` DaemonSet) | `logging` | `3100` (Loki) |
| **`gitea`** | Gitea: the internal forge and container registry ([Gitea](#gitea)) | `gitea` | `3000` (Gitea HTTP, in the cluster) |
| **`chat`** | Mattermost Team Edition on CloudNativePG ([Mattermost](#mattermost)) | `mattermost`, `mattermost-operator` | `8065` (Mattermost HTTP, in the cluster) |
| **`all`** | All components from the stacks above, and the `devops` stack ([docs/CLUSTER.md](../docs/CLUSTER.md)) | `argocd`, `argo-workflows`, `monitoring`, `otel`, `llm`, `logging`, `gitea`, `devops`, `mattermost`, `cnpg-system`, `mattermost-operator`, `cert-manager` | All ports above |

Register each manifest, Helm release and post-Helm step that runs in the cluster in `MANIFESTS_BY_STACK`, `HELM_RELEASES_BY_STACK` or `POST_HELM_BY_STACK` (`src/devops_cli/commands/k8s/stack_lifecycle.py`), with a path in the environment tree, or a file of the product base in `PRODUCT_MANIFESTS_BY_STACK` or `PRODUCT_POST_HELM_BY_STACK`, with a path in `k8s/devops`, so that `devops k8s deploy-stack --stack all` deploys it with the `infra`, `llm`, `logging`, `devops`, `gitea` and `chat` stacks. deploy-stack applies a file of `MANIFESTS_BY_STACK` with `kubectl apply -f` and a kustomization directory with `kubectl apply -k`.

## Prerequisites

- A cluster:
  - the k3s homelab: its nodes run k3s with the bundled local-path storage turned off (`--disable local-storage`);
  - or minikube running (`minikube status`, or started by `devops devcontainer post-start`).
- kubectl and helm on PATH (installed by devcontainer features)
- standard Kubernetes context configuration (the CLI uses `$KUBECONFIG` or defaults to `~/.kube/config`)
- A storage layer that serves the `local-path` StorageClass, which the claims of the stacks use:
  - On the homelab, the storage layer comes from the dan-petty/homelab repository: its `make storage` applies `k8s/manifests/local-path-storage.yaml`. That manifest holds namespace `local-path-storage`, the local-path provisioner (`rancher/local-path-provisioner` v0.0.28), the default StorageClass `local-path` (reclaim policy `Delete`) and the StorageClass `fast-nvme` (reclaim policy `Retain`). This repository does not deploy them. [Local-Path Volume Placement](#local-path-volume-placement) tells where the provisioner keeps a volume.
  - On minikube, the default `storage-provisioner` addon serves only the class `standard`. The class `local-path` comes from the `storage-provisioner-rancher` addon. `devops` starts minikube with `--addons=storage-provisioner-rancher`, so the class `local-path` exists from the first start. A minikube that already runs keeps its addons. Run `minikube addons enable storage-provisioner-rancher` one time on that cluster, or the claims that name `local-path` stay `Pending`.

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
# Open WebUI refuses a Socket.IO connection from an origin that is not an Ingress host (llm/open-webui-origins).
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
The LiteLLM gateway is the single entry point to every inference server. It serves the virtual models `devops-chat`, `devops-coder`, `devops-reasoning`, `devops-review` and `devops-triage`, plus models by name (`qwen3.8:27b`, `qwen3-embedding:0.6b`). It checks each prompt against the window of every deployment before it calls a backend, so a prompt never reaches a deployment that would cut it (see below). It falls back from an unavailable `devops-coder` or `devops-reasoning` to `devops-chat`, and rejects requests without its master key. `devops k8s deploy-stack` writes the key (`llm/llm-gateway-secrets`, starting with `sk-`) from the keyring before the gateway starts, adopting a live key the keyring lacks and generating one where neither has it; `devops k8s push-secrets --only llm/llm-gateway-secrets` does the same alone (see Cluster Secrets).

The routing config is `llm/gateway/config.yaml`. LiteLLM reads it only at start. The gateway kustomization (`llm/gateway/kustomization.yaml`) generates ConfigMap `llm-gateway-config-<hash>` from that file, and writes the name into the Deployment. When the config changes, the name and the pod template change, and Kubernetes rolls the gateway onto the new config. Argo CD's `llm` Application renders the kustomization when it syncs, and `devops k8s deploy-stack --stack llm` applies it with `kubectl apply -k llm/gateway`. Thus a config change needs no `kubectl rollout restart` (#1929). Argo CD prunes the ConfigMap of the old config. Without Argo CD, that ConfigMap stays until `teardown-stack` deletes the namespace.

A workstation reaches the gateway through the Cloudflare tunnel, and the Cloudflare edge cuts a request that has no data for 125 s (#2365). The CLI therefore streams every OpenAI-compatible chat call, and the gateway writes an SSE comment (`: ping`) into a streamed reply that has no data for 30 s (`litellm_settings.sse_keepalive_ping_interval_seconds`), also before its first token. Thus a long prefill, queue or reasoning does not end the call. A ping sends the status line before the gateway has routed the call, so a call whose first token comes after the first ping has no `x-litellm-*` response headers, and its spend-ledger row names no serving backend. A failure after the first ping comes as an SSE error frame under status 200, and the client reports it as the HTTP status that the frame names.

#### Gateway database and virtual keys
LiteLLM keeps its virtual keys (`/key/generate`: expiry, request and token limits, model list, alias) only in a Postgres database. The database is the CloudNativePG `Cluster` `llm-gateway-db` in `llm/gateway-db.yaml`, with one instance, 5 GiB on `local-path`, and Argo CD annotated `Prune=false,Delete=false`. The gateway keeps the master key as its admin key, and a virtual key does not replace it for the cluster Jobs yet.

- **No secret in git, no person step.** The `Cluster` names no `bootstrap.initdb.secret`. CloudNativePG therefore creates the user `litellm`, the database `litellm` and Secret `llm-gateway-db-app` with a generated password when it creates the database. The Deployment reads `DATABASE_URL` from the `uri` key of that Secret. `devops k8s push-secrets` has no row for it, and the secret guard of `tests/invariants/test_k8s_manifests.py` accepts a Secret that a `Cluster` without `initdb.secret` creates.
- **Network.** The gateway's policy gains an egress rule to the pods with label `cnpg.io/cluster: llm-gateway-db` on 5432. Policy `llm-gateway-db-perimeter` admits the gateway's pods and the operator in `cnpg-system` (8000 and 5432), and namespace `monitoring` on the metrics port 9187 only. Its egress is DNS and the Kubernetes API: the instance manager reads Secrets and updates status through the API, as the Mattermost database does. `llm-default-perimeter` leaves the database pods out.
- **Start-up.** LiteLLM applies its migrations with `prisma migrate deploy` before it opens port 4000. The root file system stays read-only: `LITELLM_MIGRATION_DIR` is an `emptyDir`, and the Prisma engines are in the image under `/opt/prisma`. A `startupProbe` gives a migrating pod ten minutes before the liveness probe starts. `ENFORCE_PRISMA_MIGRATION_CHECK=true` makes a failed migration end the start-up. Without it LiteLLM logs the failure and starts on an empty schema, and nothing runs the migration again.
- **When the database is down**, a virtual key that the gateway cannot check is refused: `allow_requests_on_db_unavailable` stays at its default `false`, because the gateway is reachable from outside the cluster. The master key needs no database, so the cluster Jobs, the CLI and Open WebUI keep working. The readiness probe uses `/health/liveliness`, because `/health/readiness` answers 503 while the database is down and Kubernetes would then remove every gateway pod from the Service. `/health/readiness` stays a manual check after a sync: its `db` field shows `connected`. Models stay in git (`store_model_in_db: false`).
- **Stops and restarts.** A rolling update starts the new gateway pod before it stops the old pod. On SIGTERM, uvicorn stops to accept connections and waits for each open call, and LiteLLM sets no `timeout_graceful_shutdown`, so only the kubelet ends the wait. The pod has `terminationGracePeriodSeconds: 600`, not the default 30 s, so a long call that is open at a rollout ends normally, and the old pod writes its spend queue (#5301). A call that continues for more than 600 s after the SIGTERM fails. The router timeout (1500 s) is the upper limit of the grace period. The operator stops the database instance first with a smart shutdown, which refuses new connections and waits for each open session, and then with a fast shutdown. The idle sessions of the old gateway pod keep a smart shutdown open, and a gateway pod that starts in that time stops after the 4 tries of its migration check, which take about 5 s. Thus the `Cluster` sets `smartShutdownTimeout: 15`, not the default 180 s, and a restart of the database takes seconds. The instance manager reads the value at each stop, so a change of it restarts nothing. Each probe of the gateway waits 5 s (`timeoutSeconds`), not the default 1 s, because one slow request holds the one uvicorn worker for some seconds. Change the PostgreSQL image and the LiteLLM image in different pull requests, as Renovate does: one change of both restarts the database while the new gateway pod starts.
- **No `LITELLM_SALT_KEY`.** LiteLLM uses the salt key only to encrypt values that it stores in the database, such as provider keys of models added at run time, and it falls back to the master key. It stores virtual keys as a SHA-256 hash of the key, so a salt key does not protect them. With `store_model_in_db: false` the database holds nothing to encrypt. Set a salt key, generated once and never rotated, before the first change that stores a credential in the database.
- **Order.** The operator is Helm release `cloudnative-pg` of stack `infra` (Argo CD Application `cloudnative-pg`). On a cluster without Argo CD, deploy-stack applies `llm/gateway-db.yaml` after the Helm releases, because the `Cluster` needs the operator's CRD. A gateway pod that starts before the database waits for Secret `llm-gateway-db-app`, and then restarts until the database accepts connections.
- **Rollout under Argo CD.** After the merge, Argo CD creates the policy and the `Cluster`, and starts a new gateway pod beside the old one (one replica, `maxSurge` 1, `maxUnavailable` 0). The new pod waits for the Secret, restarts a few times until the database accepts connections, migrates the empty database, and passes its readiness probe. Then Kubernetes stops the old pod. The old pod answers all requests meanwhile, so the gateway has no downtime. No person runs a command.
- **Monitoring.** PodMonitor `llm-gateway-db`, in the same file, selects the instance pods on their port `metrics` (9187), and Alloy scrapes them as it scrapes `mattermost-db`. The rules of group `llm-gateway-db` warn when the exporter has no connection or no series, when the client connections pass 80% of `max_connections`, and when the databases and the WAL pass 80% of the claim (see Alerting). The CloudNativePG dashboard shows the database (see Grafana Dashboards).
- **Spend logs.** The gateway writes a row for each request to its spend-log table, about 71,000 rows a week. No code reads that table: the AI spend dashboard reads Prometheus. To read rows by hand, use the paginated `/spend/logs/v2`. The v1 `/spend/logs` reads and serializes up to 10,000 rows in the one uvicorn worker, and the probes of the gateway wait for it. `general_settings.maximum_spend_logs_retention_period` is `30d`, so a cleanup job of the gateway deletes the rows older than 30 days, and the table stays inside the claim. LiteLLM starts the job 24 hours after each start of the gateway process, and then each 24 hours. The gateway frequently restarts before 24 hours, and each restart starts the count again, so a run can come some days late. One run deletes up to 500,000 rows, so a late run still removes all the rows older than 30 days. If no run occurs, `GatewayDatabaseNearClaim` warns before the claim fills.
- **Backups.** The database has none yet. A lost node loses its virtual keys, and a person mints them again. #3741 adds the backup, in the form that #2144 chooses.

The Service is a NodePort that Kubernetes assigns; find it with `kubectl -n llm get svc llm-gateway`, then call the API from any node address:
```bash
KEY=$(kubectl -n llm get secret llm-gateway-secrets -o jsonpath='{.data.master-key}' | base64 -d)
curl -H "Authorization: Bearer $KEY" http://<node>:<node-port>/v1/models
```
Four groups call a hosted provider: `gemini-3.8-flash` (Google), `claude-sonnet-5-5` and `claude-haiku-5-5` (Anthropic), and `deepseek-v4.1-flash-1017` (DeepSeek, through OpenRouter). A prompt sent to one of them leaves the cluster, and the provider bills each token. No pool names them, and the one fallback links a hosted group to a hosted group (`claude-sonnet-5-5` to `deepseek-v4.1-flash-1017`, #3152), so a request reaches a provider only when its caller names a hosted group. A call to `claude-sonnet-5-5` that fails (an Anthropic error, a rate limit, a spend limit) then goes to OpenRouter and not to Anthropic: in the review of 12 golden plans that model found 38% of the known defects against 56% for Sonnet 5.5, and the Gemini Flash Lite, Gemma and older Gemini models found 7 to 25%, so only it is a fallback. A person stores each key in the keyring with `devops config set gemini.api_key`, `devops config set anthropic.api_key` or `devops config set openrouter.api_key`. Then `devops k8s push-secrets --only llm/llm-gateway-secrets` writes it to the Secret as `gemini-api-key`, `anthropic-api-key` or `openrouter-api-key` and restarts the gateway. The gateway starts without a key, and a call to a group with no key fails with an error that names the missing key; the other groups work. The gateway NetworkPolicy admits TCP 443 to public addresses for these calls, and to no private range (SECURITY.md rule 13). OpenRouter picks the provider of a `deepseek-v4.1-flash-1017` call. The group asks for the cheapest provider (the OpenRouter `floor` route) with fp8 weights that does not store or train on prompts (`data_collection: deny`); a provider that fails a filter is skipped, so the price can be above the cheapest one, and a call fails when no provider passes. devops-cli records the spend of each hosted group: genai-prices holds the prices of the Gemini and Claude groups, and `_HOSTED_GROUP_PRICES` in `src/devops_cli/ai/spend/pricing.py` holds the price of the DeepSeek group, at the rates of its gateway entry (#4403). A prompt token that the provider reads from its cache costs the cached input rate, and `tests/ai/spend/test_hosted_group_prices.py` fails when a hosted group has no price or the two prices differ. A caller sets the reasoning effort. The implement job of the Service and its runner Jobs call this group ([docs/CLUSTER.md](../docs/CLUSTER.md#roadmap-service), Roadmap service, item 19). Both Claude models refuse `temperature`, `top_p` and `top_k` with a 400, and the cost map of the pinned LiteLLM image marks both models `supports_sampling_params: false`. Their groups also drop the three themselves and set their own prices, so a new map changes neither. Sonnet 5.5 also refuses a forced tool call, so a caller of the group sends `tool_choice` `auto`. LiteLLM turns a `response_format` into a forced tool call unless its model map says the model supports native structured output, so each Claude group sets `supports_native_structured_output` and `supports_response_schema` and a structured reply works (#3140). Above 100,000 prompt tokens Haiku 5.5 costs 0.50 USD for input and 2.50 USD for output per million tokens, and LiteLLM has no price tier at that size: the spend of such a call reads low. To check a key after the rollout, run `curl -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d '{"model":"gemini-3.8-flash","messages":[{"role":"user","content":"Say ok"}],"max_tokens":16}' http://<node>:<node-port>/v1/chat/completions`.

TypeSafe Jev (`typesafe/jev-1.14`) is a decision model, not a group. OpenRouter refuses it on chat completions with HTTP 400, so `model_list` has no entry for it. The gateway serves it as the pass-through `POST /v1/systemone` (`general_settings.pass_through_endpoints`), which forwards the request body unchanged to `https://openrouter.ai/api/v1/systemone` (#4289). The client `SystemOneModel` posts to `{ai.gateway_url}/systemone`, so a Jev call needs no setting beyond `ai.gateway_url` and the gateway key. The pass-through checks the gateway key of the caller, sends the OpenRouter key from the Secret key `openrouter-api-key` (keyring `openrouter.api_key`) and forwards no header of the caller. It cannot set provider preferences such as `data_collection` in the body, so the privacy setting of the OpenRouter account applies to Jev calls. A prompt sent to Jev leaves the cluster (SECURITY.md rule 13). OpenRouter bills 0.042 USD per million input tokens and nothing for output; the spend ledger of the gateway does not see these calls, because the pass-through has no cost entry. To check the route after a rollout, run `curl -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d '{"model":"typesafe/jev-1.14","state":"The page is blank after Pay.","questions":{"is_bug":{"type":"noul","instructions":"Is this a software defect?"}}}' http://<node>:<node-port>/v1/systemone`.

Each `ollama_chat` deployment sets `max_input_tokens` in its own top-level `model_info`, equal to the `OLLAMA_CONTEXT_LENGTH` of its tier, and `devops ai gateway render` keeps the two equal. LiteLLM reads the window only from that place: a `model_info` under `litellm_params` has no effect. A deployment that sets no window reads the cost-map entry of its backend model, which the last deployment registered wrote. Thus each deployment sets its own window, and a test holds this (#2825). Ollama cuts a prompt that is longer than its window and returns no error, so the check is the only guard. The gateway sets no `context_window_fallbacks`: `devops-chat`, `devops-coder` and `devops-reasoning` run on `ollama-48gib-fast`, and `devops-background` and `devops-triage` run on `ollama-64gib-standard`. Both tiers have the same window, 262,144 tokens, so none of these groups could take a prompt that another of them refused. A prompt fails with a context-window error only when no group of the chain holds it.

These groups route reviews, embeddings and background work:

- `devops-review` spreads one model name over two Ollama tiers: `qwen3.8:27b` on `ollama-48gib-fast` and `ollama-64gib-standard`. The router sends each request to the deployment with the fewest requests in flight (`least-busy`), and pre-call checks keep a prompt off any deployment whose window it exceeds. Both deployments have the window of 262,144 tokens, so a prompt up to that size fits either one. The CLI holds at most 2 review requests in flight, one for each tier (`DEFAULT_GATEWAY_REVIEW_SLOTS`). No deployment is capped with `max_parallel_requests`: LiteLLM waits on the cap only after routing, so queued requests pile up behind it while larger servers idle, and the backends queue excess requests themselves.
- Ollama models are also served under their own names: `qwen3.8:27b` and the embedding model `qwen3-embedding:0.6b`. An embedding group configures `model_info.mode: embedding` so health checks embed rather than generate.
- `qwen3-embedding:0.6b` has a deployment on each tier that serves embeddings, and LiteLLM's `order` sets which the router tries first. `ollama-48gib-fast` and `ollama-64gib-standard` serve none: they load `qwen3.8:27b` and no other model, so an embedding batch never evicts it (#3567). The gateway routes the embedding group with `simple-shuffle` across order 1 deployments (#2027). Order 1 is each instance of a tier at or below the `embedding_only` threshold (GPU Placement): `ollama-24gib-embed-gpu0` and `-gpu1`, which embed a 32-chunk RAG batch in 2 s and have no chat model to wait for or to evict. There is no next order, so an embedding call fails when both deployments of order 1 fail. Each deployment sets `num_ctx` to `CONST_RAG_MAX_CHUNK_TOKENS` (8,192), so the largest RAG chunk fits. With its 32,768-token default, the embedder takes 5.2 GB, not 2.9 GB, on `ollama-64gib-standard`.
- `qwen3.8:27b` pins the model of `devops-review`: it copies the backends and windows of the `devops-review` deployments of that model, so a pinned review is routed as the pool routes it. `devops-triage` and `devops-background` fall back to it.
- `devops-triage` is the fast triage model for candidate intake: `qwen3.8:27b` on `ollama-64gib-standard`. It serves candidate triage alone so backlog placement completes within one poll round. The router falls back to `qwen3.8:27b` if unavailable. The Service does not call it while the ConfigMap names one hosted chat model ([docs/CLUSTER.md](../docs/CLUSTER.md#roadmap-service), Roadmap service, item 19).
- `devops-background` is the group of background work: `qwen3.8:27b` on `ollama-64gib-standard`. That tier serves one request per model at a time, and it also serves interactive and review groups, so background work and those calls wait for each other. The router falls back to `qwen3.8:27b` if unavailable. A `devops-review` fallback reaches it, and so does a cluster job whose settings name it (the ConfigMap of `k8s/devops/` names it for none while it names one hosted chat model); the pinned group has no fallback. The client streams the call and the gateway's pings keep it open, so the client reads the reply of a `devops-review` call that falls back to this tier. Use it for `devops review path --watch`, `devops ai agents` and `devops ai analyze` through environment overrides, never in workstation `config.yaml`, so no interactive run lands on it. Set `DEVOPS_CLI_AI_MAX_RETRIES=1`; the ConfigMap template of `k8s/devops/` sets `ai.max_retries: 1` for the in-cluster services, which call `deepseek-v4.1-flash-1017` and not this group (item 19), and `devops k8s deploy-stack --stack devops` applies it ([docs/CLUSTER.md](../docs/CLUSTER.md#go-live-check), Roadmap service, Go-live check). The gateway retries a call of that hosted group up to 5 times (`router_settings.num_retries`), so the one client retry adds a layer on a call that the provider bills. The gateway stops a call when the tier sends no token for 1,100 s, and does not retry it. The client retries a call that fails or times out before its reply starts in its HTTP transport, the single retry layer, `ai.max_retries + 1` times, and each retry waits for the same single slot. A call that fails after its reply starts is not retried. With `1` a call is sent at most two times; `0` does not stop retries, because the transport then makes five attempts:
  ```bash
  DEVOPS_CLI_AI_MAX_RETRIES=1 DEVOPS_CLI_AI_TASK_ANALYSIS_MODEL=devops-background \
    DEVOPS_CLI_AI_TASK_COMPOSE_MODEL=devops-background devops review path src --watch --concurrency 1
  DEVOPS_CLI_AI_MAX_RETRIES=1 DEVOPS_CLI_AI_MODEL=devops-background devops ai agents   # likewise devops ai analyze
  ```

Measure the `devops-review` backends again whenever a backend, model or node changes. `devops ai gateway tune` measures each deployment of a group on its own, from an ephemeral Python container attached to the gateway pod (`kubectl debug`), so each backend is measured over the gateway's own network path. For each deployment it reports the engine, the GPUs, the capacity (fixed-length tokens per second at the best concurrency) and the cost (the tokens the model writes per request). It changes nothing. The `least-busy` router reads none of these numbers: it sends each request to the deployment with the fewest requests in flight. Use the numbers to decide which backends a group holds.
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

#### Gateway spans
The `otel` callback of LiteLLM sends a span for each gateway request to the OpenTelemetry Collector over OTLP/HTTP, with the service name `llm-gateway` (#4518). The spans show the time of the queue, the retries and the fallbacks of a call. The `OTEL_*` variables of `llm/gateway/deployment.yaml` name the Collector Service. `turn_off_message_logging: true` in `llm/gateway/config.yaml` keeps the prompt and the reply off the spans. LiteLLM still writes the key hash, the key alias, the user and the `x-` headers of each request as `metadata.*` attributes, and a refused key puts its hash in the error text. A management endpoint span gets each field of the request and response bodies as a `request.*` or `response.*` attribute, for example the raw key of `/key/block` and the callback secrets of `/team/{team_id}/callback` (#4539). The `transform/key_data` processor of the Collector's traces pipeline (`otel/values.yaml`) deletes these attributes and each attribute whose name holds `authorization` or `api-key`, and it replaces each 64-digit hex value of a gateway span or span event, before Tempo stores the span. The gateway's egress admits port 4318 of the Collector pods only, so no gateway span goes to Tempo past this rule. A request with a `traceparent` header gets its gateway span as a child of the caller's span; a request without one starts its own trace. The `k8s` row of `devops ci` checks the callback, the endpoint, the egress rule and the effect of the processor on the attributes that LiteLLM writes.

### GPU Placement: Ollama tiers
Ollama runs as one DaemonSet per total-VRAM tier (`ollama-16gib` … `ollama-128gib`, `llm/profiles/ollama-profiles.yaml`), each behind its ClusterIP Service `ollama-<n>gib`. The gateway reaches the tiers through aliases of those Services, `ollama-48gib-fast` and `ollama-64gib-standard`, and through the Services of the embedding instances, `ollama-24gib-embed-gpu0` and `-gpu1` (`llm/gateway/config.yaml`).

**The models each target keeps.** The gateway config (`llm/gateway/config.yaml`) sends each model to the targets below. A node that runs the tier of a target keeps the models of that target and no other model, and a prune of the model store removes the rest. `tests/k8s/test_k8s_ollama_models.py` fails when this table and the gateway config differ.

| Gateway target | Models it keeps |
| :--- | :--- |
| `ollama-24gib-embed-gpu0` | `qwen3-embedding:0.6b` |
| `ollama-24gib-embed-gpu1` | `qwen3-embedding:0.6b` |
| `ollama-48gib-fast` | `qwen3.8:27b` |
| `ollama-64gib-standard` | `qwen3.8:27b` |

**Prune unused models.** `devops k8s ollama prune` removes the models that no tier of a node serves. `--plan` prints the models that each node would lose and removes none. `--dry-run` prints the `kubectl exec` commands of each gateway target and makes no request to the cluster. A node whose `ollama list` fails loses no model.

**GPU thresholds.** `llm/profiles/gpu-thresholds.yaml` holds two values of `nvidia.com/gpu.architecture`, both `pascal`. Argo CD tracks `main`, so the values are in git and not in `config.yaml`. A tier in `llm/profiles/tier-templates/` is at or below a threshold when the newest architecture that it accepts is that architecture or an older one:

- At or below `embedding_only`: the tier serves embedding models alone, keeps one model loaded and sets `LLAMA_ARG_THREADS: "1"`, because the model runs on the GPU. Each of its gateway deployments has order 1. Otherwise the tier runs as its template says: it is a chat tier, it loads one model, and the gateway sends it no embedding batch.
- At or below `per_gpu`: the tier runs one DaemonSet per GPU, with `-gpu<n>` in the name. Each claims `nvidia.com/gpu: 1` and has its own Service and gateway deployment. A later instance requires a node with that many GPUs (`nvidia.com/gpu.count`). The annotation `llm.devops.io/gpu-count` of the template says how many instances exist, and `llm.devops.io/embedding-model` names the model of its gateway deployments when the tier is embedding-only. The instances of a node share the model directory, so they set `OLLAMA_NOPRUNE`.

A rendered tier is named `ollama-<VRAM of one instance>gib-<embed or speed tier>`. Its speed tier is `embed` when it serves embedding models alone, so the Services `ollama-slow`, `ollama-24gib` and `ollama-24gib-slow`, which select `slow`, do not reach it.

To change a value, edit the file and run `devops ai gateway render --apply`. The command writes the regions between the two `rendered` lines of `ollama-profiles.yaml`, `services.yaml` and `llm/gateway/config.yaml`. A test fails when those regions differ from its output. The command refuses:

- A threshold newer than the newest architecture of the templates. Tiers such as `ollama-64gib` accept any architecture and have no template, so they cannot follow it. Add a template first.
- A generation deployment on an embedding-only tier, and names each group. Which tier serves a group instead is a routing decision, so move the group in `llm/gateway/config.yaml` first.

Only the tiers in `tier-templates/` follow the thresholds. A Pascal node with a total VRAM of another tier, such as `ollama-16gib` or `ollama-64gib`, runs that tier as it is written.

**One model on the large tiers.** `ollama-48gib` and `ollama-64gib` load `qwen3.8:27b` and no other model (#3567). They set `OLLAMA_CONTEXT_LENGTH` to 262144, the native limit of the model, `OLLAMA_NUM_PARALLEL` to 1, `OLLAMA_MAX_LOADED_MODELS` to 1 and `OLLAMA_KEEP_ALIVE` to `-1`. The first request after a pod starts loads the model from the node model directory, and the model then stays loaded: no swap drops its KV cache. The gateway sends these tiers no other model and no embedding batch, and a test fails if a deployment does. A person who wants another model on them changes the DaemonSets and the gateway routes in one pull request. The model directories of the nodes still hold the files of other models. A request that names one of them straight to the tier, past the gateway, makes Ollama unload `qwen3.8:27b` to load it.

The speed Services `ollama-fast`, `ollama-standard` and `ollama-slow` (`llm/profiles/services.yaml`) name no VRAM size. Clients of Ollama's native API use them: `ollama-fast` is the `ollama-ingress` backend and the CLI's default Service (`devops k8s port-forward`, `configure-urls`). Open WebUI uses none of them: it sends its chats and its RAG embeddings to the gateway. When a host changes, change the selector of the speed Service. Its clients then follow with no edit. [llm/profiles/README.md](llm/profiles/README.md) describes the profiles and their Services.

A tier's pods schedule only on a node whose labels satisfy the tier's required node affinity. Every tier requires `nvidia.com/gpu.total-vram-gib` to be one of its values, and three also require `nvidia.com/gpu.architecture`. `nvidia.com/gpu.present=true` marks a GPU node, and `deploy-stack` treats a node with `nvidia.com/gpu` capacity above zero as one too.

| Tier | `nvidia.com/gpu.total-vram-gib` | `nvidia.com/gpu.architecture` | Serves |
| :--- | :--- | :--- | :--- |
| `ollama-16gib` | `16Gi`, `20Gi` | any | no |
| `ollama-24gib` | `24Gi`, `28Gi` | `pascal`, `maxwell`, `kepler` | no |
| `ollama-32gib` | `32Gi`, `36Gi`, `40Gi`, `44Gi` | any | no |
| `ollama-48gib` | `48Gi`, `52Gi`, `56Gi`, `60Gi` | `ada-lovelace`, `ampere`, `blackwell`, `hopper` | yes |
| `ollama-24gib-embed-gpu0` | `48Gi`, `52Gi`, `56Gi`, `60Gi` | `pascal`, `maxwell`, `kepler` | yes |
| `ollama-24gib-embed-gpu1` | `48Gi`, `52Gi`, `56Gi`, `60Gi` | `pascal`, `maxwell`, `kepler` | yes |
| `ollama-64gib` | `64Gi`, `68Gi` | any | yes |
| `ollama-72gib` | `72Gi`, `76Gi`, `80Gi`, `84Gi`, `88Gi`, `92Gi` | any | no |
| `ollama-96gib` | `96Gi`, `100Gi` … `124Gi` in steps of 4 | any | no |
| `ollama-128gib` | `128Gi` | any | no |

**Serves** says whether a node of the cluster satisfies the tier, so that the tier has a pod. Every client that names an Ollama Service names one that selects a serving tier: the CLI defaults, the `ollama-ingress` backend, the gateway's `api_base` targets and the devcontainer's `ollama.endpoint`. `tests/ai/benchmark/test_k8s_llm_gateway.py` checks this against the column. When a host goes offline or a tier gets a node, change the column. The test then names each client to move.

`ollama-16gib` has a node, and its **Serves** value is `no` because its host is unstable. A cordon does not stop a DaemonSet pod, so the gateway, the review slots and the devcontainer name no Service of this tier. The DaemonSet and its Services stay, so a revert of the change that removed the clients brings the tier back. The node of the tier has 16 GiB of memory, of which about 13 GiB is allocatable, so the `ollama` container limits its memory to its request of `8Gi`: a model load past the gateway ends in an OOM kill of the container, not in a node with no free memory.

**What sets the labels.** The cluster's node-provisioning automation, which lives outside this repository, sets `nvidia.com/gpu.present` and `nvidia.com/gpu.architecture` on every GPU node. It sets `nvidia.com/gpu.total-vram-gib` only on a node with more than one GPU, as the sum of its GPUs' memory rounded to the nearest whole GiB. GPU Feature Discovery labels per-GPU memory and the GPU count, not a total. So a single-GPU node gets no total, and a multi-GPU total can come out as a value no tier lists, such as `47Gi`. Set the label by hand, with a value from the table:

```bash
kubectl label node <node> nvidia.com/gpu.total-vram-gib=<N>Gi --overwrite
```

`deploy-stack --stack llm` reads the nodes once, right after it checks the cluster is reachable, and warns about each GPU node no tier accepts: the missing or unaccepted `total-vram-gib` with the command above, or an `architecture` outside the accepted ones. If no node satisfies any tier, it says no Ollama pod will schedule, and if it cannot read the nodes it says it could not check the labels. It also warns on an Argo CD-managed cluster. It never stops the deploy, since the stack's other workloads need no GPU label. The accepted values are read from `ollama-profiles.yaml`, so a tier changed there is checked with no other edit.

The gateway's policy `llm-gateway-perimeter` (`llm/gateway/networkpolicy.yaml`) is applied with the llm manifests, by `deploy-stack` or Argo CD's `llm` Application. It admits TCP 4000 from any source, since LiteLLM rejects a request without the master key, and limits the gateway's egress to the pods labelled `llm.devops.io/provider: ollama` on 11434 and kube-system DNS on port 53.

The cache Valkey's policy `valkey-perimeter` (`llm/valkey.yaml`) admits Open WebUI on TCP 6379 and the `monitoring` namespace on the exporter port 9121. It allows no egress, and `llm-default-perimeter` leaves the Valkey pods out. Valkey requires the password of `llm/valkey-auth` (see Cluster Secrets). Open WebUI sends it in its Redis URL, and Valkey reads it from a quoted config line. A typed value must therefore use only letters, digits, `-`, `.`, `_` and `~`. The gateway and Portkey use no Valkey: the gateway config turns on no cache, and Portkey reads a cache only from `REDIS_CONNECTION_STRING`, which is not set.

The cache Valkey keeps at most 1536 MiB of data (`--maxmemory`), three quarters of its 2048Mi limit. The rest of the limit holds fragmentation and Valkey's own overhead. At the bound, Valkey refuses writes and evicts no key (`--maxmemory-policy noeviction`). Open WebUI keeps its session pools and token revocations there, and an evicted revocation makes a signed-out token valid again. The run index (`llm/valkey-runs.yaml`) uses the same policy with a bound of 512 MiB. `ValkeyMemoryNearBound` warns when the cache Valkey keeps its data above 80% of the bound for 10 minutes. The rule selects each exported Valkey with the policy `noeviction`, and the run index has no exporter, so the rule does not watch it.

devops-cli's cache Valkey (`llm/valkey-devops.yaml`) holds the caches of the roadmap Service and the cluster jobs: the embeddings that `EmbeddingsEngine` writes, and the threat-intelligence reads. Each round of the Service and each job is a new process with an empty memory cache, so without it intake embeds every item of the roadmap again on each round. The devops ConfigMap names it in `valkey.url`, and its password reaches the pods from `devops/devops-cli` as `DEVOPS_CLI_VALKEY_PASSWORD`, the variable of `valkey.password`. Its policy `valkey-devops-perimeter` admits namespace `devops` on TCP 6379 and the `monitoring` namespace on the exporter port 9121, and allows no egress. `llm-default-perimeter` leaves its pods out, and `devops-default-perimeter` lets namespace `devops` reach namespace `llm` on 6379 beside the gateway's 4000. It keeps at most 96 MiB of data, three quarters of its 128Mi limit, writes no RDB or AOF, and at the bound evicts the least recently used key (`--maxmemory-policy allkeys-lru`): an evicted key costs one more embedding request. It can't share the cache Valkey, which must not evict Open WebUI's state.

Qdrant requires the key of `llm/qdrant-api-key` (see Cluster Secrets) on every REST and gRPC request. Only `/`, `/healthz`, `/readyz`, `/livez` and the files of its web UI need no key. The qdrant container reads the key as `QDRANT__SERVICE__API_KEY` through `env` in `llm/values-qdrant.yaml`. Open WebUI is the only workload under `k8s/` that names the Qdrant Service, and it sends the key as `QDRANT_API_KEY`. Alloy scrapes `/metrics` with the key as a bearer token, and devops-cli sends keyring `qdrant_api_key`, which the push keeps equal to the Secret. `tests/commands/k8s/test_k8s_qdrant_security.py` fails on a top-level key of `llm/values-qdrant.yaml` that the pinned chart (`tests/fixtures/charts/qdrant/`) does not declare, because Helm drops such a key with no error.

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

Alloy, run by the `k8s-monitoring` release (`monitoring/k8s-monitoring-values.yaml`), scrapes every target but two and remote-writes to the Prometheus server: the kubelet, cAdvisor, kube-state-metrics, node-exporter, the `argocd` (`controller`, `server`, `repoServer`, and `redis` exporter), `argo-workflows` (the workflow controller), `llm-gateway`, `pyroscope` and `qdrant` ServiceMonitors, the `llm-gateway-db` and `mattermost-db` PodMonitors (the CloudNativePG metrics exporter of each instance on port 9187), CoreDNS (`clusterMetrics.kubeDNS`), the pods annotated for scraping (`annotationAutodiscovery`), and the Alloy collectors, Grafana, Loki, Tempo and the DCGM exporter (`integrations`). The Prometheus server scrapes only itself and the OpenTelemetry Collector (#1130). These monitoring components run outside k8s-monitoring:

| Component | Owner | Reason |
| :--- | :--- | :--- |
| Prometheus server and Alertmanager | Their own `prometheus` release (`monitoring/prometheus-values.yaml`) | k8s-monitoring ships collectors, not a metrics store or an alert router. Alloy writes to this server, which evaluates the alert rules and sends alerts to Alertmanager. The server scrapes itself, and Alloy scrapes Alertmanager through its pod annotations |
| Grafana | Its own `grafana` release (`monitoring/grafana-values.yaml`) | k8s-monitoring does not deploy Grafana; its `grafana` integration scrapes Grafana's pod (#1131) |
| Loki | Its own `loki` release, in the `logging` stack (`logging/loki-values.yaml`) | Loki belongs to the logging stack, so k8s-monitoring's Loki integration scrapes it only where that stack runs |
| Pyroscope server | Separate `pyroscope` release (`monitoring/pyroscope-values.yaml`); collection: k8s-monitoring `profiling` | k8s-monitoring collects profiles (`profiling` in `monitoring/k8s-monitoring-values.yaml`, sent to `destinations.localPyroscope`); it does not deploy the server that stores profiles, and it scrapes Pyroscope through the chart's own ServiceMonitor (#1131, #1134) |
| Trace backend (Tempo) | Its own `tempo` release (`otel/tempo-values.yaml`) | k8s-monitoring's Tempo integration scrapes Tempo, which its own chart deploys in `otel`. The collector's trace exporter has a Tempo to reach when the collector starts: `deploy-stack` installs `tempo` before `otel-collector`, and the `cluster` app-of-apps syncs the `otel-collector` Application in sync wave 1, after `tempo` (#409) |
| dcgm-exporter | Its own `dcgm-exporter` chart (`monitoring/dcgm-exporter-values.yaml`) | k8s-monitoring's dcgm-exporter integration scrapes the exporter but ships none, so the chart deploys it on every GPU node; the chart's own ServiceMonitor stays off. The exporter collects the fields that `customMetrics` lists, and `podAnnotations` holds the checksum of that list, so a changed list restarts the pods |
| otel-collector | Its own `otel-collector` release (`otel/values.yaml`), scraped by the Prometheus server's `kubernetes-pods` job, which keeps only namespace `otel` | devops-cli exports delta temporality, and Alloy's `deltatocumulative` is experimental only, so k8s-monitoring cannot replace the collector (#1132). The server scrapes it, not Alloy, so the collector's export failures stay visible when Alloy is what fails |
| prometheus-operator-crds | Its own release, installed first | The `argocd`, `argo-workflows`, `llm-gateway`, `pyroscope` and `qdrant` ServiceMonitors and the CloudNativePG PodMonitors need the `monitoring.coreos.com` CRDs, which k8s-monitoring 4.x no longer ships |

cloudflared, Traefik, Alertmanager, roadmap-service, the three cert-manager pods (port 9402) and `llm/valkey` (`redis-exporter` sidecar on port 9121) are found by annotation autodiscovery (#1130, #551), through the `prometheus.io/*` annotations their plain manifests carry, each with the pod's `app.kubernetes.io/name` as its job; CoreDNS comes through `clusterMetrics.kubeDNS`.

`devops prometheus targets` reads the server's `/api/v1/targets`, so it lists only the server's two jobs; Alloy's targets appear in Prometheus as their `up` series.

## Grafana Dashboards

The environment dashboards live in `monitoring/dashboards/`, and the product dashboards of devops-cli, which read the `devops_cli_*` series, live in `devops/dashboards/` (#5292). The `kustomization.yaml` of `monitoring/dashboards/` generates five ConfigMaps and lists `../../devops/dashboards`, whose `kustomization.yaml` generates the sixth ConfigMap with the same options. Each ConfigMap has the label `grafana_dashboard: "1"`, and the Grafana dashboard sidecar (`monitoring/grafana-values.yaml`) loads every ConfigMap with that label:

| ConfigMap | Dashboards |
| :--- | :--- |
| `grafana-k8s-global-dashboards` | `k8s-views-global.json`, `k8s-views-pods.json` |
| `grafana-k8s-node-dashboards` | `k8s-views-nodes.json`, `k8s-views-namespaces.json` |
| `grafana-devops-cli-dashboards` | `devops-cli.json`, `ai-spend.json`, `project-metrics.json`, in `devops/dashboards/` |
| `grafana-service-dashboards` | `devops-roadmap-service.json`, `devops-sre-service.json` |
| `grafana-stack-dashboards` | `ingress-tunnel.json`, `llm-stack.json`, `otel-collector.json`, `prometheus-server.json`, `pyroscope.json`, `nvidia-dcgm.json`, `coredns.json` |
| `grafana-database-dashboards` | `cloudnative-pg.json` |

The service dashboards are generated. `make dashboards` builds each `[[service]]` table of `monitoring/dashboards/services.toml` into `<uid>.json` with the SRE template of `src/devops_cli/grafana/service_dashboard.py` ([DESIGN.md](../docs/DESIGN.md), row "Grafana"): the SLO tiles, the burn rate and the error budget, the golden signals, then the collapsed rows of capacity, logs and profiles. To change one, change its table and run `make dashboards`. Do not edit the JSON. The CI job "Design Tokens" fails when a committed dashboard is not the build.

`cloudnative-pg.json` is the upstream dashboard of [cloudnative-pg/grafana-dashboards](https://github.com/cloudnative-pg/grafana-dashboards) (Apache-2.0) at commit `7dd1bc255b52`, with two changes: its indentation is one space, not two, so its ConfigMap stays under the annotation limit below, and the empty query of its replication lag stat is removed, which `devops grafana dashboards lint` refuses. The operator chart can also write this dashboard, but to `cnpg-system`, where the sidecar does not look, so `monitoring.grafanaDashboard.create` is `false` in `mattermost/cloudnative-pg-values.yaml`. To update the copy, take the file of a newer commit and make the same two changes.

On a cluster Argo CD manages, its `monitoring` Application applies them; the root kustomization leaves them out, so the `base` Application does not own them as well. For the same reason, `devops/kustomization.yaml` does not list `dashboards`: then the `devops` Application takes the ConfigMap `grafana-devops-cli-dashboards` too, and `tests/prometheus/test_k8s_monitoring_dashboards.py` fails. Without Argo CD, `devops k8s deploy-stack --stack infra` (or `all`) applies the `monitoring` kustomization, which lists the namespace's perimeter and `dashboards`, right after the root kustomization creates the `monitoring` namespace, and `teardown-stack` removes them with that namespace. Grafana holds these dashboards as provisioned and refuses to save over them, so change the JSON file and deploy again. To provision another dashboard, add it to a generator entry; each ConfigMap must stay under the 262,144 bytes kubectl's last-applied annotation allows.

The AI spend dashboard (`ai-spend.json`) prices local savings in Prometheus. It multiplies the tokens that a local model ran (`devops_cli_ai_tokens_total{local="true"}`) by its hidden constant `reference_price_usd_per_token`, a PromQL vector of one price for each operation and token type. Each price is genai-prices' price of the default reference model of its operation (`gpt-4o` for chat, `text-embedding-3-small` for embeddings), so every process that sends tokens, and every time range in the retention window, is priced at one reference. A recording rule has samples only from its first evaluation, so the dashboard holds the prices and Prometheus records none. The savings queries also count the series from before the `local` label (#1672) that the gateway served, because the gateway serves only local models, and they count a series without the `operation` label as chat. Remove that mapping when `count(last_over_time(devops_cli_ai_tokens_total{local=""}[30d]))` is empty. `tests/prometheus/test_k8s_monitoring_dashboards.py` fails when a price of the dashboard differs from genai-prices.

The AI spend dashboard counts every caller of the gateway, not only devops-cli. AI Requests in Range and Tokens Processed in Range take a call through the gateway from the gateway's own series (`litellm_proxy_total_requests_metric_total` with a 2xx `status_code`, and `litellm_total_tokens_metric_total`), and add from devops-cli's series only its calls that bypassed the gateway. The Gateway Traffic from Every Caller row shows the gateway's attempts by status, so a 408 or a 5xx is visible, and its requests and tokens by `end_user`. Every caller sends the gateway's one master key, so the gateway tells callers apart by the end-user id that a request names: devops-cli sends its OTel service name (`devops-cli`, `devops-cli-job` or `roadmap-service`) in `x-litellm-end-user-id`, and the gateway config sets `enable_end_user_cost_tracking_prometheus_only` to put it on the `end_user` label. A caller that names no end user, such as Open WebUI, shows as `unnamed`. The coverage stat is devops-cli's own count of its replied gateway calls over the gateway's count.

The stack dashboards chart the cluster workloads and infrastructure services:

| Dashboard | Exporter / Sources | How Prometheus / Loki gets its series |
| :--- | :--- | :--- |
| `devops-roadmap-service.json`, "Roadmap Service: SLO and golden signals" (`devops-roadmap-service`), and `devops-sre-service.json`, "Service: SLO and golden signals" (`devops-sre-service`, with the variables `namespace` and `workload`) | Traefik service metrics (`traefik_service_requests_total`, `traefik_service_request_duration_seconds`) of the Kubernetes Service that has the name of the workload, cAdvisor and kube-state-metrics container series, Loki pod logs (Logs: warnings and errors, Logs: all lines), and Pyroscope flame graphs | Traefik through Alloy's annotation autodiscovery; cAdvisor, the kubelet and kube-state-metrics through Alloy; logs pushed to Loki by Alloy; profiles queried from the Pyroscope data source |
| `ingress-tunnel.json`, "SRE / Ingress & Cloudflare Tunnel" (`devops-ingress-tunnel`) | Traefik ingress metrics (port 9100) and Cloudflare Tunnel metrics (port 2000) | Alloy's annotation autodiscovery (`annotationAutodiscovery` in `monitoring/k8s-monitoring-values.yaml`), through the pods' `prometheus.io/*` annotations; network policy allows monitoring to scrape both ports |
| `llm-stack.json`, "LLM Gateway & GPUs" (`devops-llm-stack`) | LiteLLM's Prometheus callback on the gateway (`/metrics/`), the NVIDIA DCGM exporter on every GPU node, and Qdrant's `/metrics` on port 6333 | The `llm-gateway` ServiceMonitor (`llm/gateway/servicemonitor.yaml`), the `dcgm-exporter` integration (`integrations` in `monitoring/k8s-monitoring-values.yaml`), and the `qdrant` ServiceMonitor (`metrics.serviceMonitor` in `llm/values-qdrant.yaml`, authenticating with the `qdrant-api-key` Secret), run by Alloy, which remote-writes to the server |
| `otel-collector.json`, "OpenTelemetry Collector" (`devops-otel-traces`) | The collector's own telemetry on port 8888 | The server's `kubernetes-pods` job, which keeps only namespace `otel`, through the `prometheus.io/scrape` and `prometheus.io/port` pod annotations in `otel/values.yaml`; not through Alloy, whose annotation autodiscovery skips `otel`, so the collector's export failures stay visible when Alloy is what fails |
| `prometheus-server.json`, "Prometheus Server" (`devops-prometheus-server`) | The Prometheus server's own `/metrics`, and `up` for every target | The server's `prometheus` job, which scrapes itself (`scrapeConfigs.prometheus` in `monitoring/prometheus-values.yaml`) |
| `pyroscope.json`, "Continuous Profiling / Pyroscope Flamegraphs" (`devops-pyroscope`) | Grafana Pyroscope continuous profiling (CPU, memory, goroutines) | Continuous profiles collected by k8s-monitoring's `profiling` feature (`alloy-profiles` DaemonSet, eBPF `targetingScheme: all` and `pprof`, in `monitoring/k8s-monitoring-values.yaml`) and sent to `destinations.localPyroscope` (#1134) |
| `coredns.json`, "CoreDNS" (`devops-coredns`) | CoreDNS metrics on port 9153 (`coredns_dns_*`, `coredns_cache_*`, `coredns_proxy_*`) | Alloy's `clusterMetrics.kubeDNS` job (`job="integrations/kubernetes/kube-dns"` in `monitoring/k8s-monitoring-values.yaml`) (#822) |
| `cloudnative-pg.json`, "CloudNativePG" (`cloudnative-pg`) | The CloudNativePG metrics exporter of each instance on port 9187 (`cnpg_*`), and the operator's `controller_runtime_*` | The PodMonitors `llm-gateway-db` (`llm/gateway-db.yaml`) and `mattermost-db` (`mattermost/podmonitor.yaml`), and the operator's chart PodMonitor (`monitoring.podMonitorEnabled` in `mattermost/cloudnative-pg-values.yaml`), run by Alloy. Select the database with the `namespace` and `cluster` variables (#4994) |

```bash
devops grafana dashboards lint  # both folders; also catches a uid two files share
devops grafana dashboards sync  # posts every file of both folders
```
`sync` exits 1 if any dashboard failed. It reports the provisioned dashboards as skipped, not failed.

`tests/commands/k8s/test_stack_dashboards.py` checks every query in `llm-stack.json`, `otel-collector.json`, `prometheus-server.json`, `coredns.json`, `ingress-tunnel.json`, `k8s-views-global.json`, `k8s-views-namespaces.json` and `k8s-views-nodes.json` against captures of these exporters in `tests/fixtures/metrics/` (filtered by `tests/fixtures/k8s_monitoring/cluster_metrics/` and `includeMetrics` for cAdvisor, kube-state-metrics and the kubelet): each series it selects, each label it matches or groups by, and the scrape in the table. No query falls back to a constant such as `or vector(0)`, so a panel without data reads "No data" rather than zero, and a panel drawn against a limit extends its axis to that limit. The gateway's failure panel, Qdrant's REST request rate and latency panels, and the collector's span export failures (`noValue: "none recorded"`) stay empty until the first such event. The gateway's cooldown and fallback stats count the events in the time range and show "none recorded" before the first one.

## Grafana Image Renderer

The `grafana` chart runs the [Grafana Image Renderer](https://github.com/grafana/grafana-image-renderer) (Apache-2.0) as Deployment and Service `grafana-image-renderer` in namespace `monitoring` (`imageRenderer` in `monitoring/grafana-values.yaml`). It gives a PNG of a panel or a dashboard to the render API of Grafana (`/render/d-solo/...` and `/render/d/...`), to the Grafana MCP tool `get_panel_image`, and to alert notifications.

- Grafana calls the renderer at `http://grafana-image-renderer.monitoring:8081/render` (`GF_RENDERING_SERVER_URL`), and the renderer opens the page at `http://grafana.monitoring:80/` (`GF_RENDERING_CALLBACK_URL`). The chart sets both URLs from the Service names. No Ingress routes to the renderer. The NetworkPolicy of the chart, `grafana-image-renderer-ingress`, admits Grafana to port 8081, and `monitoring-default-perimeter` admits the other pods of the namespace.
- Each request carries the token of Secret `monitoring/grafana-image-renderer` ([Cluster Secrets](#cluster-secrets)). The chart can make this Secret, but its template makes a new random token at each `helm template`, and Argo CD renders the chart with `helm template`. So each new revision would change the token while the pods keep the old one.
- The image has a release tag, and the helm-values manager of Renovate reads it.
- The renderer requests `100m` of CPU and `512Mi` of memory, and its limits are `2` CPUs and `1536Mi`. `GOMEMLIMIT` is `192MiB`: the renderer documents ask for a value below the limit, 1 GiB for each 8 GiB of limit, because Chromium uses the remaining memory. A local measurement with v5.12.11 and Grafana 13.3.1 under these limits: 10 panel renders in a row used 370 MiB at most (24 % of the limit), and 3 renders at one time and one render of the 55 panels of `devops-cli-telemetry` used 897 MiB at most (58 %). One panel render took 4 s to 7 s.

After a change to a dashboard or to the renderer, render a panel in the light and the dark theme. Grafana lets an anonymous Viewer render:

```bash
kubectl -n monitoring port-forward svc/grafana 3000:80
for theme in light dark; do
  curl -s -o "panel-$theme.png" -w "%{http_code} %{content_type} $theme\n" \
    "http://localhost:3000/render/d-solo/devops-cli-telemetry/x?orgId=1&panelId=11&width=1000&height=500&from=now-6h&to=now&theme=$theme"
done
```

Each line shows `200 image/png`. Open the two files, and make sure that the text and the series are clear on each background. The MCP tool `get_panel_image` does the same check with the dashboard UID, the panel ID and the theme. After 10 renders in a row, the working set of the renderer stays below 80 % of its memory limit:

```promql
max_over_time(container_memory_working_set_bytes{namespace="monitoring", container="grafana-image-renderer"}[30m]) / (1536 * 1024 * 1024)
```

## Log and Metric Retention

Logs and metrics are kept for 30 days:

| Store | Kept for | Deleted by | Volume |
| :--- | :--- | :--- | :--- |
| Loki (`logging/loki-values.yaml`) | `limits_config.retention_period: 720h` | The compactor, which applies retention only with `compactor.retention_enabled`, every 11 minutes | `storage-loki-0`, 20Gi |
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

`tests/core/test_k8s_local_path_placement.py` fails when a pod that mounts a claim has no such affinity, in a chart values file or in a manifest under `k8s/`. It reads a CloudNativePG `Cluster` that sets `spec.storage` as a pod on a claim, and it takes the affinity of that pod from `spec.affinity`: the operator makes a claim from `spec.storage` and applies `spec.affinity` to the database pods. It also fails when an Argo CD Application installs a chart, or pins a chart version, that the claim table `CHART_CLAIMS` does not name, because each chart keeps its claims and its affinity at different values and a chart release can move them. A person who bumps a chart reads the claim values of the new version again and changes the key of its entry.

The table `_CONTROL_PLANE_CLAIM_EXEMPTIONS` of the test names each pod that may stay on the control-plane node, with its reason. It holds two entries, and each entry goes when its item moves the volume:

| Key | Reason | Item |
| :--- | :--- | :--- |
| `k8s/mattermost/database.yaml:Cluster/mattermost-db` | The claim of the database is on the control-plane node. The pod stays Pending with the affinity. | #3803 moves the volume and then adds the affinity. |
| `k8s/llm/gateway-db.yaml:Cluster/llm-gateway-db` | The claim of the gateway database is on the control-plane node. | #3782 moves the volume and then adds the affinity. |

A pod that must stay on the control-plane node gets an entry with its reason. An example is a pod whose volume is still on the control-plane node. With the affinity, that pod cannot start. Move the volume as below. Then remove its entry and add the affinity to its values in one pull request. The move of the Mattermost database needs a backup first (#3803).

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

1. It pauses automated sync from the top down: the root Applications of the setting `argocd.root_applications` (`bootstrap`, `cluster`), then each Application that tracks the claim or the workloads that mount it (Pausing an Application, below). If it did not, self-heal would start the workload again during the copy.
2. It makes the claim `<claim>-move`, with the size and the class of the old claim, and the pod `<claim>-dst` on the target node. local-path binds the new volume on that node.
3. It scales the workloads that mount the claim to zero. It finds them from the volumes of the pod specs, not from labels. Then it starts the pod `<claim>-src`, which mounts the old claim read-only. Its volume keeps it on the old node, so one pod cannot mount the two claims.
4. It copies through the API server with GNU tar in `debian:trixie-slim`, which keeps the owners, the modes and the sparse files. The source keeps its stdout open until the destination has ended, because the end of that stdout loses the data that still waits on the path to a slower destination. The extract ends at the end-of-archive marker, and a named pipe from the stdout of the destination to the stdin of the source then ends the source. When the exec stream stops (`connection reset by peer`), it empties the destination and copies one more time.
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

- Qdrant: chart 1.20.0 has no value for the field. qdrant/qdrant-helm#506 asks for the value. When a chart release adds it, set the value and remove the exception in one pull request.

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

## Service levels

The [SRE guideline](../docs/guidelines/sre.md) sets how a project runs its services, and the [production readiness guideline](../docs/guidelines/production-readiness.md) sets the rows that each service meets. [The guideline index](../docs/guidelines/index.md) lists each guideline. This section holds only the decisions of this cluster. [Tracker #5541](https://github.com/dan-petty/devops-cli/issues/5541) holds the open SRE and production readiness gaps of this cluster, so this section holds no gap row. The service dashboards, `devops prometheus rules` and `devops roadmap review run` give the measured values.

[`catalog.toml`](catalog.toml) is the catalog data: the Applications, the tier, the data class and the dependencies of each service. A service with a Homepage UI takes its description from the `gethomepage.dev/description` annotation of that UI (#4600), so its entry holds no description. A new service adds its entry in the pull request that adds the service (rule SRE1).

**SLOs.** The window of each SLO is 28 days. SLO 5 is the default of the service dashboards (`monitoring/dashboards/services.toml`) until the owner sets another target. The rows stay here until the Sloth specs of #4709 hold them.

| SLO | Service | SLI: good events / valid events | Objective | Error budget |
| :--- | :--- | :--- | ---: | :--- |
| 1 | Roadmap Service | Row runs with `result="success"` / row runs with `result` `success` or `error`, for each row and repository (`devops_cli_service_jobs_total`) | 99.0 % | 1 % of the runs of each row and repository |
| 2 | Runner Jobs | Runner Jobs (`devops-cli-runner-*`) that end in under 3,600 s / runner Jobs that end | 90.0 % | 10 % of the Jobs |
| 3 | LLM gateway | Gateway requests with no failure / gateway requests (`litellm_proxy_*_requests_metric_total`) | 99.5 % | 0.5 % of the requests |
| 4 | LLM gateway | Gateway requests that end in under 60 s / gateway requests (`litellm_request_total_latency_metric_bucket`) | 95.0 % | 5 % of the requests |
| 5 | Roadmap Service | Ingress requests with no 5xx answer / ingress requests (`traefik_service_requests_total`) | 99.9 % | 0.1 % of the requests |

SLO 2 counts only the runner Jobs that end. kube-state-metrics shows a Job only while the Job object exists, and a failed Job has no completion time.

**Owner values.**

- **Incident trigger 1.** A burn rate of 14.4x or more for 1 hour or more, with at least 20 events. 14.4x is the 1-hour page rate of a 30-day window. The default of the guideline for 28 days is 13.44x. The value stays here until the settings of the incident job (#5477) hold it.
- **Pages.** One owner holds one 12-hour shift each day, so the page budget is 2 pages a day.

**Accepted exceptions.**

- Git does not hold the Secrets ([Cluster Secrets](#cluster-secrets)) or ConfigMap `devops-cli-config` ([Homelab Values at Deploy Time](#homelab-values-at-deploy-time)).
- The sweep and its Valkey keep state on `local-path` volumes, which stop with their node ([ADR 0021](../docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md)). The off-node backup of owned state limits the loss.
- The roadmap Service runs one pod with `Recreate` ([Roadmap service](../docs/CLUSTER.md#roadmap-service)).

**Runbooks for the whole system:** the [stop switch](../docs/CLUSTER.md#stop-switch), the [planned maintenance](#planned-maintenance), the [recovery of Argo CD](#recovery) and the [failure recovery matrix](../docs/ROUTINE_TASKS.md#4-failure-recovery--troubleshooting-matrix).

## Alerting

The [SRE guideline](../docs/guidelines/sre.md) sets the method of the SLOs, the burn-rate alerts, the page and ticket targets and the incident steps. [Service levels](#service-levels) holds the decisions of this cluster. This section holds the rules and the receiver.

Alertmanager runs from the prometheus chart (`alertmanager` in `monitoring/prometheus-values.yaml`), and Grafana reads it as the `Alertmanager` datasource. The environment rules are in the same file, under `serverFiles.alerting_rules.yml`. The product rules, the groups that select a `devops_cli_*` series, are in `devops/monitoring/prometheus-rules-values.yaml`, under `serverFiles.devops_cli_alerting_rules.yml` (#5292). The `prometheus` Application gives the chart this file as its second values file, and `devops k8s deploy-stack` gives `helm upgrade` both files. The chart writes each key of `serverFiles` to the ConfigMap `prometheus-server`, and `serverFiles.prometheus.yml.rule_files` of the environment values names the 4 rule files of the chart and the product file. `tests/prometheus/test_k8s_monitoring_alerting.py` pins the rules and checks that each selects only series that a scrape or the OpenTelemetry collector in `k8s/` serves. No rule watches the controller manager, scheduler or proxy: k3s runs them inside its server process, so nothing scrapes them and such a rule would fire on the missing target.

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
| `DevopsCliMetricStreamsShareSeries` | Prometheus holds two `target_info` series with the same `job` and `instance`, so two metric streams write one series and its totals are wrong (#4697, #5338). The rule sees only writers that send at the same time: after a pod change, the 15 minute lookback holds the old series for less than 30 minutes. Compare the labels of the two series (`target_info{job="<job>", instance="<instance>"}`). A different `telemetry_sdk_*` label means that a second SDK sends with the same `service.name` and `service.instance.id`. Any other label that differs means that a devops-cli build with another metric Resource runs next to the current build: stop or update the old process (global install, long-lived MCP server, worktree on an old branch, Job from an old image). A `host_name` label means that the metrics did not go through `transform/metric_resource` of the collector (`otel/values.yaml`). The alert clears 15 minutes after the old writer stops | 30m | warning |
| `ArgoCdApplicationOutOfSync` | An Argo CD Application's `sync_status` is not `Synced` | 15m | warning |
| `ArgoCdApplicationUnhealthy` | An Argo CD Application's `health_status` is neither `Healthy` nor `Progressing` | 15m | warning |
| `ArgoCdAutoSyncDisabled` | An Argo CD Application's `autosync_enabled` is `false` | 15m | warning |
| `ArgoCdSyncOperationStuck` | An Argo CD Application has a sync operation running | 1h | warning |
| `IngressServesPlaceholderHost` | An Ingress routes a host under the placeholder domain of git (`kube_ingress_path`), so Traefik returns 404 for its real host; see Homelab Values at Deploy Time | 5m | critical |
| `CloudflareTunnelDegraded` | Total Cloudflare Tunnel HA connections across `cloudflared` replicas are under 2 | 5m | warning |
| `CoreDnsServfailResponses` | Over 5% of CoreDNS responses return `SERVFAIL` | 5m | warning |
| `ValkeyCacheErrors` | A Valkey exporter reports `redis_up == 0` or rejected client connections | 5m | warning |
| `ValkeyMemoryNearBound` | A Valkey with the policy `noeviction` and a bound keeps its data above 80% of its `maxmemory`; at the bound it refuses each write | 10m | warning |
| `GatewayDatabaseDown` | The CloudNativePG exporter of the gateway database (`llm/llm-gateway-db`) has no connection to PostgreSQL (`cnpg_collector_up` is 0), or Prometheus has no series from it. The gateway then refuses each virtual key (#4994). Run `kubectl get cluster -n llm llm-gateway-db` and read the log of pod `llm-gateway-db-1` | 5m | warning |
| `GatewayDatabaseConnectionsNearMax` | The client connections of the gateway database are above 80% of `max_connections`; at the limit PostgreSQL refuses each new connection. Find the client on the Connections panels of the CloudNativePG dashboard | 10m | warning |
| `GatewayDatabaseNearClaim` | The databases and the WAL of the gateway database are above 80% of its claim (5 GiB). local-path does not enforce the claim, so the data can fill the root disk of the node. Find what grows on the CloudNativePG dashboard; the spend logs keep 30 days (`maximum_spend_logs_retention_period` in `llm/gateway/config.yaml`) | 15m | warning |
| `RagIngestBehind` | No RAG ingestion run succeeded for repository `{{ $labels.repo }}` in the last two schedule periods (360s) | — | warning |
| `ResearchCriticalFindings` | The last `devops research sweep` of the last 7 days found a critical advisory that affects a pin of the project (#3899). The sweep sets zero for a severity with no finding, so a clean sweep ends the alert. A sweep with a lookup that got no answer sets no value. Read the candidates that the sweep filed, or run `devops research advisories`, and update the pin. Run the sweep again | — | critical |
| `ClaudeSpendDailyHigh` | The calls of `claude-sonnet-5-5` cost more than 15 USD in the last 24 hours (#4222). The rule sums the 24 hour increase of `devops_cli_ai_spend_usd_total` of every job, and keeps the spend of a counter that reset. The highest normal day is 5.59 USD, and a failed stage burst costs about 21 USD per hour. Read the cost page of the AI spend dashboard, find the caller by the `end_user` label, and stop the job. Set the threshold again with the data of a month | — | warning |
| `HostedSpendDailyHigh` | The calls of all hosted models cost more than 25 USD in the last 24 hours (#4222). A local request adds 0 to `devops_cli_ai_spend_usd_total`, so the sum is the hosted spend. Read the cost page of the AI spend dashboard, find the caller by the `end_user` label, and stop the job | — | warning |
| `RoadmapServiceIdentityRefused`, `RoadmapServiceGitHubThrottled` | GitHub refused the identity of the roadmap Service, or throttled its requests; see [docs/CLUSTER.md](../docs/CLUSTER.md#alerts), Roadmap service, Alerts | — | critical |
| `RoadmapServiceJobsFailing` | All jobs of one row of a repository failed in 1 hour | 30m | warning |
| `RoadmapServiceLaneStalled`, `RoadmapServiceRestarted`, `RoadmapServiceMemoryNearLimit`, `RoadmapServiceUnavailable`, `RoadmapServiceGitHubRequestsHigh`, `RoadmapServiceModelRequestsHigh`, `RoadmapServiceStateUnkept`, `RoadmapServiceRowSuspended` | The roadmap Service stalls, its pod restarts, uses almost all of its memory limit or is unavailable, its GitHub or model requests in an hour are high, it could not write a state record, or a row stays suspended; see [docs/CLUSTER.md](../docs/CLUSTER.md#alerts), Roadmap service, Alerts | 0–15m | warning |
| `RoadmapServiceWebhooksRejected` | The webhook route of the roadmap Service rejected more than 20 deliveries in 15 minutes; see [docs/CLUSTER.md](../docs/CLUSTER.md#alerts), Roadmap service, Alerts | — | warning |
| `ClusterMetricsMissing` | `kube_node_status_condition` is absent, so the node rules cannot fire | 10m | critical |
| `PrometheusConfigReloadFailed`, `PrometheusRuleEvaluationFailures`, `PrometheusNotConnectedToAlertmanager`, `PrometheusDroppingAlerts`, `PrometheusCompactionsFailing` | Prometheus's own health | 0–15m | warning |
| `AlertmanagerConfigReloadFailed`, `AlertmanagerNotificationsFailing` | Alertmanager's own health; the second only once the alertmanager-mattermost Secret exists | 10m, 15m | warning |

Retention, volume sizes and what `LogOrMetricVolumeDiskLow` and `PrometheusNearRetentionSizeCap` watch are in Log and Metric Retention, above.

The local-path volumes are host directories. They report no kubelet volume stats and do not enforce their claim's size, so the host filesystem under them is what fills. `HostFilesystemSpaceLow` watches every filesystem of every node; `LogOrMetricVolumeDiskLow` watches the same 10% on the root filesystem of the node holding Loki's and Prometheus's claims and names the claim at risk, so on that node both fire. For Prometheus, `PrometheusNearRetentionSizeCap` warns before its size cap deletes anything, `PrometheusSizeLimitCutHistory` once it has, and `PrometheusStorageNearClaim` if the data outgrows the claim with no cap holding it.

The GPU power budget is one number for the whole site, from the GPUs' draw before a breaker trip on the circuit every node shared. Once the power layout is settled, it should become one budget per circuit.

### Free space of the root disk after a prune

The prune of the model store (`devops k8s ollama prune`) frees the root disk of a node. This query shows if the free space of that disk stays above 25% for the 7 days after the prune. Run it in Grafana, in the Explore view of the `Prometheus` datasource, or in the expression browser of the Prometheus server:

```promql
min_over_time(node_filesystem_avail_bytes{mountpoint="/", instance="<node>"}[7d]) / max_over_time(node_filesystem_size_bytes{mountpoint="/", instance="<node>"}[7d]) < 0.25
```

Set `instance` to the node that runs the pruned store. An empty result means that the node stayed above 25% free for the 7 days. A result names the node that fell below 25% free. Prometheus keeps 30 days of samples (`server.retention` in `monitoring/prometheus-values.yaml`), so the `[7d]` window is readable. `LocalPathNodeDiskHigh` is no proof of this bound: it fires at 85% used, 10 points above 75%, and only after 15 minutes (Alerting, above).

A node keeps the models of the gateway targets that its tier serves (GPU Placement: Ollama tiers, the keep table). Check the models that the node keeps with `kubectl -n llm exec <tier-pod> -- ollama list`, in a pod of that tier. Compare the list with the row of the table for the targets of the tier.

Post the query and its result as a comment on #3654. The next prune then has the method and the measurement together. #4001 holds the 7-day measurement and that comment.

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

Every Secret the stacks read comes from the workstation's OS keyring. `devops k8s push-secrets` writes them (workstation keyring → cluster, the reverse of `devops k8s sync-secrets`), and `devops k8s deploy-stack` runs the same push right after the namespaces, before any manifest or Helm release. One table in `src/devops_cli/k8s/cluster_secrets.py` lists them, and a test fails on any Secret a manifest or values file here references without a row. Add a new secret as a row with a generator, so that `push-secrets` makes its value: an agent writes no secret value. Argo CD applies a manifest when it merges, and a pod that reads a missing Secret does not start. So a person runs `uv run devops k8s push-secrets --only <namespace>/<name>` from the branch of the pull request before the merge of the manifest that reads the new Secret. Make the reference `optional: true` when the pod can start without it. Check the pods after the merge. The table:

| Secret | Key | Source | Required | When the keyring has no value | Stack | Restarted when it changes |
|---|---|---|---|---|---|---|
| `llm/llm-gateway-secrets` | `master-key` | keyring `llm_gateway_master_key` | yes | adopt the live value; else generate `sk-` + 48 hex | llm | `deployment/llm-gateway` |
| `llm/llm-gateway-secrets` | `gemini-api-key` | keyring `gemini_api_key` | no | adopt the live value; else skip with a warning | llm | `deployment/llm-gateway` |
| `llm/llm-gateway-secrets` | `anthropic-api-key` | keyring `anthropic_api_key` | no | adopt the live value; else skip with a warning | llm | `deployment/llm-gateway` |
| `llm/llm-gateway-secrets` | `openrouter-api-key` | keyring `openrouter_api_key` | no | adopt the live value; else skip with a warning | llm | `deployment/llm-gateway` |
| `llm/qdrant-api-key` | `api-key` | keyring `qdrant_api_key` | yes | adopt the live value; else generate `token_urlsafe(32)` | llm | `statefulset/qdrant`, `statefulset/open-webui` |
| `llm/valkey-runs-auth` | `password` | keyring `runs_index_password` | yes | adopt the live value; else generate 64 hex | llm | `deployment/valkey-runs` |
| `llm/valkey-auth` | `VALKEY_PASSWORD` | keyring `valkey_password` | yes | adopt the live value; else generate 64 hex | llm | `deployment/valkey`, `statefulset/open-webui` |
| `llm/valkey-devops-auth` | `password` | keyring `valkey_devops_password` | yes | adopt the live value; else generate 64 hex | llm | `deployment/valkey-devops` |
| `cloudflared/cloudflared-token` | `token` | keyring `cloudflare_tunnel_token` | no | adopt the live value; else skip with a warning | base | `deployment/cloudflared` |
| `devops/crawl4ai` | `CRAWL4AI_API_TOKEN` | keyring `crawl4ai_api_token` | yes | adopt the live value; else generate `token_urlsafe(32)` | devops | `deployment/crawl4ai` |
| `devops/searxng` | `SEARXNG_SECRET` | keyring `searxng_secret_key` | yes | adopt the live value; else generate 64 hex | devops | `deployment/searxng` |
| `devops/mcp-server` | `DEVOPS_CLI_MCP_TOKEN` | keyring `mcp_token` | yes | adopt the live value; else generate `token_urlsafe(32)` | devops | `deployment/mcp-server` |
| `devops/devops-cli` | `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` | keyring `service_github_app_private_key` | yes | adopt the live value; else fail | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_AI_API_KEY` | keyring `llm_gateway_master_key` | yes | adopt from `llm/llm-gateway-secrets master-key`; else fail | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS` | keyring `service_webhook_secrets` | no | adopt the live value; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_FIRECRAWL_API_KEY` | keyring `firecrawl_api_key` | no | adopt the live value; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_VALKEY_PASSWORD` | keyring `valkey_devops_password` | yes | adopt from `llm/valkey-devops-auth password`; else generate 64 hex | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_MATTERMOST_COMMAND_TOKEN` | keyring `mattermost_command_token` | no | adopt the live value; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_CRAWL4AI_API_TOKEN` | keyring `crawl4ai_api_token` | no | adopt from `devops/crawl4ai CRAWL4AI_API_TOKEN`; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_MCP_STAGE_TOKEN` | keyring `mcp_token` | no | adopt from `devops/mcp-server DEVOPS_CLI_MCP_TOKEN`; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_MCP_IMPLEMENT_TOKEN` | keyring `mcp_token` | no | adopt from `devops/mcp-server DEVOPS_CLI_MCP_TOKEN`; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/qdrant-api-key` | `api-key` | keyring `qdrant_api_key` | yes | adopt from `llm/qdrant-api-key api-key`; else generate `token_urlsafe(32)` | devops | none |
| `monitoring/grafana-admin` | `admin-user` | literal | yes | fail | infra | `deployment/grafana` |
| `monitoring/grafana-admin` | `admin-password` | keyring `grafana_password` | yes | adopt from `monitoring/grafana admin-password`; else generate `token_urlsafe(32)` | infra | `deployment/grafana` |
| `monitoring/grafana-image-renderer` | `token` | keyring `grafana_renderer_token` | yes | adopt the live value; else generate `token_urlsafe(32)` | infra | `deployment/grafana`, `deployment/grafana-image-renderer` |
| `monitoring/alertmanager-mattermost` | `url` | derived from keyring mattermost_alerts_hook | no | skip with a warning | infra | none |
| `argocd/argocd-notifications-secret` | `github-appID` | setting argocd.github_app_id | yes | fail | infra | none |
| `argocd/argocd-notifications-secret` | `github-installationID` | setting argocd.github_app_installation_id | yes | fail | infra | none |
| `argocd/argocd-notifications-secret` | `github-privateKey` | keyring `argocd_github_app_private_key` | yes | adopt the live value; else fail | infra | none |
| `argocd/argocd-notifications-secret` | `mattermost-deploys-url` | derived from keyring mattermost_deploys_hook | no | skip with a warning | infra | none |
| `gitea/gitea-admin` | `username` | literal | yes | fail | gitea | `deployment/gitea` |
| `gitea/gitea-admin` | `password` | keyring `gitea_admin_password` | yes | adopt the live value; else fail | gitea | `deployment/gitea` |
| `mattermost/mattermost-db` | `username` | literal | yes | fail | chat | none |
| `mattermost/mattermost-db` | `password` | keyring `mattermost_db_password` | yes | adopt from `mattermost/mattermost-db password`; else generate `token_urlsafe(32)` | chat | none |
| `mattermost/mattermost-db` | `DB_CONNECTION_STRING` | derived from literal, keyring mattermost_db_password | yes | fail | chat | none |

- A Secret that a CloudNativePG `Cluster` without `bootstrap.initdb.secret` creates, such as `llm/llm-gateway-db-app`, has no row. The operator generates its password when it creates the database, and the Deployment reads it with `secretKeyRef`.
- The keyring must be unlocked (`devops devcontainer unlock-keyring`); a locked or missing keyring stops the push before anything is read or written, and stops deploy-stack before it applies anything.
- A value the keyring lacks but the cluster holds is adopted into the keyring, so a first push changes nothing live. Only values nobody types are generated, and each is stored in the keyring before it is pushed.
- Typed values are stored at a hidden prompt: `devops config set cloudflare.tunnel_token` or `devops config set gitea.admin_password`.
- A derived entry is built from other values of the same push, such as a connection string from a user and a password. The push resolves every other entry first, then fills each field of the entry's template with the value of its input, quoted with `urllib.parse.quote(..., safe="")`. It never adopts, generates or stores a derived value, and a live value that differs needs `--rotate`. `--plan` names the source as `derived from` and its inputs, and `--dry-run` shows a placeholder.
- A row may name its Secret type, such as `kubernetes.io/basic-auth`. The default is `Opaque`. Kubernetes cannot change the type of an existing Secret, so a row names its type before its first push.
- `CRAWL4AI_API_TOKEN` is the bearer token of Crawl4AI, which refuses to listen beyond loopback without it. One keyring value, `crawl4ai_api_token`, feeds Secret `devops/crawl4ai` and the key `DEVOPS_CLI_CRAWL4AI_API_TOKEN` of Secret `devops/devops-cli`, so the client and the service always hold the same token. A person runs `devops k8s push-secrets --only devops/crawl4ai --only devops/devops-cli` to create or change them; no other command writes them.
- `DEVOPS_CLI_MCP_TOKEN` is the bearer token of the MCP server, which refuses to start without it (`mcp.token`, SECURITY.md, MCP Server on the Network). The server accepts one token, so one keyring value, `mcp_token`, feeds Secret `devops/mcp-server` (read by Deployment `mcp-server` with `secretKeyRef`) and the keys `DEVOPS_CLI_MCP_STAGE_TOKEN` and `DEVOPS_CLI_MCP_IMPLEMENT_TOKEN` of Secret `devops/devops-cli` (the tokens of the stage and implement clients, `mcp.stage_token` and `mcp.implement_token`). A person runs `devops k8s push-secrets --only devops/mcp-server --only devops/devops-cli` to create or change them; a change restarts `deployment/mcp-server` and `deployment/roadmap-service`. The clients stay off until a person sets `roadmap.stage.mcp` or `roadmap.implement.mcp` in the ConfigMap, and the `roadmap.mcp.url` setting names the server. Two NetworkPolicies let the clients reach the server (`mcp-server-ingress` and `mcp-server-clients`, TCP 8001 only, to the pods of the server only). Both select the clients by the label `app.kubernetes.io/name`: `roadmap-service`, and `devops-cli-job`, the label that `build_job` sets on every Job pod. A pod with the label of the CronJob template, `devops-cli-runner`, never runs, so no policy names it (#4355).
- `SEARXNG_SECRET` is the server secret of SearXNG, which refuses to start with its default key. Its keyring value, `searxng_secret_key`, is no managed credential: no setting reads it, and only the pod does. A person runs `devops k8s push-secrets --only devops/searxng` to create or change it, and a change restarts `deployment/searxng`.
- `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` is the private key of GitHub App `devops-cli-service`, which the roadmap Service and the cluster Jobs act as ([ADR 0015](../docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md)). Store it with `devops config set service.github_app.private_key --from-file <key.pem>`. A pod whose environment holds the key acts as the App: it mints an installation token, mints a new one before the token expires, and gives the current token to each gh and git child as GH_TOKEN. A workstation keeps the key only in the keyring, so a workstation run keeps the gh login of its person.
- `argocd/argocd-notifications-secret` holds the GitHub App that Argo CD's GitHub notifier acts as, and the webhook URL for Mattermost deploys. Its `service.github` refers to the keys as `$github-appID`, `$github-installationID` and `$github-privateKey`, and `service.webhook.mattermost` refers to `$mattermost-deploys-url`. Store the values with `devops config set argocd.github_app_id <id>`, `devops config set argocd.github_app_installation_id <id>`, `devops config set argocd.github_app_private_key --from-file <key.pem>`, and `devops config set mattermost.deploys_hook`, then run `devops k8s push-secrets --only argocd/argocd-notifications-secret`. The Argo CD values set `notifications.secret.create: false`, so the chart never creates a Secret of the same name, and the `homelab` project ignores the pushed Secret as an orphan.
- `monitoring/alertmanager-mattermost` holds the incoming webhook URL that Alertmanager uses to post critical and warning alerts to Mattermost. Store the webhook token with `devops config set mattermost.alerts_hook`, then push with `devops k8s push-secrets --only monitoring/alertmanager-mattermost`. The `homelab` project ignores the Secret as an orphan.
- `monitoring/grafana-image-renderer` holds the token that Grafana sends to its image renderer ([Grafana Image Renderer](#grafana-image-renderer)). Its keyring value, `grafana_renderer_token`, is no managed credential: no setting reads it, and only the Grafana pod and the renderer pod do. Neither pod starts without the Secret. `deploy-stack` pushes it before the Helm releases. On a cluster that Argo CD manages, a person runs `devops k8s push-secrets --only monitoring/grafana-image-renderer` before the first sync of values that enable the renderer. A change restarts `deployment/grafana` and `deployment/grafana-image-renderer`. The `homelab` project ignores the Secret as an orphan.
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

## gVisor Runtime

`runtimeclass-gvisor.yaml` declares RuntimeClass `gvisor` with handler `runsc`. The root kustomization lists it, so Argo CD's `base` Application applies it on the homelab, and `devops k8s deploy-stack` applies it on a cluster with no Argo CD. gVisor (`runsc`) is a user-space kernel. A pod of this class runs on that kernel and reaches the host kernel only through a small, filtered set of system calls of the gVisor Sentry, so most defects of the host kernel are out of its reach ([ADR 0018](../docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md)). The class is for pods that run code that a model writes, such as the runner Jobs, the run Job of the planner and the in-cluster browser. No workload uses the class yet.

- **Node label.** The class sets `scheduling.nodeSelector` to `node-restriction.kubernetes.io/gvisor: "true"`. Admission adds this selector to each pod of the class, so such a pod runs only on a node with the label. When no node has the label, the pod stays Pending. It never runs on a node without `runsc`. The NodeRestriction admission plugin of k3s stops a kubelet from setting a label under `node-restriction.kubernetes.io/`, so only an admin sets it, and a node cannot label itself to attract the pods of the class.
- **Node setup.** k3s finds some runtimes on a node by itself, but not `runsc`. The infra repository installs a pinned `runsc` on a node and adds the `runsc` runtime to the containerd config template of k3s. Then it sets the node label. The label comes last, so a node gets a pod of the class only after containerd has `runsc` there. The infra repository does not start a sandbox, so the first pod of the class on a node is a canary.
- **Use.** A pod sets `runtimeClassName: gvisor`. In such a pod, `uname -r` prints the kernel version that gVisor reports, and not the kernel of the host. With the pinned `runsc` (release 20261109.0), it prints `4.19.0-gvisor`. An older `runsc` printed `4.4.0`.
- **Seccomp.** Under `runsc`, the node does not load the seccomp profile of the pod (`RuntimeDefault`) into the sandbox, because the `runsc` option `oci-seccomp` is off. The seccomp filter of the gVisor Sentry on the host applies in its place. So the seccomp control of ADR 0018 has a different meaning in a pod of this class.
- **Limits.** The CPU and memory limits of a pod hold under `runsc`. The measurement of `runc` against `runsc` on the labelled node ([#5434 result](https://github.com/dan-petty/devops-cli/issues/5434#issuecomment-6860621985)) shows this. A CPU limit of `500m` makes a CPU task 2.6 times slower, and an allocation past a memory limit of 224 MiB ends in `OOMKilled`. So the limit defect of [gVisor issue #13777](https://github.com/google/gvisor/issues/13777) did not occur. Under `runsc`, CPU work has no overhead, file work is 1.44 times slower, headless Chromium works, and a pod starts as fast as under `runc`.
- **Overhead.** A pod of the class uses 15.1 MiB more memory than under `runc`, for the Sentry and the gofer. So the class sets `overhead.podFixed` to memory `16Mi`. The measurement found no CPU overhead, so the class sets no CPU overhead. Admission adds the overhead to each pod of the class. The scheduler, the kubelet and a ResourceQuota count it with the resources of the containers. The measurement ran on an agent node. The control-plane node has no `runsc`, so a pod of the class does not run there.

## Agent sessions

`k8s/agents/` defines read-only identity and boundaries for autonomous AI agent sessions running against the cluster:

- **Namespace `agents`**: Enforces `restricted` Pod Security Standards across `enforce`, `warn`, and `audit` levels.
- **ServiceAccount `devops-agent`**: Created in namespace `agents` with `automountServiceAccountToken: false` to ensure agents do not automatically mount cluster credentials.
- **ClusterRoleBinding `devops-agent-view`**: Binds `devops-agent` exclusively to the built-in read-only `view` ClusterRole. No other RBAC manifests grant mutating or secret-reading permissions to this identity.
- **GitOps Management**: Managed by Application `agents` (`k8s/argocd/apps/agents.yaml`) under the `homelab` project, with AppProject orphan-ignore rules configured for transient session secrets (`agent-grant-*`).

## Argo Workflows

`k8s/argo-workflows/` installs the [Argo Workflows](https://argo-workflows.readthedocs.io/) controller in its own namespace, `argo-workflows`, with WorkflowTemplate `devops-cli-version`, which measured what a Workflow costs. [ADR 0008](../docs/adr/0008-argo-workflows-run-the-roadmap-jobs-after-a-measured-go.md) records why and what result counts as a go (#1535), and [ADR 0021](../docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md) records the go and the move of the roadmap jobs (#4517). No roadmap job runs on it yet. Namespace `devops` holds WorkflowTemplate and CronWorkflow `rag-ingest` (#4180), but the controller watches only namespace `argo-workflows` (`singleNamespace`), so it does not run them.

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

Go when the warm p95 is at most 30 seconds and the burst finished with no 429 or 5xx. The measurement of 2026-11-11 gave a warm p95 of 11 s, and the owner recorded the go on [#1535](https://github.com/dan-petty/devops-cli/issues/1535). [ADR 0021](../docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md) records the numbers and the later steps (tracker #4517).

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
- The Access application of the wildcard has the policy `homelab-public-ip-bypass` (the setting `cloudflare.access.bypass_policy_name`) with the current public address of the workstation. `devops cloudflare access status --json` gives the ID of the application, and `devops cloudflare access policies <app-id>` lists its policies.

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

The next major version of the chart (its main branch, with Gitea 28) replaces `gitea.admin` with `secrets.admin`, turns persistence off by default and moves `strategy` under `deployment`. Change those keys in `gitea/values.yaml` in the pull request that changes the pinned version in `argocd/apps/gitea.yaml` and `HELM_RELEASES_BY_STACK`.

## Mattermost

Mattermost Team Edition runs under Argo CD from the Mattermost Operator on CloudNativePG PostgreSQL 17.

### What runs where

- **Operator**: `mattermost-operator` runs in namespace `mattermost-operator`.
- **Database Operator**: `cloudnative-pg` runs in namespace `cnpg-system`. It also runs the gateway database of stack `llm`, so deploy-stack installs it with stack `infra`. The Barman Cloud plugin runs beside it ([CloudNativePG Backup Plugin](#cloudnativepg-backup-plugin)).
- **Workload**: `Mattermost` runs in namespace `mattermost`.
- **Database**: CloudNativePG `Cluster` named `mattermost-db` runs in namespace `mattermost`.
- **Volume**: PVC `mattermost-files` stores uploaded files on `local-path`.

| Consumer | Address | How it reaches Mattermost |
| :--- | :--- | :--- |
| In-cluster pods | `http://mattermost.mattermost.svc.cluster.local:8065` | the service on TCP 8065 |
| Workstations and browsers | `https://mattermost.<domain>` | Cloudflare Tunnel, Traefik and Ingress `mattermost/mattermost` |

### Rollout

1. Merge the pull request. Argo CD creates the namespaces and objects. The database waits for Secret `mattermost/mattermost-db`. Alert `MattermostDatabaseDown` fires until step 2 completes.
2. Run `uv run devops k8s deploy-stack --stack chat --context <context>`. Always keep the default `--wait`: CloudNativePG's admission webhook refuses the `Cluster` until its operator is ready. Run `--stack infra` first on a cluster without Argo CD, because that stack installs the operator. The deploy pushes Secret `mattermost/mattermost-db` and sets the host on Application `mattermost`.
3. The owner signs up first from the bypassed network address. Cloudflare Access admits only the owner, so nobody else can claim the administrator account.
4. Set both persistent volumes to Retain:
   ```bash
   kubectl patch pv "$(kubectl -n mattermost get pvc -l cnpg.io/cluster=mattermost-db -o jsonpath='{.items[0].spec.volumeName}')" -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
   kubectl patch pv "$(kubectl -n mattermost get pvc mattermost-files -o jsonpath='{.spec.volumeName}')" -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
   ```
5. Run `uv run devops k8s bootstrap-mattermost --admin-user <user> --context <context>`. It creates the team (`--team`, default the setting `mattermost.team`, `homelab`), the channels `alerts` and `deploys`, an incoming webhook for each channel that is locked to its channel (#1390), and the slash command `/roadmap`. It saves the tokens in the keyring and pushes the Secrets.

### Operations

- **Backups**: The homelab has no backup mechanism for Mattermost yet (#1081). If a worker node fails, unbacked data on `local-path` is lost.
- **Upload limits**: The upload limit is 99 MB (`MM_FILESETTINGS_MAXFILESIZE=99000000`). Cloudflare enforces a 100 MB request ceiling, so 99 MB prevents edge 413 errors before Mattermost sees the payload. The mobile app has the same limit.
- **Upgrades**: Change `version` in `k8s/mattermost/mattermost.yaml`. With `Recreate` deployment strategy, an upgrade causes a brief outage while the old pod terminates and the new pod mounts the volume.
- **Password reset without email**:
  ```bash
  kubectl -n mattermost exec deploy/mattermost -- mmctl --local user change-password <user> --password <new>
  ```
- **Teardown**: On a cluster without Argo CD, `teardown-stack --stack chat` deletes the database and the files claim.

## CloudNativePG Backup Plugin

CloudNativePG 1.32.0 removes the in-tree `barmanObjectStore` (CloudNativePG release-1.30 documentation, `docs/src/appendixes/backup_barmanobjectstore.md`). A `Cluster` backs up and archives its WAL through the [Barman Cloud plugin](https://github.com/cloudnative-pg/plugin-barman-cloud) (Apache-2.0). The plugin gets its TLS certificates from [cert-manager](https://github.com/cert-manager/cert-manager) (Apache-2.0). Both run with stack `infra`. No database uses the plugin yet: the backup of a database adds an `ObjectStore` and the `plugins` entry of its `Cluster`.

| Helm release and Argo CD Application | Chart | Namespace | Purpose |
| :--- | :--- | :--- | :--- |
| `cert-manager` | `jetstack/cert-manager` v1.21.3 | `cert-manager` | Issues the server and client certificates of the plugin. The plugin chart brings its own self-signed `Issuer`, so there is no `ClusterIssuer` and no ACME account. |
| `plugin-barman-cloud` | `cloudnative-pg/plugin-barman-cloud` 0.9.0 (plugin v0.16.0) | `cnpg-system` | The plugin. It must run in the namespace of the operator. The operator finds it through Service `barman-cloud`, which has the label `cnpg.io/pluginName: barman-cloud.cloudnative-pg.io`. The chart adds CRD `objectstores.barmancloud.cnpg.io`. |

- **Order.** deploy-stack installs `cloudnative-pg`, then `cert-manager`, then `plugin-barman-cloud`. The start-up check Job of cert-manager holds `--wait` until the webhook answers, so the plugin chart can create its `Issuer` and `Certificate` objects. Argo CD syncs Application `plugin-barman-cloud` in sync wave 1, after `cert-manager`. It skips the dry run of a kind that has no CRD yet (`SkipDryRunOnMissingResource=true`), and it retries a failed sync five times.
- **CRDs.** The cert-manager chart installs its CRDs with `helm.sh/resource-policy: keep` (`crds.keep`), because a deleted CRD deletes every `Certificate` and `Issuer` in the cluster. Helm keeps them when the release is removed, and Argo CD reads the annotation as `Delete=false`.
- **Pod Security.** Namespaces `cert-manager` and `cnpg-system` enforce `restricted`. The pods of both charts meet it with the default values. cert-manager keeps its leader election lease in namespace `cert-manager` (`global.leaderElection.namespace`), so the chart writes no Role in `kube-system`.
- **Network.** `cert-manager/networkpolicy.yaml` admits only the metrics scrape of `monitoring` on 9402, and lets the pods reach only CoreDNS and the API server. The issuers are self-signed, so no pod calls an ACME server. `cert-manager/networkpolicy-webhook.yaml` admits any peer on TCP 10250 to the webhook pods alone: the API server calls the webhook from the host network of the control-plane node, and no selector names that address. `cnpg-system/networkpolicy.yaml` selects the plugin pod alone. Only the operator reaches its gRPC port 9090, and the pod reaches only CoreDNS and the API server. The instance pods need no rule there, because the plugin sidecar runs in the instance pod. The sidecar, not the plugin pod, sends the backups to the object store, so the perimeter of each database namespace gets that egress rule with its backup. The operator in `cnpg-system` has no policy.
- **Metrics.** Alloy scrapes the three cert-manager pods through their `prometheus.io/*` annotations ([Scrape Ownership](#scrape-ownership)).
- **Check.**
  ```bash
  kubectl get crd | grep -E 'cert-manager.io|barmancloud.cnpg.io'
  kubectl -n cnpg-system get certificate   # barman-cloud-client and barman-cloud-server are Ready
  kubectl -n argocd get application cert-manager plugin-barman-cloud
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

Teardown leaves the `prometheus-operator-crds` release's CRDs in the cluster. Deleting a CRD deletes every object of its kind, such as every ServiceMonitor, so remove them by hand only when nothing in the cluster uses them. The `argo-workflows` release's Workflow CRDs stay too (`crds.keep`), for the same reason: deleting them deletes every Workflow and WorkflowTemplate.

## GitOps

Argo CD maintains the declared state of the homelab cluster directly from this repository. A two-level application topology decouples cluster bootstrap from leaf applications:

1. **`bootstrap` (`k8s/argocd/bootstrap/bootstrap.yaml`)**: Tracks `main`. Syncs the root `cluster` Application.
2. **`cluster` (`k8s/argocd/bootstrap/cluster.yaml`)**: Tracks `main`. Syncs project RBAC boundaries (`k8s/argocd/apps/projects.yaml`) and every leaf Application of `k8s/argocd/apps/`: a raw leaf Application has one source, and a Helm leaf Application has several sources.

The private repository dan-petty/homelab receives a copy of the environment (dan-petty/homelab#23). The AppProjects `homelab` and `homelab-system` admit it as a source, and they keep this repository. Argo CD reads the homelab repository with the repository credential Secret `repo-homelab` in namespace `argocd`. The owner makes that Secret, and it never goes into git, so project `homelab` ignores it as an orphan. [docs/HOMELAB_REPO_SWITCH.md](../docs/HOMELAB_REPO_SWITCH.md) gives the steps that move the Applications to the homelab repository, with the check and the revert of each step.

When the root `cluster` Application is present in the cluster, `devops k8s deploy-stack` delegates manifest and Helm reconciliation to Argo CD, and `devops k8s teardown-stack` refuses execution to prevent configuration drift.

An object in the cluster that git does not hold is drift: remove it, or add it to git. The packaged add-ons of k3s are the exception (below). Back up the data on a PersistentVolume before you delete its claim. Public access goes through the Cloudflare tunnel and Cloudflare Access, and only the owner changes the Cloudflare configuration.

k3s, not git, holds its packaged add-ons, so an add-on and its objects are not drift. Do not remove them. The k3s server applies each packaged manifest as an `Addon` object in `kube-system`, and writes the file again at each start. `kubectl -n kube-system get addon` lists the add-ons. On k3s v1.37 they are `coredns`, `ccm`, `rolebindings`, `runtimes`, `gateway-api-crd` and seven metrics-server add-ons. For example, metrics-server serves the metrics API that `kubectl top` reads, and `runtimes` holds the RuntimeClass `nvidia` that the Ollama pods use. Each object of an add-on has the annotation `objectset.rio.cattle.io/owner-gvk` with the value `k3s.cattle.io/v1, Kind=Addon`. Its annotation `objectset.rio.cattle.io/owner-name` gives the add-on. Only the owner changes the k3s server, and so the add-ons.

CoreDNS is one of these add-ons: the add-on `coredns` applies the packaged manifest `coredns.yaml`. The Deployment `coredns` has 1 replica. It requests 100m CPU and 70Mi of memory, with a 170Mi memory limit and no CPU limit. k3s does not install CoreDNS from a Helm chart, so a HelmChartConfig has no chart to change. A change by hand to the Deployment stays only until k3s applies the manifest again. No alert reads the memory of the CoreDNS container. `kubectl -n kube-system get deployment coredns -o jsonpath='{.spec.replicas} {.spec.template.spec.containers[0].resources}'` shows the live values.

### Homelab Values at Deploy Time

This repository is public, so it holds no homelab value. Ingress hosts sit under the placeholder domain `example.com`, and the devops-cli config holds only its template, `k8s/devops/configmap.example.yaml`. `devops k8s deploy-stack` supplies the real values from `config.yaml` and the keyring:

| Value | Source | Where it lives | Supplied by |
| :--- | :--- | :--- | :--- |
| Secrets | the OS keyring (`devops k8s push-secrets`) | Secrets in the cluster | every stack's deploy, for its Secrets |
| `service.repos`, `service.github_app.app_id`, `service.github_app.installation_id`, `service.github_app.slug`, `service.poll_interval_seconds` | `config.yaml` | ConfigMap `devops-cli-config`, which no Application owns | `--stack devops` or `all` |
| `service.github_requests_per_hour`, only when a source sets it | `config.yaml` or `DEVOPS_CLI_SERVICE_GITHUB_REQUESTS_PER_HOUR` | ConfigMap `devops-cli-config`. With no value set, the ConfigMap holds none, and the Service uses its default of 500 | `--stack devops` or `all` |
| Hosts under the configured domain | `--domain`, else `k8s.domain`, `cloudflare.domain`, `DEVOPS_CLI_K8S_DOMAIN` or `DEVOPS_CLI_DOMAIN` | Kustomize patches in `spec.source.kustomize` of the Applications `devops` and `ingress` | `--stack devops` or `all` (both Applications), `--stack infra` or `gitea` (`ingress` only) |
| Container environment values under the configured domain: each `env[].value` of a container or init container of a Deployment that holds the placeholder domain, such as `HOMEPAGE_VAR_DOMAIN` | the same as the hosts | Kustomize patches in `spec.source.kustomize` of the Application that renders the Deployment | the same stacks as the hosts of that Application |
| ConfigMap data values under the configured domain: each `data` value of a ConfigMap that holds the placeholder domain, such as `CORS_ALLOW_ORIGIN` of `llm/open-webui-origins` | the same as the hosts | Kustomize patches in `spec.source.kustomize` of the Application that renders the ConfigMap | the same stacks as the hosts of that Application. Without Argo CD, the stack that lists the file in `MANIFESTS_BY_STACK` applies it under the configured domain |

To change the hourly GitHub request budget of the Service, run `devops config set service.github_requests_per_hour <n>`, then `devops k8s deploy-stack --stack devops`. The Service shows the budget it runs with in `devops_cli_service_budget_limit_requests{job="roadmap-service"}`, and the alert `RoadmapServiceGitHubRequestsHigh` follows that value.

A change of a live value follows these rules:

- A person changes the value with `devops config set` ([AGENTS.md](../AGENTS.md) rule 12). The command keeps a copy of `config.yaml` and a record of the changed keys, with no value.
- Do not change ConfigMap `devops-cli-config` with `kubectl edit` or `kubectl apply`. The next deploy-stack replaces such a change, and no record of it stays.
- deploy-stack also pushes the Secrets of its stack ([Cluster Secrets](#cluster-secrets)). An agent runs it only when `devops k8s push-secrets --stack <stack> --plan` shows each key `unchanged`. If not, a person runs it.
- Write a comment on the issue of the change. Give the key, the reason and the time in UTC, and no secret value.

The budget counts what GitHub counts against the rate limit of the installation: a conditional request that GitHub answers with 304 (#3497) leaves the budget when its answer comes. A request with no answer stays in it, because GitHub may have counted it, and a gh command has no status to read. `devops_cli_github_requests_total` still counts every request with its `status`, so `sum(increase(devops_cli_github_requests_total{job="roadmap-service", status!="304"}[1h]))` is the budget's measure (#3939).

The cluster Jobs act as the same App as the Service, and they do not count in `service.github_requests_per_hour`. Only the Service keeps this budget, in a record on its volume. A Job pod has no budget and an `emptyDir` home, so the Service does not see the requests of a Job. GitHub counts the requests of both against the one rate limit of the App installation. To read the requests of the Jobs, set the variable `Job` of the `devops-cli Telemetry` dashboard to `devops-cli-job`, and read the row GitHub API. The list of the variable follows the time range of the dashboard. If the list does not show this value, no Job ended or sent a request in that range: make the range wider.

The row Roadmap Service of that dashboard charts the rounds, the budget, the queues, the stops and the inputs of the Service.

The rest of ConfigMap `devops-cli-config` (gateway URL, models, context windows, telemetry) comes from `configmap.example.yaml` of the product base that deploy-stack reads (`--product-dir`, default `k8s/devops` of the current checkout), so run it from a checkout of `main`, the revision the cluster runs.

Unlike the ConfigMap, the host patches do not depend on the checkout. deploy-stack derives them from what each Application renders at the revision Argo CD builds: it fetches the Application's `targetRevision` from its `repoURL` into a temporary directory and builds its path with Kustomize, whichever branch is checked out locally. The fetch gets the credential of the GitHub session from `gh auth git-credential`, so an Application can name a private repository on github.com. The dry run lists the Applications and fetches nothing. `--argocd-revision <ref>` builds another revision instead, to stage hosts before a pull request merges.

The `cluster` Application ignores `spec.source.kustomize` on the two Applications in its diff. It applies the two Applications server-side, because each has the annotation `argocd.argoproj.io/sync-options: ServerSideApply=true`. Argo CD reads that annotation in every sync, automated or by hand, with any sync options. Server-side apply deletes only the fields that its own field manager, `argocd-controller`, set. The host patches belong to the field manager of deploy-stack's `kubectl patch`, and the image digest on `devops` belongs to Image Updater, so a sync of `cluster` keeps them. Do not remove the annotation. Client-side apply deletes each field that the `last-applied-configuration` annotation holds and git does not. The `RespectIgnoreDifferences=true` option of `cluster` writes the patches into that annotation, so a sync by hand without that option deletes them (#1817). The annotation `argocd.argoproj.io/client-side-apply-migration-manager: argocd-controller` on `cluster` moves the fields of the old client-side apply entry to the server-side apply entry in the first server-side sync. Thus a field that git removes from the two Applications also leaves the cluster.

Each patch names one object (an Ingress, an IngressRoute, a Mattermost, a Deployment or a ConfigMap) and tests the placeholder host, environment value or data value at each position before replacing it, so a value that git reorders or removes within that object fails the Application's manifest generation instead of routing to another backend. Kustomize skips a patch whose object no longer exists, and nothing covers an object, host, environment value or data value that git adds: run `devops k8s deploy-stack --stack devops` again once such a change reaches the Applications' revision. deploy-stack renders everything before it writes anything, so an unset setting stops it with an error naming the setting and changes nothing in the cluster. An unset service setting stops the dry run too; an unset domain stops only an Argo CD-managed deploy, and the dry run says so. A revision whose Application renders no host under the placeholder is refused rather than given an empty patch list.

Open WebUI reads `CORS_ALLOW_ORIGIN` from ConfigMap `llm/open-webui-origins` (`ingress/open-webui-origins.yaml`) only at start. It allows only these origins for its API and its Socket.IO connections, and without the variable it allows every origin. The value holds the HTTPS origin of each host of Ingress `llm/open-webui-ingress`, in the same order, and the `k8s` row of `devops ci` fails when the two differ. The Open WebUI pod does not start until the ConfigMap exists. On the homelab, Application `ingress` renders the ConfigMap, so `--stack infra`, `devops` or `gitea` sets its domain with the hosts. Without Argo CD, `--stack llm` applies it under the configured domain before the chart. A changed value does not restart Open WebUI: after it, run `kubectl -n llm rollout restart statefulset/open-webui`. Before a pull request that adds or changes the origins merges, stage them with `--argocd-revision`, so that Open WebUI does not start with the placeholder origins.

These values exist only in the cluster and in `config.yaml`, until step 14 of [the switch to the homelab repository](../docs/HOMELAB_REPO_SWITCH.md#step-14-the-live-patches-into-the-homelab-files) puts them into the private homelab repository. A sync keeps the host patches, but these actions remove them:

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

1. The Applications track `main` (`tests/invariants/test_k8s_argocd_apps.py` holds them there), so a merge moves `main` forward and the host patches stay in place. Run `devops k8s deploy-stack --stack devops --argocd-revision <branch>` from a checkout of the pull request's branch, right before merging, when the pull request changes `k8s/devops/configmap.example.yaml` (the ConfigMap follows only deploy-stack) or adds, removes, renames or reorders an Ingress or IngressRoute, or a host in one, or adds or changes a container environment value or a ConfigMap data value that holds the placeholder domain, such as the origins of Open WebUI. If the pull request moved a host that `main` also renders, the Application shows the ComparisonError `testing value <pointer> failed` until the merge, and its live Ingresses stay as they were.
2. Merge. Argo CD builds `main` with the staged hosts.
3. The service image changes only with a release. When the release pull request merges, the `Release` workflow's run on `main` builds, smoke-tests, scans, pushes and attests the service image, then tags it with the release tag and `latest` ([`RELEASE_CYCLE.md`](../RELEASE_CYCLE.md)). Within one poll of `latest` moving, Image Updater puts the `devops` Application on the new digest ([docs/CLUSTER.md](../docs/CLUSTER.md#service-image-updates), Service Image Updates), and roadmap-service, which uses the Recreate strategy, is down only while its pod restarts. Until then both workloads keep the previous release's digest: the merge's own sync changes no image, and nothing is committed. A person who re-runs a failed publish job moves both tags when it passes, and Image Updater rolls the workloads onto the new digest.
4. Check: `devops argo cd apps status devops` and `devops argo cd apps status ingress` are Synced and Healthy and exit 0. For `devops`, the command also reads the digest that `service:latest` names in GHCR and exits 1 when the Application's `spec.source.kustomize.images` pins another one, so ImageUpdater `devops` stopped updating ([docs/CLUSTER.md](../docs/CLUSTER.md#service-image-updates), Service Image Updates). `kubectl get ingress,ingressroute -A -o yaml | grep example.com` prints nothing, and `kubectl -n devops get configmap devops-cli-config -o yaml` holds the configured repositories and the template values of `main` (gateway URL, models, context windows).

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

Every Application sets `enabled: true` under `spec.syncPolicy.automated` in git, and `tests/invariants/test_k8s_argocd_apps.py` pins it. The value is in the parent's last-applied configuration, so a different value in the cluster is drift. `cluster` is the parent of the Applications in `k8s/argocd/apps/`, and `bootstrap` is the parent of `cluster` and of itself.

- Pause an Application in git: set `enabled: false` in its manifest and merge the change. While it is paused, the `ArgoCdAutoSyncDisabled` alert fires after 15 minutes.
- Do not pause an Application in the Argo CD UI or API. Its parent shows it OutOfSync and turns automated sync on again at its next self-heal.
- For an emergency stop that cannot wait for a merge, or for a volume move (Local-Path Volume Placement), pause from the top down: `bootstrap`, then `cluster`, then the Application. A paused `bootstrap` does not revert itself. Then commit the pause, or turn `bootstrap` on again: it restores `cluster`, and `cluster` restores the others from git.

### Notifications

Argo CD delivers notifications to Mattermost when the `devops` application deploys successfully and when any application sync fails. It also writes a GitHub deployment for each deploy of an Application that has one GitHub source.

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
- **GitHub deployments**: Each Application under `k8s/argocd/apps/` that has one `spec.source` on github.com carries the annotation `notifications.argoproj.io/subscribe.on-deployed.github: ""`.
  - When such an Application finishes a sync and reaches Healthy status (`on-deployed`), the notifier `service.github` writes a GitHub deployment for the synced commit. The environment is the Application name, and the status is `success`.
  - The trigger fires once for each value of `operationState.syncResult.revision`. This is the revision that the notifier reads. The `status.sync.revision` value moves to a new commit before its sync runs, so the trigger does not use it.
  - The notifier acts as the GitHub App `devops-cli-argocd`. It reads the keys `$github-appID`, `$github-installationID` and `$github-privateKey` of `argocd/argocd-notifications-secret` (see Cluster Secrets). The notifier needs only the repository permission Deployments (read and write). The repository credential `argocd/repo-homelab` uses the same App with the permission Contents (read) on the homelab repository (see GitOps).
  - The deployment sets `autoMerge: false` and no required check. So GitHub reads no commit status and writes no branch.
  - A multi-source Application sets neither `spec.source` nor `syncResult.revision`, so it carries no annotation.
  - The notification posts to `api.github.com` on TCP port 443. The perimeter network policy allows it.
  - List the deployments with `devops gh api "repos/<owner>/<name>/deployments?environment=<application>"`. A failed sync writes no GitHub deployment.
  - The engine builds all notifiers together. If one of the three keys is missing or the private key is not valid, no notification posts, including the Mattermost alerts. So the secret push requires the three keys, and it fails when one has no value.

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
[Client / Browser] ──── HTTPS ───▶ [DNS: *.<domain>]
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
  [chat.<domain>] ──▶ open-webui               [grafana.<domain>]    ──▶ grafana
  [ai.<domain>]   ──▶ llm-gateway              [argocd.<domain>]     ──▶ argocd
                                               [git.<domain>]        ──▶ gitea-http
                                               [mattermost.<domain>] ──▶ mattermost
```

### 1. Cloudflare Dashboard Tunnel Configuration

1. In **Cloudflare Zero Trust** (`Networks` > `Tunnels`), select your tunnel (e.g. `homelab`).
2. Add a **Public Hostname**:
   - **Subdomain**: `*`
   - **Domain**: `<domain>` (e.g. `example.com`)
   - **Path**: *(empty)*
   - **Type**: `HTTP`
   - **URL**: `traefik.kube-system.svc.cluster.local:80` (or `traefik.ingress.svc.cluster.local:80`)
   - **Additional Settings** > **HTTP Settings**:
     - **HTTP Host Header**: *(Leave blank)* — this preserves the client's original host header (e.g. `chat.<domain>`) so Traefik can route it.

### 2. Cloudflare Zero Trust Access Policy

1. In **Access** > **Applications**, add a **Self-Hosted Application**:
   - **Application Name**: `Homelab Wildcard`
   - **Application Domain**: `*.<domain>`
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
├── kustomization.yaml        # Root kustomize: applies namespaces, RuntimeClass gvisor, cloudflared, and the perimeters of cert-manager and cnpg-system
├── namespaces.yaml           # Namespace definitions with Prune=false,Delete=false
├── runtimeclass-gvisor.yaml  # RuntimeClass gvisor (handler runsc) for the nodes with label node-restriction.kubernetes.io/gvisor=true
├── catalog.toml              # The decisions of each service: Applications, tier, data class and dependencies (Service levels)
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
├── cert-manager/             # cert-manager, the certificates of the Barman Cloud plugin (#4764)
│   ├── kustomization.yaml    # The two perimeters, as the root kustomization applies them
│   ├── values.yaml           # Helm values for jetstack/cert-manager: kept CRDs, leader election in its namespace
│   ├── networkpolicy.yaml    # Default-deny perimeter: the metrics scrape in, DNS and the API server out
│   └── networkpolicy-webhook.yaml # The webhook pods: TCP 10250 in from any peer, for the API server
├── cnpg-system/              # The Barman Cloud plugin of CloudNativePG (#4764)
│   ├── kustomization.yaml    # The plugin perimeter, as the root kustomization applies it
│   ├── plugin-barman-cloud-values.yaml # Helm values for cloudnative-pg/plugin-barman-cloud
│   └── networkpolicy.yaml    # The plugin pod: the operator in on 9090, DNS and the API server out
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
│   ├── cronworkflow-rag-ingest.yaml # CronWorkflow rag-ingest: runs WorkflowTemplate rag-ingest every 3 minutes
│   ├── networkpolicy.yaml    # Default-deny perimeter: DNS, the gateway and public HTTPS out; skips the crawl4ai and searxng pods
│   ├── networkpolicy-rag-ingest.yaml # Lets the rag-ingest pods reach Qdrant on TCP 6333
│   ├── workflowtemplate-rag-ingest.yaml # WorkflowTemplate rag-ingest: keeps the RAG index current
│   ├── dashboards/           # The product dashboards; Application monitoring applies them, so the kustomization above does not list this folder
│   │   ├── kustomization.yaml # configMapGenerator: ConfigMap grafana-devops-cli-dashboards in namespace monitoring
│   │   ├── devops-cli.json   # devops-cli commands, reviews, RAG, spend and the roadmap Service
│   │   ├── ai-spend.json     # AI spend and LLM usage
│   │   └── project-metrics.json # Project & engineering velocity, release cadence and CI pass rates
│   ├── monitoring/
│   │   └── prometheus-rules-values.yaml # Second Helm values file of prometheus-community/prometheus: the product alert rules
│   ├── crawl4ai/             # Crawl4AI page-text service: Deployment, Service and the NetworkPolicies of the pod and of its one client
│   │   ├── kustomization.yaml
│   │   ├── deployment.yaml
│   │   ├── networkpolicy-client.yaml
│   │   ├── networkpolicy.yaml
│   │   └── service.yaml
│   ├── mcp-server/           # Role-scoped MCP server: Deployment, Service and NetworkPolicies for the roadmap Service and the Job pods
│   │   ├── kustomization.yaml
│   │   ├── deployment.yaml
│   │   ├── networkpolicy-client.yaml
│   │   ├── networkpolicy.yaml
│   │   └── service.yaml
│   ├── searxng/              # SearXNG search service: settings ConfigMap, Deployment, Service and the NetworkPolicies of the pod and of its one client
│   │   ├── kustomization.yaml
│   │   ├── configmap.yaml
│   │   ├── deployment.yaml
│   │   ├── networkpolicy-client.yaml
│   │   ├── networkpolicy.yaml
│   │   └── service.yaml
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
│   ├── ingress-routes.yaml   # Ingress rules for chat, ai, grafana, argocd, git, prometheus, qdrant
│   └── open-webui-origins.yaml # The CORS origins of Open WebUI: the HTTPS origins of its Ingress hosts
├── argocd/
│   ├── kustomization.yaml    # Kustomize overlay for Argo CD
│   ├── values.yaml           # Helm values for argo/argo-cd
│   ├── image-updater-values.yaml # Helm values for argo/argocd-image-updater: the ImageUpdater for Application devops
│   ├── bootstrap/            # Two-level bootstrap applications
│   │   ├── bootstrap.yaml    # Root app tracking main, reconciles cluster app
│   │   └── cluster.yaml      # Cluster app tracking main, reconciles projects & leaf apps
│   └── apps/                 # AppProjects and the leaf Applications (raw and Helm)
│       └── projects.yaml     # AppProjects: homelab and homelab-system
├── overlays/
│   └── homelab/              # Homelab overlays the Applications devops and ingress render; hosts stay under example.com
│       ├── ingress/          # Application ingress: k8s/ingress
│       └── devops/           # Application devops: k8s/devops
├── monitoring/
│   ├── kustomization.yaml    # Kustomize overlay for monitoring: NetworkPolicy and dashboards
│   ├── networkpolicy.yaml    # Default perimeter for the monitoring namespace
│   ├── dcgm-exporter-values.yaml # Helm values for nvidia/dcgm-exporter (GPU metrics)
│   ├── grafana-values.yaml   # Helm values for grafana-community/grafana (datasources, dashboard sidecar)
│   ├── k8s-monitoring-values.yaml # Helm values for grafana/k8s-monitoring (Alloy, kube-state-metrics, node-exporter, node journals, annotation autodiscovery, CoreDNS, profiling, and the Alloy, Grafana, Loki, Tempo and DCGM integrations)
│   ├── prometheus-operator-crds-values.yaml # Helm values for prometheus-community/prometheus-operator-crds (ServiceMonitor and other monitoring.coreos.com CRDs)
│   ├── prometheus-values.yaml # Helm values for prometheus-community/prometheus (server, Alertmanager, the environment alert rules and rule_files)
│   └── dashboards/
│       ├── kustomization.yaml # configMapGenerator: sidecar-labelled ConfigMaps for the environment dashboard groups; lists ../../devops/dashboards
│       ├── k8s-views-global.json, k8s-views-pods.json # ConfigMap grafana-k8s-global-dashboards
│       ├── k8s-views-nodes.json, k8s-views-namespaces.json # ConfigMap grafana-k8s-node-dashboards
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
