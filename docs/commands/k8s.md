# `devops k8s`

Manage Kubernetes clusters, pods, services, and workloads.

## Commands

## `devops k8s contexts`

**List kubeconfig contexts and mark the active one.**

```bash
devops k8s contexts [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s switch-context`

**Switch active kubeconfig context and ensure cluster is running.**

```bash
devops k8s switch-context [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Target context name to switch to. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s status`

**Show node and pod summary for the current context.**

```bash
devops k8s status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s apply`

**Apply a Kubernetes manifest (delegates to kubectl).**

```bash
devops k8s apply [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `string` | Yes | Manifest file or directory path. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |
| `--template`, `-t` | `boolean` | - | Render manifest as a template substituting domain from config or --domain before applying. |
| `--domain`, `-d` | `string` | - | Domain to substitute for template (defaults to k8s.domain in config.yaml). |

---

## `devops k8s render`

**Render Kubernetes manifest templates with domain and variables substituted.**

```bash
devops k8s render [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `string` | Yes | Manifest file or directory path. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--domain`, `-d` | `string` | - | Domain to substitute for template (defaults to k8s.domain in config.yaml). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s logs`

**Stream pod logs or execute LogQL queries across cluster log streams.**

```bash
devops k8s logs [OPTIONS] <pod> <query_arg>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<pod>` | `string` | No | Pod name. |
| `<query_arg>` | `string` | No | Optional LogQL query string when using query subcommand |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--query`, `-q` | `string` | - | LogQL query expression |
| `--container`, `-c` | `string` | - | Specific container name within the pod. |
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |
| `--follow`, `-f` | `boolean` | - | Follow stream or log output in real time. |
| `--tail` | `integer` | `100` | Number of recent lines to display. |
| `--limit` | `integer` | `100` | Max lines for LogQL query |
| `--since` | `string` | `1h` | Time range for LogQL query |
| `--loki-url` | `string` | - | Loki service endpoint |
| `--format` | `string` | `text` | Output format (text, json) |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s bootstrap`

**Bootstrap homelab Kubernetes cluster with Minikube, Calico, and ingress.**

```bash
devops k8s bootstrap [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | `k8s` | Directory containing Kubernetes manifests. |
| `--auto-start` / `--no-auto-start` | `boolean` | `True` | Auto-start minikube if stopped. |
| `--stack`, `-s` | `string` | `all` | Stack to operate on: infra | llm | logging | devops | gitea | chat | all. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s bootstrap-openwebui`

**Bootstrap or activate a local administrator account for Open-WebUI.**

```bash
devops k8s bootstrap-openwebui [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--email`, `-e` | `string` | `admin@localhost` | Email address for the local administrator account. |
| `--password`, `-p` | `string` | - | Password for administrator. If omitted, securely generated and stored in OS Keyring. |
| `--name`, `-n` | `string` | `Local Administrator` | Full display name for the administrator. |
| `--context`, `-c` | `string` | - | Kubernetes context to target (defaults to config default or active). |
| `--show-password` | `boolean` | - | Display generated admin password in plain text instead of masking. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s deploy-stack`

**Deploy one stack (infra, llm, logging, devops, gitea, chat) or all of them to Kubernetes with Helm and Kustomize.**

Deploy one stack (infra, llm, logging, devops, gitea, chat) or all of them to Kubernetes with Helm and Kustomize.

Right after the namespaces, it pushes the Secrets of the base rows, its stacks and every detached stack whose namespace exists (`devops k8s push-secrets`), before anything that reads them. A locked or missing keyring stops it before it applies anything.

```bash
devops k8s deploy-stack [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--k8s-dir` | `path` | `k8s` | Path to k8s/ config directory. |
| `--stack`, `-s` | `string` | `infra` | Stack to operate on: infra | llm | logging | devops | gitea | chat | all. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--domain`, `-d` | `string` | - | Domain to substitute for template (defaults to k8s.domain in config.yaml). |
| `--wait` / `--no-wait` | `boolean` | `True` | Wait for Helm releases and workloads to become ready before returning. |
| `--timeout`, `-t` | `string` | `10m` | Timeout for Helm operations when waiting. |
| `--port-forward` / `--no-port-forward` | `boolean` | - | Start background port-forwarding daemons for deployed services. |
| `--configure-urls` / `--no-configure-urls` | `boolean` | - | Auto-configure devops-cli settings with detected Kubernetes service URLs. |
| `--push-secrets` / `--no-push-secrets` | `boolean` | `True` | Push the stacks' Secrets from the OS keyring before applying anything (--no-push-secrets for a cluster without a keyring). |
| `--argocd-revision` | `string` | - | Derive the Argo CD host overrides from this Git revision instead of each Application's targetRevision, to stage them before a pull request merges into main (Argo CD-managed clusters only). |
| `--dry-run` | `boolean` | - | Print the releases, manifests and Secrets (key names only) a deploy would apply, and run nothing. |

---

## `devops k8s sync-secrets`

**Copy chart-generated admin credentials (Argo CD, Grafana) from the cluster into the OS keyring.**

Copy chart-generated admin credentials (Argo CD, Grafana) from the cluster into the OS keyring.

The direction is cluster → workstation keyring, the reverse of `push-secrets`. The command
keeps a stored Argo CD or Grafana API token that the service accepts, and mints a new token
only when the service refuses the stored one. When a token check fails, the stored token
stays. Each failed step shows its cause, and the command then exits with status 1.

```bash
devops k8s sync-secrets [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `infra` | Stack to operate on: infra | llm | logging | devops | gitea | chat | all. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s push-secrets`

**Write the cluster's Secrets from the OS keyring (workstation keyring → cluster, the reverse of sync-secrets). Adopts live values the keyring lacks, generates the ones nobody types, and never replaces a live value without --rotate.**

```bash
devops k8s push-secrets [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `all` | Push the Secrets of one stack: base, infra, llm, logging, devops, gitea, chat, or all (default). |
| `--only` | `string` | - | Push only this Secret, as NAMESPACE/NAME. Repeatable; replaces --stack. |
| `--rotate` | `boolean` | - | Replace live values that differ from the keyring's. |
| `--restart` / `--no-restart` | `boolean` | `True` | Restart the workloads of each existing Secret whose data changed; --no-restart prints the commands instead. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--plan` | `boolean` | - | Read the keyring and the live Secrets (read-only); print each key's state and the workloads a change would restart, and write nothing. |
| `--dry-run` | `boolean` | - | Make no request, reads included: print the requests a push would make, in order, with placeholders for every value. Wins over --plan. |

---

## `devops k8s run-job`

**Run a devops command as a Job in namespace devops, from the template of a CronJob with only its arguments changed, follow its log and exit with its exit code.**

```bash
devops k8s run-job [OPTIONS] <args>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<args>` | `string` | Yes | The devops arguments the Job runs, after `--`. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--template` | `choice (default|runner)` | `default` | The CronJob whose template makes the Job: default is CronJob devops-cli, runner is CronJob devops-cli-runner, the pod of the implement job (it sets roadmap.implement.in_runner). |
| `--repo` | `string` | - | owner/name of the one repository the runner Job may use. The Job's GitHub token names only that repository. Required with --template runner, and used with no other template. The Job carries a label of the repository, and the command creates no Job while another runner Job of the repository has not ended. |
| `--wait` / `--no-wait` | `boolean` | `True` | Follow the Job's log and exit with its exit code; --no-wait prints the Job's name. |
| `--start-timeout` | `float` | `120.0` | Seconds to wait for the Job's pod to leave Pending. |
| `--dry-run` | `boolean` | - | Make no request, not even the CronJob read: print the kubectl requests a run would make, in order, with the Job's template parts as placeholders. |

---

## `devops k8s configure-urls`

**Auto-detect Kubernetes stack URLs and update CLI config.**

```bash
devops k8s configure-urls [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `infra` | Stack to operate on: infra | llm | logging | devops | gitea | chat | all. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--addressing`, `-a` | `string` | - | How to record endpoints: 'nodeport' writes a cluster-specific host and port, 'proxy' writes portable k8s:// service addresses needing no port-forward, only for the Services that the API server reaches, 'fqdn' discovers Ingress hostnames and writes domain-based URLs. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s service-url`

**Show, or fetch from, a cluster service address that needs no port-forward.**

```bash
devops k8s service-url [OPTIONS] <service>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<service>` | `string` | Yes | Service name to address through the Kubernetes API server. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | `default` | Kubernetes namespace. |
| `--port`, `-p` | `string` | `http` | Service port name or number (a Service may expose several). |
| `--path` | `string` | `` | Request path appended to the service address. |
| `--tls` | `boolean` | - | The service speaks HTTPS behind the proxy. |
| `--fetch` | `boolean` | - | Fetch the address and print the JSON response instead of the address. |
| `--context`, `-c` | `string` | - | Target context name to switch to. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s port-forward`

**Port-forward k8s monitoring / LLM stack services to localhost ports.**

```bash
devops k8s port-forward [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `infra` | Stack to operate on: infra | llm | logging | devops | gitea | chat | all. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--argocd-port` | `integer` | `8080` | Local port for ArgoCD. |
| `--grafana-port` | `integer` | `8030` | Local port for Grafana. |
| `--prometheus-port` | `integer` | `8090` | Local port for Prometheus. |
| `--tempo-port` | `integer` | `3200` | Local port for Grafana Tempo HTTP API. |
| `--pyroscope-port` | `integer` | `4040` | Local port for Pyroscope Continuous Profiling UI. |
| `--otel-port` | `integer` | `4318` | Local port for OpenTelemetry OTLP Traces (HTTP). |
| `--ollama-port` | `integer` | `11434` | Local port for Ollama. |
| `--open-webui-port` | `integer` | `3000` | Local port for Open-WebUI. |
| `--qdrant-port` | `integer` | `6333` | Local port for Qdrant HTTP. |
| `--valkey-port` | `integer` | `6379` | Local port for Valkey. |
| `--address` | `string` | `127.0.0.1` | Local address to bind for port-forwarding. |
| `--update-config` / `--no-update-config` | `boolean` | - | Update devops-cli configuration with port-forwarded service URLs. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s port-forward-status`

**List active background Kubernetes port-forward daemons.**

```bash
devops k8s port-forward-status
```

---

## `devops k8s port-forward-stop`

**Terminate active background Kubernetes port-forward daemons.**

```bash
devops k8s port-forward-stop [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--service`, `-s` | `string` | - | Specific service to stop |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s teardown-stack`

**Uninstall the k8s infrastructure / LLM stack and delete namespaces.**

```bash
devops k8s teardown-stack [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--k8s-dir` | `path` | `k8s` | Path to k8s/ config directory. |
| `--stack`, `-s` | `string` | `infra` | Stack to operate on: infra | llm | logging | devops | gitea | chat | all. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s rbac-audit`

**Audit RBAC RoleBindings and ServiceAccounts for overprivileged access.**

```bash
devops k8s rbac-audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | Audit only this namespace's RoleBindings and Roles; ClusterRoleBindings are always read. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s lint`

**Validate K8s manifests and Helm charts using Red Hat Kube-linter.**

```bash
devops k8s lint [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target K8s manifest file or directory to lint. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s audit`

**Sanitize active K8s/Minikube cluster resource health using Derailed Popeye.**

```bash
devops k8s audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s check-deprecated`

**Scan manifests for deprecated/removed K8s API versions using Fairwinds Pluto.**

```bash
devops k8s check-deprecated [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target manifest file or directory to scan for deprecated APIs. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s image-pins`

**Render each Argo CD Application of the repository and resolve each image it pins in its
registry, as an anonymous client, without pulling it. Exits 1, before it resolves an image, when
an image has no digest and the latest tag or no tag, unless Image Updater moves it. Exits 1 when
a registry does not hold an image or refuses the read. Docker Hub counts each read of a Docker
Hub image as an anonymous pull, from the allowance of the network's public address, which the
cluster's nodes may share; the CI job `image-pins` runs the check on a pull request that changes
k8s/.**

```bash
devops k8s image-pins [OPTIONS] <root>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<root>` | `path` | No | Repository root whose Argo CD Applications in k8s/argocd/ are rendered. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s create-tls-secret`

**Create or update a kubernetes.io/tls secret from certificate and private key files.**

```bash
devops k8s create-tls-secret [OPTIONS] <secret_name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<secret_name>` | `string` | Yes | Name of the Kubernetes TLS secret to create or update. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | `default` | Kubernetes namespace. |
| `--cert` | `path` | `~/.config/devops-cli/tls/tls.crt` | Path to TLS certificate file (.crt or .pem). |
| `--key` | `path` | `~/.config/devops-cli/tls/tls.key` | Path to TLS private key file (.key or .pem). |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s enable-tls`

**Generate Homelab certificates and apply TLS secrets across Kubernetes cluster namespaces.**

```bash
devops k8s enable-tls [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--tls-dir` | `path` | `~/.config/devops-cli/tls` | Directory with generated TLS certificates. |
| `--secret-name` | `string` | `homelab-tls` | Name of the Kubernetes TLS secret to create or update. |
| `--stack`, `-s` | `string` | `all` | Stack to operate on: infra | llm | logging | devops | gitea | chat | all. |
| `--overwrite`, `-f` | `boolean` | - | Overwrite existing files or resources if they exist. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s validate`

**Validate Kubernetes YAML manifests against OpenAPI schemas using Kubeconform.**

```bash
devops k8s validate [OPTIONS] <manifest_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<manifest_path>` | `path` | No | Manifest file or directory path. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--kubernetes-version`, `-v` | `string` | `master` | Target Kubernetes OpenAPI version. |
| `--strict` / `--no-strict` | `boolean` | `True` | Disallow additional undeclared properties. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---

## `devops k8s validate-policy`

**Validate Kubernetes manifests against Kyverno or OPA admission policies.**

```bash
devops k8s validate-policy [OPTIONS] <manifest_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<manifest_path>` | `path` | No | Manifest file or directory path. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--policy`, `-p` | `path` | - | Path to Kyverno policy or OPA rule file. |
| `--engine`, `-e` | `string` | `kyverno` | Policy evaluation engine (kyverno, opa). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---

## `devops k8s stream-logs`

**Stream logs across multiple pods in parallel using Stern or kubectl.**

```bash
devops k8s stream-logs [OPTIONS] <pod_query>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<pod_query>` | `string` | Yes | Regex pattern or query to match pod names. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |
| `--container`, `-c` | `string` | - | Specific container name within the pod. |
| `--tail`, `-t` | `integer` | `100` | Number of historical log lines to stream. |
| `--follow`, `-f` / `--no-follow` | `boolean` | - | Continuously stream live log output. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s diff-helm`

**Preview Kubernetes manifest diffs before executing a Helm upgrade.**

```bash
devops k8s diff-helm [OPTIONS] <release_name> <chart_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<release_name>` | `string` | Yes | Name of deployed Helm release. |
| `<chart_path>` | `path` | No | Path to local Helm chart directory or packaged archive. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |
| `--values`, `-f` | `path` | - | Values YAML files to override release defaults. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s chaos`

**Run resilience and chaos experiments against Kubernetes workloads.**

```bash
devops k8s chaos [OPTIONS] <experiment>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<experiment>` | `string` | No | Resilience experiment name (e.g., pod-kill, latency-inject). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--deployment`, `-d` | `string` | `sample-app` | Target deployment to disrupt. |
| `--namespace`, `-n` | `string` | `default` | Kubernetes namespace. |
| `--duration` | `integer` | `30` | Reconciliation monitoring window in seconds. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---

## `devops k8s pods`

**List running pods with health status, restart counts, and age.**

```bash
devops k8s pods [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |
| `--label`, `-l` | `string` | - | Kubernetes label selector filter (e.g. app=frontend). |
| `--all-namespaces`, `-A` | `boolean` | - | Query pods across all namespaces. |
| `--watch`, `-w` | `boolean` | - | Continuously refresh pod list in real-time terminal display. |
| `--interval`, `-i` | `float` | `3.0` | Auto-refresh polling interval in seconds. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops k8s security-stream`

**Stream runtime security anomaly events from Kubernetes Falco eBPF probes.**

```bash
devops k8s security-stream [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | `falco` | Kubernetes namespace. |
| `--label`, `-l` | `string` | `app.kubernetes.io/name=falco` | Kubernetes label selector filter (e.g. app=frontend). |
| `--severity`, `-s` | `string` | - | Minimum severity filter threshold (Notice, Warning, Error, Critical). |
| `--duration`, `-d` | `integer` | `30` | Observation streaming window duration in seconds. |
| `--tail`, `-t` | `integer` | `100` | Number of historical log lines to stream. |
| `--follow`, `-f` / `--no-follow` | `boolean` | - | Continuously stream live log output. |
| `--simulate` | `boolean` | - | Generate simulated kernel eBPF security anomalies for testing. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--format` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--output`, `-o` | `path` | - | Export discovered alerts to JSON file |

---

## `devops k8s gpu-matrix`

**Query traditional homelab GPU matrix and model service alias mappings.**

```bash
devops k8s gpu-matrix [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--gpus`, `-g` | `integer` | - | Filter by GPU count (1, 2, 3, 4). |
| `--vram`, `-v` | `integer` | - | Filter by VRAM per GPU in GiB (16, 24, 32). |
| `--backend`, `-b` | `string` | - | Filter by inference backend (e.g. ollama). |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml. |
| `--aliases`, `-a` | `boolean` | - | Include Kubernetes model service aliases mapping. |

---

## `devops k8s doctor`

**Diagnose Kubernetes cluster deployment health, correlate failures, and recommend remediations.**

```bash
devops k8s doctor [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | Target specific Kubernetes namespace (default: all namespaces). |
| `--context` | `string` | - | Target Kubernetes cluster context (default: resolved context). |
| `--tail`, `-t` | `integer` | `20` | Number of container log lines to tail per flagged container. |
| `--format`, `-f` | `string` | `table` | Output format: table, json, or yaml. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--stack` | `string` | - | Check one stack end to end in place of the cluster rules: gitea. The gitea checks read Applications gitea and gitea-manifests, the volume of claim gitea-shared-storage, the Pod Security of namespace gitea and the host of Ingress gitea-ingress. Through that host, they check the sign-in page, the refusal of an anonymous API read, the token challenge of the registry, and the clone URL of a temporary private repository, which they make as gitea_admin with keyring gitea_admin_password and then delete. Last, they check that the pod reaches no address outside the cluster. Exits 2 when a check fails. |

---

## `devops k8s tunnel`

**Keep the local end of the Kubernetes API route at k8s.\<domain\> running: one 'cloudflared access tcp' forward, for the tunnel kubeconfig context off the home network.**

```bash
devops k8s tunnel COMMAND [ARGS]...
```

### `devops k8s tunnel start`

**Log in to Cloudflare Access, then start the forward to k8s.tunnel_host in the background and wait until its port accepts connections. When a recorded forward runs, report it and start no other.**

```bash
devops k8s tunnel start [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--port`, `-p` | `integer` | `16443` | Local port of the forward. |
| `--context` | `boolean` | - | Add or update the kubeconfig cluster and context \<cluster\>-tunnel, which reach the API server through the forward. |
| `--from-context` | `string` | - | Kubeconfig context whose cluster, user and CA data the tunnel context copies (default: k8s.context). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops k8s tunnel stop`

**Stop the recorded forward and its process group, and remove its record.**

```bash
devops k8s tunnel stop [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops k8s tunnel status`

**Show the recorded forward, whether its port accepts connections, and whether the API server of the tunnel context answers. A 401 or 403 counts as an answer.**

```bash
devops k8s tunnel status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--port`, `-p` | `integer` | - | Local port of the forward. |
| `--context`, `-c` | `string` | - | Kubeconfig context to check the API server through (default: the context that 'start --context' wrote). |

---

## `devops k8s volume`

**Move a local-path claim to a volume on another node, and reclaim orphaned PersistentVolumes.**

```bash
devops k8s volume COMMAND [ARGS]...
```

### `devops k8s volume reclaim`

**Safely reclaim an orphaned PersistentVolume verified to have no active claims or mounts.**

```bash
devops k8s volume reclaim [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Name of the PersistentVolume to reclaim. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Simulate volume reclaim and print planned Kubernetes API operations without network requests. |
| `--yes`, `-y` | `boolean` | - | Confirm reclamation without interactive prompt (required in non-interactive sessions). |
| `--patch` | `boolean` | - | Patch volume finalizers instead of issuing a DELETE request. |
| `--context`, `-c` | `string` | - | Target context name to switch to. |

### `devops k8s volume move`

**Move the data of a local-path claim to a new volume on another node, and bind the claim to it. The move pauses Argo CD from the top down, stops the workloads that mount the claim, copies the data with GNU tar through the API server, compares the two sides, binds the claim to the new volume, starts the workloads and resumes Argo CD. Before it deletes the old claim, a failure undoes its steps; after that, a failure leaves Argo CD paused and names the saved claim. The old volume stays, with reclaim policy Retain, until a person deletes it.**

```bash
devops k8s volume move [OPTIONS] <claim>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<claim>` | `string` | Yes | The claim to move, as NAMESPACE/CLAIM. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--to-node` | `string` | - | The worker node to move the volume to. Default: the worker node with the most free disk, for a volume on the control-plane node. A volume on a worker node moves only to the node that this option names. |
| `--plan` | `boolean` | - | Read the claim, its volume, the nodes, the workloads and the Argo CD Applications, print each step with the real names, and change nothing. |
| `--dry-run` | `boolean` | - | Make no request, reads included: print the requests a move would make, in order, with placeholders for each value that a read gives. Wins over --plan. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |

---
