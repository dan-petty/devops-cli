# `devops k8s`

Manage Kubernetes clusters, pods, services, and workloads.

## Commands

## `devops k8s contexts`

**List kubeconfig contexts and mark the active one.**

```bash
devops k8s contexts
```

---

## `devops k8s switch-context`

**Switch active kubeconfig context.**

```bash
devops k8s switch-context <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Target context name to switch to. |

---

## `devops k8s status`

**Show node and pod summary for the current context.**

```bash
devops k8s status
```

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

---

## `devops k8s logs`

**Stream pod logs (delegates to kubectl).**

```bash
devops k8s logs [OPTIONS] <pod>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<pod>` | `string` | Yes | Pod name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--container`, `-c` | `string` | - | Specific container name within the pod. |
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |
| `--follow`, `-f` | `boolean` | - | Follow stream or log output in real time. |
| `--tail` | `integer` | `100` | Number of recent lines to display. |

---

## `devops k8s bootstrap`

**Bootstrap minikube Kubernetes cluster and deploy infrastructure/LLM stack.**

```bash
devops k8s bootstrap [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | `k8s` | Directory containing Kubernetes manifests. |
| `--auto-start`, `--no-auto-start` | `boolean` | `True` | Auto-start minikube if stopped. |
| `--stack`, `-s` | `string` | `all` | Stack to operate on: infra | llm | all. |

---

## `devops k8s bootstrap-openwebui`

**Bootstrap or activate a local administrator account for Open-WebUI.**

```bash
devops k8s bootstrap-openwebui [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--email`, `-e` | `string` | `admin@localhost` | Admin email address. |
| `--name`, `-n` | `string` | `Admin` | Admin display name. |
| `--password`, `-p` | `string` | `<masked>` | Admin password. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |

---

## `devops k8s deploy-stack`

**Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to Kubernetes.**

```bash
devops k8s deploy-stack [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--k8s-dir` | `path` | `k8s` | Path to k8s/ config directory. |
| `--stack`, `-s` | `string` | `infra` | Stack to operate on: infra | llm | all. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |

---

## `devops k8s configure-urls`

**Auto-detect Kubernetes stack URLs and update CLI config.**

```bash
devops k8s configure-urls [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `infra` | Stack to operate on: infra | llm | all. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |

---

## `devops k8s port-forward`

**Port-forward k8s monitoring / LLM stack services to localhost ports and update CLI config.**

```bash
devops k8s port-forward [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `infra` | Stack to operate on: infra | llm | all. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--argocd-port` | `integer` | `8080` | Local port for ArgoCD. |
| `--grafana-port` | `integer` | `8030` | Local port for Grafana. |
| `--prometheus-port` | `integer` | `8090` | Local port for Prometheus. |
| `--jaeger-port` | `integer` | `16686` | Local port for Jaeger Query UI. |
| `--otel-port` | `integer` | `4318` | Local port for OpenTelemetry OTLP Traces (HTTP). |
| `--ollama-port` | `integer` | `11434` | Local port for Ollama. |
| `--open-webui-port` | `integer` | `3000` | Local port for Open-WebUI. |
| `--qdrant-port` | `integer` | `6333` | Local port for Qdrant HTTP. |
| `--valkey-port` | `integer` | `<masked>` | Local port for Valkey. |
| `--address` | `string` | `127.0.0.1` | Local address to bind for port-forwarding. |

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
| `--stack`, `-s` | `string` | `infra` | Stack to operate on: infra | llm | all. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |

---

## `devops k8s rbac-audit`

**Audit RBAC RoleBindings and ServiceAccounts for overprivileged access.**

```bash
devops k8s rbac-audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | - |

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
| `--key` | `path` | `<masked>` | Path to TLS private key file (.key or .pem). |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |

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
| `--secret-name` | `string` | `<masked>` | Name of the Kubernetes TLS secret to create or update. |
| `--stack`, `-s` | `string` | `all` | Stack to operate on: infra | llm | all. |
| `--overwrite`, `-f` | `boolean` | - | Overwrite existing files or resources if they exist. |

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
| `--strict`, `--no-strict` | `boolean` | `True` | Disallow additional undeclared properties. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
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
| `--follow`, `-f`, `--no-follow` | `boolean` | - | Continuously stream live log output. |
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
