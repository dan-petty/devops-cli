# k8s/ — Local Kubernetes Infrastructure & LLM Stacks

Kustomize + Helm-based configurations for deploying infrastructure management (`infra`) and local AI/LLM (`llm`) stacks to the devcontainer's minikube cluster.

## Stacks Overview

| Stack | Components | Namespaces | Default Ports |
| :--- | :--- | :--- | :--- |
| **`infra`** *(Default)* | ArgoCD (backed by Valkey), Grafana k8s-monitoring (Alloy + kube-state-metrics + node-exporter), Prometheus server, Grafana, Alertmanager, Grafana Pyroscope, NVIDIA DCGM Exporter, OpenTelemetry Collector, Jaeger | `argocd`, `monitoring`, `otel` | `8080` (ArgoCD), `8030` (Grafana), `8090` (Prometheus), `4040` (Pyroscope) |
| **`llm`** | Ollama (per-VRAM-tier DaemonSets), LLM Gateway (LiteLLM), Open-WebUI, Qdrant Vector DB, Valkey Cache | `llm` | `11434` (Ollama), `3000` (WebUI), `6333` (Qdrant), `6379` (Valkey) |
| **`logging`** | Loki, Fluent Bit (pod logs shipped from `infra` stack's Alloy) | `logging` | `3100` (Loki) |
| **`all`** | All components from the three stacks | `argocd`, `monitoring`, `otel`, `llm`, `logging` | All ports above |

## Prerequisites

- minikube running (`minikube status` or auto-started by `devops devcontainer post-start`)
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
# Ollama REST API (one ClusterIP Service per VRAM tier, e.g. ollama-16gib)
kubectl -n llm port-forward svc/ollama-16gib 11434:11434

# Open-WebUI Web Interface
minikube service open-webui -n llm --url

# Qdrant Vector Database HTTP API
minikube service qdrant -n llm --url

# Valkey In-Memory Cache
kubectl -n llm exec -it svc/valkey -- valkey-cli ping

# Valkey Run Index (not deployed by deploy-stack; apply `k8s/llm/valkey-runs.yaml` yourself after creating its password):
# benchmark and evaluation runs shared by workstations. Its password Secret comes from the keyring (see Cluster Secrets),
# then point devops-cli at it through its NodePort.
devops k8s push-secrets --only llm/valkey-runs-auth
devops ai runs connect

# LLM Gateway: authenticated OpenAI-compatible API for every Ollama model
minikube service llm-gateway -n llm --url
```

### LLM Gateway (`llm-gateway`)
The LiteLLM gateway is the single entry point to every inference server. It serves the virtual models `devops-chat`, `devops-coder`, `devops-reasoning` and `devops-review`, plus models by name (`qwen3.8:27b`, `gemma4:31b`, `deepseek-r1:70b`, `bge-m3:latest`, `embeddinggemma:300m`). It moves a prompt too long for `devops-chat` to `devops-coder`, then `devops-reasoning`, before calling any backend. It falls back from an unavailable `devops-coder` to `devops-reasoning` before the small Ollama model, and rejects requests without its master key. `devops k8s deploy-stack` writes the key (`llm/llm-gateway-secrets`, starting with `sk-`) from the keyring before the gateway starts, adopting a live key the keyring lacks and generating one where neither has it; `devops k8s push-secrets --only llm/llm-gateway-secrets` does the same alone (see Cluster Secrets).
The Service is a NodePort that Kubernetes assigns; find it with `kubectl -n llm get svc llm-gateway`, then call the API from any node address:
```bash
KEY=$(kubectl -n llm get secret llm-gateway-secrets -o jsonpath='{.data.master-key}' | base64 -d)
curl -H "Authorization: Bearer $KEY" http://<node>:<node-port>/v1/models
```
These groups route reviews, embeddings and background work:

- `devops-review` spreads one model name over four Ollama tiers: `qwen3-coder:30b` on `ollama-48gib` (weight 9) and `ollama-64gib` (6), and `gpt-oss:20b` on `ollama-16gib` (8) and `ollama-24gib` (1). Each deployment takes a share of requests weighted by its throughput, and pre-call checks keep a prompt off any deployment whose window it exceeds. No deployment is capped with `max_parallel_requests`: LiteLLM waits on the cap only after routing, so queued requests pile up behind it while larger servers idle, and the backends queue excess requests themselves.
- Ollama models are also served under their own names: `qwen3.8:27b`, `gemma4:31b`, `deepseek-r1:70b`, and the embedding models `bge-m3:latest` and `embeddinggemma:300m`. Embedding groups configure `model_info.mode: embedding` so health checks embed rather than generate.
- `qwen3-coder:30b` and `gpt-oss:20b` each pin one of `devops-review`'s models: the group copies that model's `devops-review` deployments and weights, with no `max_input_tokens` and no fallback, so a review measured on one model is routed as the pool routes it.
- `devops-background` is the background tier's one generation model: `qwen3.8:27b` on `ollama-48gib-slow`. That tier serves one request at a time, so it is in no interactive or review pool, where background work would queue in front of review calls. It keeps its embedding model and `qwen3.8:27b` loaded together and is sent no other model. In-cluster services (`k8s/devops/` such as `roadmap-service` and cluster jobs) and `devops-review` fallback reach it; the pinned groups have no fallback. The gateway's 1,500 s timeout outlasts the review client's 1,200 s, so a `devops-review` call that timed out at the gateway was already given up, and the fallback spends the tier's slot on a reply nobody reads. Use it for `devops review path --watch`, `devops ai pipeline`, `devops ai agents` and `devops ai analyze` through environment overrides, never in workstation `config.yaml`, so no interactive run lands on it. Set `DEVOPS_CLI_AI_MAX_RETRIES=1`. The gateway abandons a call after 1,100 s and never retries it, but the client retries a failed or timed-out call in its HTTP transport and again in its dispatch loop, `ai.max_retries` times each, and every retry waits for the same single slot. With `1` a call is sent at most four times; `0` does not stop retries, because the transport then makes five attempts:
  ```bash
  DEVOPS_CLI_AI_MAX_RETRIES=1 DEVOPS_CLI_AI_TASK_ANALYSIS_MODEL=devops-background \
    DEVOPS_CLI_AI_TASK_VERIFICATION_MODEL=devops-background \
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
    # verification:      # checks the findings analysis produced; unset, analysis verifies
    #   model: devops-reasoning   # layered on analysis: same provider, gateway and window
    chat:                # devops ai chat
      provider: gateway
      model: devops-coder
    embedding:
      provider: gateway
      model: embeddinggemma:300m
```
Provider `gateway` always sends to `ai.gateway_url`, even when `ai.api_base_url` is set for another provider. To send one task to a different gateway, set `api_base_url` on that task.

`verification` applies on top of `analysis`, so it only has to name what differs. Leave it unset unless a comparison on your own reviews favors a split. On the homelab, verifying with the 32B model then behind `devops-reasoning` (vLLM, since removed) made reviews slower, since every verification queued on one server. It also rejected nearly every candidate, while one top-severity false positive still passed.

Open WebUI uses the same key: on a fresh install it connects to the gateway automatically. An existing installation keeps the connections stored in its database, so add `http://llm-gateway.llm.svc.cluster.local:4000/v1` under Admin Panel > Settings > Connections.

### GPU Placement: Ollama tiers
Ollama runs as one DaemonSet per total-VRAM tier (`ollama-16gib` … `ollama-128gib`, `llm/profiles/ollama-profiles.yaml`), scheduled by the node label `nvidia.com/gpu.total-vram-gib`. The gateway reaches each tier through its ClusterIP Service `ollama-<n>gib`.

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
- `--addressing proxy` writes `k8s://` addresses that the API server proxies from the control-plane node's host network. kube-router admits host-network traffic only to pods on the same node, so Grafana, Prometheus and Pyroscope answer this way only while they run on the control-plane node. Elsewhere, use port-forward or `fqdn`. The same holds for any namespace behind a perimeter, `llm` included.

## Grafana Dashboards

Dashboards live in `monitoring/dashboards/`. Its `kustomization.yaml` generates four ConfigMaps labelled `grafana_dashboard: "1"`, and the Grafana dashboard sidecar (`monitoring/grafana-values.yaml`) loads every ConfigMap with that label:

| ConfigMap | Dashboards |
| :--- | :--- |
| `grafana-k8s-global-dashboards` | `k8s-views-global.json`, `k8s-views-pods.json` |
| `grafana-k8s-node-dashboards` | `k8s-views-nodes.json`, `k8s-views-namespaces.json` |
| `grafana-devops-cli-dashboards` | `devops-cli.json`, `ai-spend.json`, `project-metrics.json` |
| `grafana-stack-dashboards` | `sre-service.json`, `ingress-tunnel.json`, `llm-stack.json`, `otel-collector.json`, `prometheus-server.json`, `pyroscope.json` |

On a cluster Argo CD manages, its `monitoring` Application applies them; the root kustomization leaves them out, so the `base` Application does not own them as well. Without Argo CD, `devops k8s deploy-stack --stack infra` (or `all`) applies the `monitoring` kustomization, which lists the namespace's perimeter and `dashboards`, right after the root kustomization creates the `monitoring` namespace, and `teardown-stack` removes them with that namespace. Grafana holds these dashboards as provisioned and refuses to save over them, so change the JSON file and deploy again. To provision another dashboard, add it to a generator entry; each ConfigMap must stay under the 262,144 bytes kubectl's last-applied annotation allows.

The stack dashboards chart the cluster workloads and infrastructure services:

| Dashboard | Exporter / Sources | How Prometheus / Loki gets its series |
| :--- | :--- | :--- |
| `sre-service.json`, "SRE Service & Logs" (`devops-sre-service`) | cAdvisor container CPU, memory, network packets/drops, Loki service logs, and Pyroscope flamegraphs | Metrics scraped by Alloy from cAdvisor/Kubelet and Kube State Metrics; logs pushed to Loki via Alloy or OpenTelemetry collector; continuous profiles queried from Pyroscope datasource |
| `ingress-tunnel.json`, "SRE / Ingress & Cloudflare Tunnel" (`devops-ingress-tunnel`) | Traefik ingress metrics (port 9100) and Cloudflare Tunnel metrics (port 2000) | Scraped directly by the Prometheus server's `kubernetes-pods` job via pod annotations; network policy allows monitoring to scrape Cloudflare Tunnel |
| `llm-stack.json`, "LLM Gateway & GPUs" (`devops-llm-stack`) | LiteLLM's Prometheus callback on the gateway (`/metrics/`), and the NVIDIA DCGM exporter on every GPU node | The `llm-gateway` ServiceMonitor in `monitoring/k8s-monitoring-values.yaml` and the DCGM chart's own ServiceMonitor (`serviceMonitor.enabled` in `monitoring/dcgm-exporter-values.yaml`), read by Alloy, which remote-writes to the server |
| `otel-collector.json`, "OpenTelemetry Collector" (`devops-otel-traces`) | The collector's own telemetry on port 8888 | The server's `kubernetes-pods` job, through the `prometheus.io/scrape` and `prometheus.io/port` pod annotations in `otel/values.yaml`; not through Alloy, so the collector's export failures stay visible when Alloy is what fails |
| `prometheus-server.json`, "Prometheus Server" (`devops-prometheus-server`) | The Prometheus server's own `/metrics`, and `up` for every target | The server's `prometheus` job, which scrapes itself (`scrapeConfigs.prometheus` in `monitoring/prometheus-values.yaml`) |
| `pyroscope.json`, "Continuous Profiling / Pyroscope Flamegraphs" (`devops-pyroscope`) | Grafana Pyroscope continuous profiling (CPU, memory, goroutines) | Continuous profiles collected by the Alloy profiling agent and scraped by the Pyroscope backend |

```bash
devops grafana dashboards lint k8s/monitoring/dashboards  # also catches a uid two files share
devops grafana dashboards sync                            # posts every file in the directory
```
`sync` exits 1 if any dashboard failed. It reports the provisioned dashboards as skipped, not failed.

`tests/test_stack_dashboards.py` checks every query against captures of these exporters in `tests/fixtures/metrics/`: each series it selects, each label it matches or groups by, and the scrape in the table. No query falls back to a constant such as `or vector(0)`, so a panel without data reads "No data" rather than zero, and a panel drawn against a limit extends its axis to that limit. The gateway's failure, cooldown and fallback panels and the collector's span export failures stay empty until the first such event.

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

Loki's compactor retention takes effect once #550's Loki migration has been applied, a step a person runs: the volume rebind above, then the Loki upgrade. Until then Loki deletes no logs by age. The same upgrade adds the pod annotations through which Prometheus scrapes Loki, so `LokiRetentionNotRunning` has no series before it; after it, the alert fires if the compactor stops applying retention.

## Host Journals and Health Metrics

Each node sends its journal to Loki and its health series to Prometheus through the k8s-monitoring chart (`monitoring/k8s-monitoring-values.yaml`), with no agent installed on the host:

- **Journal (`nodeLogs`)**: the `alloy-logs` DaemonSet, which already reads pod logs, reads `/var/log/journal`. It keeps kernel lines at every priority, the `k3s`, `k3s-agent`, `nvidia-power-limit`, `containerd` and `systemd-journald` units and systemd's own lines about them at info and above, and every other line at warning and above. Each unit may send 1 line/s after a burst of 10,000; kernel lines have no limit. Lines carry `job="integrations/kubernetes/journal"`, `instance` (the node), `unit`, `transport` and `level`, with the boot ID as structured metadata (`boot_id`).
- **What the journal reader drops**: counted only on each `alloy-logs` pod's own `/metrics` (port 12345), which Prometheus does not scrape. Every entry the keep rules drop counts as `loki_source_journal_target_parsing_errors_total{error="empty_labels"}`, so that series counts the filter at work, not errors; lines the rate limit cuts count per unit in `loki_process_dropped_lines_by_label_total{label_name="unit"}`.
- **Metrics (`hostMetrics`)**: beyond the chart's default list, `node_boot_time_seconds`, `node_hwmon_temp_celsius` with `node_hwmon_chip_names`, `node_pressure_*`, the EDAC correctable and uncorrectable error counters, `node_nvme_info`, filesystem size and free space, and `node_systemd_unit_state` for the units above. node-exporter's systemd collector reads unit state over the host's D-Bus socket, reached through the node root the chart mounts at `/host/root`.

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
| `PersistentVolumeSpaceLow` | A volume that reports kubelet volume stats has under 10% free; no volume on this cluster reports them yet | 15m | warning |
| `LogOrMetricVolumeDiskLow` | The root filesystem of the node holding `storage-loki-0` or `prometheus-server` has under 10% free; names the claim at risk | 30m | warning |
| `PrometheusNearRetentionSizeCap` | Prometheus's data uses over 80% of `server.retentionSize`, before the cap deletes blocks younger than 30 days | 1h | warning |
| `PrometheusSizeLimitCutHistory` | Prometheus deleted blocks to stay under its size cap | — | warning |
| `PrometheusStorageNearClaim` | Prometheus's data uses over 80% of the `prometheus-server` claim, which with the cap at 80% of the claim means the cap is not holding it | 1h | warning |
| `LokiRetentionNotRunning` | Loki's compactor has not applied retention for over an hour; silent until #550's Loki migration, whose upgrade turns retention on and starts the Loki scrape | 30m | warning |
| `LokiRequestErrors` | Over 5% of a Loki route's requests return 5xx | 15m | warning |
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

Silence the node, then drain it. Every alert about one node carries a `node` label: node-exporter's rules copy it from `instance`, the kubernetes-pods job sets it on the pods it scrapes, and `LogOrMetricVolumeDiskLow` takes it from the pod holding the claim. So one silence covers the node, its scrape targets, its units and the `NodeRebooted` that follows. Make it last the work plus 30 minutes:

```bash
kubectl -n monitoring exec statefulset/prometheus-alertmanager -c alertmanager -- \
  amtool --alertmanager.url=http://localhost:9093 silence add 'node="<node>"' \
  --duration=3h --author=<name> --comment="<reason>"
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data
```

The drain matters because a few cluster-wide alerts have no `node` label. One pod, `k8s-monitoring-alloy-metrics-0`, forwards every series from kube-state-metrics, node-exporter and the DCGM exporter. Drained, it starts again on another node. Left on a node that powers off, it stays bound there until the node returns. Those series stop, no other node's `NodeNotReady` can fire, and after about 15 minutes `ClusterMetricsMissing` (critical, no `node` label) pages, because the node silence does not match it. Pods on `local-path` volumes (Prometheus, Loki, Grafana, Pyroscope and Alertmanager) cannot move and wait for their node. While the node holding Prometheus or Alertmanager is down, no alert is evaluated or sent at all.

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
| `llm/qdrant-api-key` | `api-key` | keyring `qdrant_api_key` | yes | adopt the live value; else generate `token_urlsafe(32)` | llm | `statefulset/qdrant` |
| `llm/valkey-runs-auth` | `password` | keyring `runs_index_password` | yes | adopt the live value; else generate 64 hex | llm | `deployment/valkey-runs` |
| `cloudflared/cloudflared-token` | `token` | keyring `cloudflare_tunnel_token` | no | adopt the live value; else skip with a warning | base | `deployment/cloudflared` |
| `devops/devops-cli` | `GH_TOKEN` | gh account | yes | fail | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_AI_API_KEY` | keyring `llm_gateway_master_key` | yes | adopt from `llm/llm-gateway-secrets master-key`; else fail | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS` | keyring `service_webhook_secrets` | no | adopt the live value; else skip with a warning | devops | `deployment/roadmap-service` |
| `devops/devops-cli` | `DEVOPS_CLI_TAVILY_API_KEY` | keyring `tavily_api_key` | no | adopt the live value; else skip with a warning | devops | `deployment/roadmap-service` |
| `monitoring/grafana-admin` | `admin-user` | literal | yes | fail | infra | `deployment/grafana` |
| `monitoring/grafana-admin` | `admin-password` | keyring `grafana_password` | yes | adopt from `monitoring/grafana admin-password`; else generate `token_urlsafe(32)` | infra | `deployment/grafana` |

- The keyring must be unlocked (`devops devcontainer unlock-keyring`); a locked or missing keyring stops the push before anything is read or written, and stops deploy-stack before it applies anything.
- A value the keyring lacks but the cluster holds is adopted into the keyring, so a first push changes nothing live. Only values nobody types are generated, and each is stored in the keyring before it is pushed.
- Typed values are stored at a hidden prompt: `devops config set cloudflare.tunnel_token`.
- `GH_TOKEN` is the token gh keeps in the OS keyring for the machine account named by `--github-account` or `devops config set k8s.github_account <login>`. The push takes gh's word for it: `gh auth status` must list the login with its token in the keyring and its own check of the token passing, then `gh auth token --user <login>` reads it. devops-cli never calls GitHub with the machine token itself, so a run keeps the one GitHub identity it has (#767).
- `devops` rows are pushed wherever namespace `devops` exists, also by every deploy-stack run. `devops k8s deploy-stack --no-push-secrets` skips the push on a cluster without a keyring.
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

1. `uv run devops config set service.repos <owner/name>` (each repository the service works for), then `uv run devops config set service.webhook_secrets` (hidden prompt; a JSON object mapping `owner/name` to its secret). deploy-stack refuses the devops stack until `service.repos` and the machine account (step 2) are set.
2. `uv run devops k8s push-secrets --stack devops`, with the machine account's login in `k8s.github_account` (#741). deploy-stack also pushes it once namespace `devops` exists.
3. Invite the machine account as a Write collaborator on each repo and board.
4. Check that the GHCR `service` package is public (#741 made it so): `DOCKER_CONFIG=$(mktemp -d) docker pull ghcr.io/dan-petty/devops-cli/service:<tag>`.
5. `devops cloudflare tunnel routes`. If no route covers the webhook host, add one in the dashboard, not with `tunnel sync` (#794).
6. `devops cloudflare access status`, then add a Bypass application for `hooks.<domain>/webhooks/github`.
7. `devops k8s deploy-stack --stack devops` (or `--stack all`).
8. Add each repo's webhook: `https://hooks.<domain>/webhooks/github`, `application/json`, that repo's secret, and the Issues, Pull requests and Milestones events.
9. To rotate a credential, update it in the keyring (`uv run devops config set service.webhook_secrets`, or `gh auth login` for the machine account), then run `uv run devops k8s push-secrets --only devops/devops-cli --rotate`. It restarts `roadmap-service`.
10. Run one service per set of repos. While it runs, use `devops roadmap run --dry-run` (#981).

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

## GitOps

Argo CD maintains the declared state of the homelab cluster directly from this repository. A two-level application topology decouples cluster bootstrap from leaf applications:

1. **`bootstrap` (`k8s/argocd/bootstrap/bootstrap.yaml`)**: Tracks `main`. Syncs the root `cluster` Application.
2. **`cluster` (`k8s/argocd/bootstrap/cluster.yaml`)**: Tracks `main`. Syncs project RBAC boundaries (`k8s/argocd/apps/projects.yaml`) and all 20 leaf Applications (8 raw leaf applications and 12 multi-source Helm applications).

When the root `cluster` Application is present in the cluster, `devops k8s deploy-stack` delegates manifest and Helm reconciliation to Argo CD, and `devops k8s teardown-stack` refuses execution to prevent configuration drift.

### Homelab Values at Deploy Time

This repository is public, so it holds no homelab value. Ingress hosts sit under the placeholder domain `example.com`, and the devops-cli config holds only its template, `k8s/devops/configmap.example.yaml`. `devops k8s deploy-stack` supplies the real values from `config.yaml` and the keyring:

| Value | Source | Where it lives | Supplied by |
| :--- | :--- | :--- | :--- |
| Secrets | the OS keyring (`devops k8s push-secrets`) | Secrets in the cluster | every stack's deploy, for its Secrets |
| `service.repos`, `service.machine_account` (or `k8s.github_account`), `service.poll_interval_seconds`, `service.drain_timeout_seconds` | `config.yaml` | ConfigMap `devops-cli-config`, which no Application owns | `--stack devops` or `all` |
| Hosts under the configured domain | `--domain`, else `k8s.domain`, `cloudflare.domain`, `DEVOPS_CLI_K8S_DOMAIN` or `DEVOPS_CLI_DOMAIN` | Kustomize patches in `spec.source.kustomize` of the Applications `devops` and `ingress` | `--stack devops` or `all` (both Applications), `--stack infra` (`ingress` only) |

The rest of ConfigMap `devops-cli-config` (gateway URL, models, context windows, telemetry) comes from `k8s/devops/configmap.example.yaml` in the checkout deploy-stack runs from (`--k8s-dir`, default `./k8s`), so run it from a checkout of the release the cluster runs.

Unlike the ConfigMap, the host patches do not depend on the checkout. deploy-stack derives them from what each Application renders at the revision Argo CD builds: it fetches the Application's `targetRevision` from its `repoURL` into a temporary directory and builds its path with Kustomize, whichever branch is checked out locally. `--argocd-revision <ref>` builds another revision instead, to stage hosts before a release merges. The `cluster` Application ignores `spec.source.kustomize` on the two Applications and syncs with `RespectIgnoreDifferences=true`, so its self-heal keeps the patches.

Each patch names one Ingress or IngressRoute and tests the placeholder host at each position before replacing it, so a host that git reorders or removes within that object fails the Application's manifest generation instead of routing to another backend. Kustomize skips a patch whose object no longer exists, and nothing covers an object or host that git adds: run `devops k8s deploy-stack --stack devops` again once such a change reaches the Applications' revision. deploy-stack renders everything before it writes anything, so an unset setting stops it with an error naming the setting and changes nothing in the cluster. An unset service setting stops the dry run too; an unset domain stops only an Argo CD-managed deploy, and the dry run says so. A revision whose Application renders no host under the placeholder is refused rather than given an empty patch list.

These values exist only in the cluster and in `config.yaml`. Once `cluster` has recreated the Applications `devops` and `ingress` (after `bootstrap-gitops`, for example), run `devops k8s deploy-stack --stack devops` to set them again; until then they sync the placeholder hosts.

#### When a release merges into `main`

1. The Applications track `main` (`devops release check` holds them there), so a merge moves `main` forward and the host patches stay in place. Run `devops k8s deploy-stack --stack devops --argocd-revision release/vX.Y.Z` from a checkout of the release, right before merging, when the release changes `k8s/devops/configmap.example.yaml` (the ConfigMap follows only deploy-stack) or adds, removes, renames or reorders an Ingress or IngressRoute, or a host in one. If the release moved a host that `main` also renders, the Application shows the ComparisonError `testing value <pointer> failed` until the merge, and its live Ingresses stay as they were.
2. Merge. Argo CD builds the release with the staged hosts.
3. The `devops` Application pins roadmap-service and CronJob `devops-cli` to `service:vX.Y.Z`, which the Release Orchestration workflow publishes only after its release job. roadmap-service uses the Recreate strategy, so it is down until that image exists; watch the workflow, and once the image is published run `kubectl -n devops rollout restart deploy/roadmap-service`.
4. Check: `devops argo cd apps status devops` and `devops argo cd apps status ingress` are Synced and Healthy, `kubectl get ingress,ingressroute -A -o yaml | grep example.com` prints nothing, and `kubectl -n devops get configmap devops-cli-config -o yaml` holds the configured repositories and the release's template values (gateway URL, models, context windows).

> [!NOTE]
> `k8s/coredns/` remains managed outside Argo CD to preserve cluster DNS resolution during bootstrap and recovery cycles.

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

### Replaced Hand Steps

| Previous Manual Step | Replaced By Argo CD GitOps |
| :--- | :--- |
| `devops k8s deploy-stack --stack <name>` | Automated reconciliation by Argo CD leaf applications. |
| `devops k8s apply k8s/...` | Declarative raw leaf Applications (`apps/*.yaml`) with `selfHeal: true`. |
| Manual Helm release upgrades (`helm upgrade ...`) | Multi-source Helm Applications with pinned chart versions and git value files. |
| Ad-hoc ingress and domain patching | Host overrides that `devops k8s deploy-stack` sets on the Applications `devops` and `ingress` from `config.yaml` (see Homelab Values at Deploy Time). |
| Secret storage in Helm values | External secret synchronization (`devops k8s push-secrets`) decoupled from manifests. |
| Manual drift reconciliation | Automated self-healing (`automated.prune: true`, `automated.selfHeal: true`). |

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
     k8s / Namespace: llm                         k8s / Namespaces: monitoring, argocd
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
3. Set your Traefik ingress service type to `ClusterIP`:
   ```bash
   kubectl patch svc traefik -n kube-system -p '{"spec": {"type": "ClusterIP"}}'
   ```
4. Deploy the core service Ingress definitions with template substitution (substitutes `k8s.domain` from `config.yaml`; set it to `homelab.<domain>` so the rendered hosts such as `chat.homelab.<domain>` fall under the `*.homelab.<domain>` tunnel hostname):
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
├── kustomization.yaml        # Root kustomize: applies namespaces, cloudflared, registry, monitoring Service aliases
├── namespaces.yaml           # Namespace definitions with Prune=false,Delete=false
├── cloudflared/
│   ├── kustomization.yaml    # Kustomize overlay for Cloudflare Tunnel
│   ├── deployment.yaml       # Multi-replica non-root cloudflared deployment
│   └── networkpolicy.yaml    # Network isolation for tunnel ingress and egress
├── devops/                   # In-cluster devops-cli runtime; not in the root kustomization
│   ├── kustomization.yaml    # Its resources, and the service image's tag (`devops release prepare` sets it)
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
│   └── ingress-routes.yaml   # Ingress rules for chat, ai, grafana, argocd, prometheus, qdrant
├── argocd/
│   ├── kustomization.yaml    # Kustomize overlay for Argo CD
│   ├── values.yaml           # Helm values for argo/argo-cd
│   ├── bootstrap/            # Two-level bootstrap applications
│   │   ├── bootstrap.yaml    # Root app tracking main, reconciles cluster app
│   │   └── cluster.yaml      # Cluster app tracking release branch, reconciles projects & leaf apps
│   └── apps/                 # AppProjects and 20 leaf Applications (8 raw + 12 Helm)
│       └── projects.yaml     # AppProjects: homelab and homelab-system
├── overlays/
│   └── homelab/              # Homelab overlays the Applications devops and ingress render; hosts stay under example.com
│       ├── ingress/          # Application ingress: k8s/ingress without the roadmap-service Ingress
│       └── devops/           # Application devops: k8s/devops
├── monitoring/
│   ├── kustomization.yaml    # Kustomize overlay for monitoring: NetworkPolicy and dashboards
│   ├── networkpolicy.yaml    # Default perimeter for the monitoring namespace
│   ├── service-aliases.yaml  # Alias Services for Prometheus and Grafana; the root kustomization lists them
│   ├── dcgm-exporter-values.yaml # Helm values for nvidia/dcgm-exporter (GPU metrics)
│   ├── grafana-values.yaml   # Helm values for grafana/grafana (datasources, dashboard sidecar)
│   ├── k8s-monitoring-values.yaml # Helm values for grafana/k8s-monitoring (Alloy, kube-state-metrics, node-exporter, node journals, and gateway monitors)
│   ├── prometheus-operator-crds-values.yaml # Helm values for prometheus-community/prometheus-operator-crds (ServiceMonitor and other monitoring.coreos.com CRDs)
│   ├── prometheus-values.yaml # Helm values for prometheus-community/prometheus (server, Alertmanager and alert rules)
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
│   ├── networkpolicy.yaml    # Perimeter NetworkPolicy for otel namespace
│   └── values.yaml           # Helm values for opentelemetry-collector
├── llm/
│   ├── kustomization.yaml    # Kustomize overlay for LLM stack base
│   ├── profiles/             # Ollama per-VRAM-tier DaemonSets and ollama-<n>gib Services (applied by deploy-stack)
│   ├── valkey.yaml           # Valkey Deployment + Service manifest
│   ├── valkey-runs.yaml      # Run index Valkey: PVC, Deployment, NodePort Service, NetworkPolicy
│   ├── values-open-webui.yaml# Helm values for open-webui/open-webui
│   ├── values-qdrant.yaml    # Helm values for qdrant/qdrant
│   └── gateway/              # LiteLLM gateway: Deployment, routing ConfigMap, NodePort Service, NetworkPolicy
└── README.md                 # This file
```
