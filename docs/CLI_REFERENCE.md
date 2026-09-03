# DevOps CLI Reference

Complete command-line reference for `devops-cli`, automatically generated from CLI command specifications.

## Command Groups

- [`devops repos`](#devops-repos) — Clone, synchronize, and manage organization repositories.
- [`devops ssh`](#devops-ssh) — Generate, rotate, audit, and register Ed25519 SSH keypairs.
- [`devops branches`](#devops-branches) — Branch management and Jira workflows.
- [`devops devcontainer`](#devops-devcontainer) — Manage devcontainer configurations.
- [`devops workspace`](#devops-workspace) — Manage multi-root VS Code workspace files (.code-workspace).
- [`devops install-tools`](#devops-install-tools) — Install and manage DevOps tool binaries.
- [`devops k8s`](#devops-k8s) — Manage Kubernetes clusters, pods, services, and workloads.
- [`devops kustomize`](#devops-kustomize) — Kustomize build and apply operations.
- [`devops docker`](#devops-docker) — Docker image management.
- [`devops grafana`](#devops-grafana) — Grafana dashboard and alert management.
- [`devops prometheus`](#devops-prometheus) — Prometheus metrics querying and analysis.
- [`devops argo`](#devops-argo) — Argo CD, Workflows, and Rollouts management.
- [`devops config`](#devops-config) — Show, set, get, or initialize CLI configuration.
- [`devops ci`](#devops-ci) — Run tests, linting, formatting, and type-checks.
- [`devops uv`](#devops-uv) — uv dependency management proxies.
- [`devops scan`](#devops-scan) — Security scanner suite: Trivy, Gitleaks, Semgrep, Checkov, Kubeconform.
- [`devops ai`](#devops-ai) — Configure, test, chat, analyze, and review codebases (Ollama, Claude, Copilot).
- [`devops review`](#devops-review) — AI-powered multi-persona code review and security audits.
- [`devops mcp`](#devops-mcp) — FastMCP server and Model Context Protocol integrations.
- [`devops docs`](#devops-docs) — Generate and validate CLI and architecture documentation.
- [`devops release`](#devops-release) — Automate version bumps, changelogs, tags, and GitHub releases.
- [`devops pr`](#devops-pr) — GitHub Pull Request workflows and reviews.
- [`devops tf`](#devops-tf) — OpenTofu and Terraform Infrastructure-as-Code operations.
- [`devops tls`](#devops-tls) — Generate and manage homelab TLS certificates and CAs.
- [`devops telemetry`](#devops-telemetry) — OpenTelemetry tracing, metrics, and Jaeger observability.
- [`devops serve`](#devops-serve) — FastAPI REST & OpenAPI Service Engine for remote automation, health probes, and metrics.
- [`devops test`](#devops-test) — Test suite orchestration, git-diff aware test selector, and load testing.
- [`devops pipeline`](#devops-pipeline) — Programmable containerized pipeline execution (Dagger).
- [`devops vault`](#devops-vault) — Enterprise HashiCorp Vault secret broker

---

## devops repos

Clone, synchronize, and manage organization repositories.

### `devops repos clone-org`

**Clone all repos from a GitHub org into repos/<org>/.**

```bash
devops repos clone-org [OPTIONS] <org>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<org>` | `string` | No | GitHub organisation name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |
| `--private`, `--no-private` | `boolean` | `True` | - |
| `--forks`, `--no-forks` | `boolean` | - | - |

### `devops repos clone`

**Clone an individual repository into repos/_standalone/<name>/.**

```bash
devops repos clone [OPTIONS] <url>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<url>` | `string` | Yes | Repository URL (SSH or HTTPS). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |

### `devops repos list`

**List all cloned repositories.**

```bash
devops repos list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |

### `devops repos update`

**Fetch (and optionally pull) all tracking branches across repos.**

```bash
devops repos update [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--pull`, `--no-pull` | `boolean` | `True` | - |

### `devops repos sync`

**Fetch (and optionally pull) all tracking branches across repos.**

```bash
devops repos sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--pull`, `--no-pull` | `boolean` | `True` | - |

---

## devops ssh

Generate, rotate, audit, and register Ed25519 SSH keypairs.

### `devops ssh generate`

**Generate a new Ed25519 SSH key with prefix and YYYYMMDD date suffix.**

```bash
devops ssh generate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-dir` | `path` | - | Directory where SSH keys are stored. |
| `--comment`, `-c` | `string` | `` | Comment to include in public key. |
| `--prefix`, `-p` | `string` | - | Optional prefix for the SSH key name (defaults to config setting, devcontainer name, or basename pwd). |

### `devops ssh register`

```bash
devops ssh register [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-file`, `-k` | `path` | - | Path to private key. |
| `--title` | `string` | - | Title for the item or entity. |
| `--prefix`, `-p` | `string` | - | Optional prefix for the SSH key name (defaults to config setting, devcontainer name, or basename pwd). |

### `devops ssh rotate`

**Rotate keys older than rotation_days (default 90).**

Rotate keys older than rotation_days (default 90).

Generates, registers, and reports the old key.

```bash
devops ssh rotate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-dir` | `path` | - | Directory where SSH keys are stored. |
| `--force`, `-f` | `boolean` | - | Rotate even if not yet due. |
| `--prefix`, `-p` | `string` | - | Optional prefix for the SSH key name (defaults to config setting, devcontainer name, or basename pwd). |

### `devops ssh list`

**List all managed SSH keys with their age and rotation status.**

```bash
devops ssh list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-dir` | `path` | - | Directory where SSH keys are stored. |
| `--prefix`, `-p` | `string` | - | Optional prefix for the SSH key name (defaults to config setting, devcontainer name, or basename pwd). |

### `devops ssh audit`

**List all managed SSH keys with their age and rotation status.**

```bash
devops ssh audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-dir` | `path` | - | Directory where SSH keys are stored. |
| `--prefix`, `-p` | `string` | - | Optional prefix for the SSH key name (defaults to config setting, devcontainer name, or basename pwd). |

### `devops ssh status`

**Show the active SSH key and days until rotation.**

```bash
devops ssh status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-dir` | `path` | - | Directory where SSH keys are stored. |
| `--prefix`, `-p` | `string` | - | Optional prefix for the SSH key name (defaults to config setting, devcontainer name, or basename pwd). |

---

## devops branches

Branch management and Jira workflows.

### `devops branches update`

**Fetch and pull tracking branches across all repos.**

```bash
devops branches update [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |

### `devops branches sync`

**Fetch and pull tracking branches across all repos.**

```bash
devops branches sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |

### `devops branches jira`

**Create a feature branch for a Jira ticket: feature/PROJ-123[-slug].**

```bash
devops branches jira [OPTIONS] <ticket_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<ticket_id>` | `string` | Yes | Jira ticket ID, e.g. PROJ-123. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--slug`, `-s` | `string` | - | Short branch description. |
| `--repo`, `-r` | `path` | - | Repository root directory (default: current directory). |

### `devops branches list`

**List branches across all repos.**

```bash
devops branches list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |
| `--all`, `-a` | `boolean` | - | Include remote branches. |

### `devops branches clean`

**Delete local branches merged into main/master.**

```bash
devops branches clean [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |
| `--dry-run`, `-n` | `boolean` | - | Preview execution plan without mutating external state. |

---

## devops devcontainer

Manage devcontainer configurations.

### `devops devcontainer init`

**Scaffold .devcontainer/ using the published DevOps CLI devcontainer image.**

```bash
devops devcontainer init [OPTIONS] <repo_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo_path>` | `path` | No | Path to the repository. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--name`, `-n` | `string` | - | Project name. |
| `--python` | `string` | `3.14` | Python version for base template. |
| `--image`, `-i` | `string` | - | Base container image (defaults to published devops-cli image). |
| `--published`, `-p` | `boolean` | `True` | Use published GHCR image (defaults to True). |
| `--home-volume` | `string` | - | Custom volume name for /home/vscode (defaults to <project_name>-home). |
| `--force`, `-f` | `boolean` | - | Overwrite existing devcontainer.json and configurations. |

### `devops devcontainer update`

**Update the Python image version in an existing devcontainer.json.**

```bash
devops devcontainer update [OPTIONS] <repo_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo_path>` | `path` | No | Path to the repository. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--python` | `string` | `3.14` | Python version for base template. |

### `devops devcontainer validate`

**Validate .devcontainer/devcontainer.json manifest syntax and configuration schema.**

```bash
devops devcontainer validate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | `.` | Path to workspace directory containing .devcontainer. |
| `--config`, `-c` | `path` | - | Direct path to devcontainer.json. |
| `--dry-run` | `boolean` | - | Simulate DevContainer manifest validation. |

### `devops devcontainer list`

**List repos with their devcontainer status.**

```bash
devops devcontainer list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |

### `devops devcontainer post-create`

**Execute DevContainer post-create setup tasks (history, shell completions, config prep).**

```bash
devops devcontainer post-create [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | `.` | Workspace root directory path. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops devcontainer post-start`

**Execute DevContainer post-start tasks (SSH keys, git defaults, kubeconfig, MCP sync).**

```bash
devops devcontainer post-start [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | `.` | Workspace root directory path. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops devcontainer run-lifecycle`

**Run specified DevContainer lifecycle hook tasks natively in Python.**

```bash
devops devcontainer run-lifecycle [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | `.` | Workspace root directory path. |
| `--post-create` | `boolean` | - | Execute post-create setup tasks. |
| `--post-start` | `boolean` | - | Execute post-start lifecycle tasks. |
| `--all`, `-a` | `boolean` | - | Execute all DevContainer lifecycle tasks. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops devcontainer bootstrap-k8s`

**Execute Minikube cluster startup and Kubernetes stack deployment in the background.**

```bash
devops devcontainer bootstrap-k8s [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | `.` | Workspace root directory path. |
| `--stack`, `-s` | `string` | `infra` | Kubernetes stack to deploy (e.g. infra, llm, monitoring, all). |
| `--deploy`, `--no-deploy` | `boolean` | `True` | Auto-deploy Kubernetes stack after cluster startup. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## devops workspace

Manage multi-root VS Code workspace files (.code-workspace).

### `devops workspace add`

**Add a folder to the VS Code workspace file.**

```bash
devops workspace add [OPTIONS] <repo_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo_path>` | `path` | Yes | Add a repository folder into the VS Code workspace file. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | - | Target VS Code workspace file (.code-workspace or .json). |

### `devops workspace remove`

**Remove a folder from the VS Code workspace file.**

```bash
devops workspace remove [OPTIONS] <repo_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo_path>` | `path` | Yes | Remove a repository folder from the VS Code workspace file. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | - | Target VS Code workspace file (.code-workspace or .json). |

### `devops workspace generate`

**Regenerate the workspace file from all repos in the repos directory.**

```bash
devops workspace generate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |
| `--workspace`, `-w` | `path` | - | Target VS Code workspace file (.code-workspace or .json). |

### `devops workspace open`

**Open the workspace in VS Code.**

```bash
devops workspace open [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | - | Target VS Code workspace file (.code-workspace or .json). |

### `devops workspace clean`

**Clean stale review sessions, old analysis caches, and temporary traces under .data/.**

```bash
devops workspace clean [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--older-than`, `-d` | `integer` | `7` | Prune artifacts older than N days. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## devops install-tools

Install and manage DevOps tool binaries.

### `devops install-tools status`

**Show installation status and versions for all managed tools.**

```bash
devops install-tools status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--target-dir`, `-d` | `path` | `~/.local/bin` | - |

---

## devops k8s

Manage Kubernetes clusters, pods, services, and workloads.

### `devops k8s contexts`

**List kubeconfig contexts and mark the active one.**

```bash
devops k8s contexts
```

### `devops k8s switch-context`

**Switch active kubeconfig context.**

```bash
devops k8s switch-context <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Target context name to switch to. |

### `devops k8s status`

**Show node and pod summary for the current context.**

```bash
devops k8s status
```

### `devops k8s apply`

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

### `devops k8s logs`

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

### `devops k8s bootstrap`

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

### `devops k8s bootstrap-openwebui`

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

### `devops k8s deploy-stack`

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

### `devops k8s sync-secrets`

**Fetch stack admin credentials (ArgoCD, Grafana) from Kubernetes and store in OS Keyring.**

```bash
devops k8s sync-secrets [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `infra` | Stack to operate on: infra | llm | all. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops k8s configure-urls`

**Auto-detect Kubernetes stack URLs and update CLI config.**

```bash
devops k8s configure-urls [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `infra` | Stack to operate on: infra | llm | all. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |

### `devops k8s port-forward`

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

### `devops k8s port-forward-status`

**List active background Kubernetes port-forward daemons.**

```bash
devops k8s port-forward-status
```

### `devops k8s port-forward-stop`

**Terminate active background Kubernetes port-forward daemons.**

```bash
devops k8s port-forward-stop [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--service`, `-s` | `string` | - | Specific service to stop |

### `devops k8s teardown-stack`

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

### `devops k8s rbac-audit`

**Audit RBAC RoleBindings and ServiceAccounts for overprivileged access.**

```bash
devops k8s rbac-audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | - |

### `devops k8s lint`

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

### `devops k8s audit`

**Sanitize active K8s/Minikube cluster resource health using Derailed Popeye.**

```bash
devops k8s audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops k8s check-deprecated`

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

### `devops k8s create-tls-secret`

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

### `devops k8s enable-tls`

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

### `devops k8s validate`

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

### `devops k8s validate-policy`

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

### `devops k8s stream-logs`

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

### `devops k8s diff-helm`

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

### `devops k8s chaos`

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

### `devops k8s pods`

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

## devops kustomize

Kustomize build and apply operations.

### `devops kustomize build`

**Build kustomize overlays (delegates to kustomize build).**

```bash
devops kustomize build [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Target kustomize directory path. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `string` | - | Destination file or directory for generated manifests. |

### `devops kustomize diff`

**Show a diff of pending changes (delegates to kubectl diff -k).**

```bash
devops kustomize diff <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Target kustomize directory path. |

### `devops kustomize apply`

**Apply a kustomization (delegates to kubectl apply -k).**

```bash
devops kustomize apply [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Target kustomize directory path. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |

---

## devops docker

Docker image management.

### `devops docker images`

**List local Docker images.**

```bash
devops docker images [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--name`, `-n` | `string` | - | Filter containers or images by name. |

### `devops docker build`

**Build a Docker image.**

```bash
devops docker build [OPTIONS] <context>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<context>` | `path` | No | Build context directory. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--tag`, `-t` | `string` | - | Image tag name. |
| `--file`, `-f` | `path` | - | Path to Dockerfile. |
| `--no-cache` | `boolean` | - | Do not use cached image layers when building. |

### `devops docker push`

**Push a Docker image to a registry.**

```bash
devops docker push <image>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<image>` | `string` | Yes | Docker image name or repository tag. |

### `devops docker prune`

**Remove unused containers, images, and networks.**

```bash
devops docker prune [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--volumes` | `boolean` | - | Include or prune volumes. |
| `--force`, `-f` | `boolean` | - | Force execution ignoring non-blocking warnings. |

### `devops docker stats`

**Display live container CPU, memory, and network I/O statistics.**

```bash
devops docker stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--name`, `-n` | `string` | - | Filter containers or images by name. |
| `--watch`, `-w` | `boolean` | - | Continuously refresh output in the terminal at a fixed interval. |
| `--interval`, `-i` | `float` | `2.0` | Auto-refresh polling interval in seconds. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops docker analyze-layers`

**Analyze container image layer efficiency and wasted space using Dive.**

```bash
devops docker analyze-layers [OPTIONS] <image>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<image>` | `string` | Yes | Docker image name or repository tag. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops docker sandbox`

**Execute workload inside an isolated, disposable Docker container sandbox.**

```bash
devops docker sandbox [OPTIONS] <command>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<command>` | `string` | Yes | Workload command to execute inside container sandbox |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--image`, `-i` | `string` | `python:3.14-slim` | Docker container image to execute within |
| `--workspace`, `-w` | `path` | `.` | Workspace directory to mount |
| `--memory`, `-m` | `string` | `2g` | Memory limit (e.g. 2g, 512m) |
| `--cpus`, `-c` | `float` | `2.0` | CPU limit |
| `--network`, `-n` | `string` | `bridge` | Network mode: bridge | none | host |
| `--read-only` | `boolean` | - | Mount workspace as read-only |
| `--rootless`, `--root` | `boolean` | `True` | Run container with host user UID/GID |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## devops grafana

Grafana dashboard and alert management.

### `devops grafana search`

**Search Grafana dashboards and folders by query string.**

```bash
devops grafana search [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--query`, `-q` | `string` | `` | Search query. |

### `devops grafana datasources`

**List configured datasources.**

```bash
devops grafana datasources
```

### `devops grafana alerts`

**List alert rules (Grafana 9+ unified alerting).**

```bash
devops grafana alerts
```

### `devops grafana dashboards`

```bash
devops grafana dashboards COMMAND [ARGS]...
```

#### `devops grafana dashboards list`

**List all dashboards.**

```bash
devops grafana dashboards list
```

#### `devops grafana dashboards export`

**Export a dashboard to JSON.**

```bash
devops grafana dashboards export [OPTIONS] <uid>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<uid>` | `string` | Yes | Dashboard UID. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Destination path for output report or artifacts. |

#### `devops grafana dashboards import`

**Import a dashboard from JSON.**

```bash
devops grafana dashboards import [OPTIONS] <file>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<file>` | `path` | Yes | Path to dashboard JSON file to import. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--folder-id` | `integer` | `0` | Target Grafana folder ID for dashboard import. |

#### `devops grafana dashboards sync`

**Sync all bundled/local dashboards to Grafana.**

```bash
devops grafana dashboards sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | - | Directory path containing dashboard definitions. |

---

## devops prometheus

Prometheus metrics querying and analysis.

### `devops prometheus query`

**Execute an instant PromQL query.**

```bash
devops prometheus query [OPTIONS] <expr>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<expr>` | `string` | Yes | PromQL expression. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--time`, `-t` | `string` | - | Evaluation timestamp for instant vector query. |

### `devops prometheus query-range`

**Execute a range PromQL query and summarise the result.**

```bash
devops prometheus query-range [OPTIONS] <expr>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<expr>` | `string` | Yes | PromQL expression. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--start`, `-s` | `string` | `1h` | Start: duration ago (e.g. 1h) or Unix ts. |
| `--end`, `-e` | `string` | - | Query range end timestamp or relative duration. |
| `--step` | `string` | `60s` | Query resolution step interval. |

### `devops prometheus rules`

**List Prometheus recording and alerting rules.**

```bash
devops prometheus rules
```

### `devops prometheus targets`

**List active Prometheus scrape targets.**

```bash
devops prometheus targets
```

---

## devops argo

Argo CD, Workflows, and Rollouts management.

### `devops argo cd`

```bash
devops argo cd COMMAND [ARGS]...
```

#### `devops argo cd apps`

```bash
devops argo cd apps COMMAND [ARGS]...
```

##### `devops argo cd apps list`

**List all ArgoCD applications.**

```bash
devops argo cd apps list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--watch`, `-w` | `boolean` | - | Watch application status changes live. |
| `--interval`, `-i` | `float` | `3.0` | Auto-refresh polling interval in seconds. |

##### `devops argo cd apps sync`

**Trigger a sync for an ArgoCD application.**

```bash
devops argo cd apps sync [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Application name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--prune` | `boolean` | - | Allow deletion of resources omitted from the source repository. |
| `--force` | `boolean` | - | Force execution ignoring non-blocking warnings. |

##### `devops argo cd apps status`

**Show sync and health status for an ArgoCD application.**

```bash
devops argo cd apps status [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Application name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--watch`, `-w` | `boolean` | - | Watch application status changes live. |
| `--interval`, `-i` | `float` | `3.0` | Auto-refresh polling interval in seconds. |

##### `devops argo cd apps bootstrap-gitops`

**Bootstrap local GitOps project orchestration via ArgoCD and the Git daemon.**

```bash
devops argo cd apps bootstrap-gitops [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--root-app`, `-f` | `path` | `k8s/argocd/apps/root-app.yaml` | Path to root ArgoCD App-of-Apps manifest. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |

### `devops argo workflows`

```bash
devops argo workflows COMMAND [ARGS]...
```

#### `devops argo workflows list`

**List Argo Workflows.**

```bash
devops argo workflows list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |

#### `devops argo workflows submit`

**Submit an Argo Workflow from a YAML file.**

```bash
devops argo workflows submit [OPTIONS] <file>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<file>` | `path` | Yes | Workflow YAML file. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |
| `--wait`, `-w` | `boolean` | - | Wait for sync operation to finish. |

#### `devops argo workflows logs`

**Stream logs for an Argo Workflow.**

```bash
devops argo workflows logs [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Workflow name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |
| `--follow`, `-f` | `boolean` | - | Stream workflow execution logs. |

### `devops argo rollouts`

```bash
devops argo rollouts COMMAND [ARGS]...
```

#### `devops argo rollouts list`

**List Argo Rollouts.**

```bash
devops argo rollouts list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |

#### `devops argo rollouts status`

**Show status for an Argo Rollout.**

```bash
devops argo rollouts status [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Rollout name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |
| `--watch`, `-w` | `boolean` | - | Watch application status changes live. |

---

## devops config

Show, set, get, or initialize CLI configuration.

### `devops config show`

**Print all configuration values, masking secrets.**

```bash
devops config show
```

### `devops config get`

**Print a single configuration value.**

```bash
devops config get <key>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<key>` | `string` | Yes | Dotted config key, e.g. github.default_org. |

### `devops config set`

**Set a configuration value. Tokens are stored in the OS keyring.**

```bash
devops config set <key> <value>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<key>` | `string` | Yes | Dotted config key, e.g. github.default_org. |
| `<value>` | `string` | Yes | Value to set. |

### `devops config init`

**Interactive first-time setup wizard.**

```bash
devops config init
```

### `devops config env-vars`

**Output environment variables available for devops-cli configuration.**

```bash
devops config env-vars [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--export`, `-e` | `boolean` | - | Print environment variables as shell export statements. |
| `--json`, `-j` | `boolean` | - | Print environment variables as JSON. |

### `devops config env`

**Output environment variables available for devops-cli configuration.**

```bash
devops config env [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--export`, `-e` | `boolean` | - | Print environment variables as shell export statements. |
| `--json`, `-j` | `boolean` | - | Print environment variables as JSON. |

### `devops config output`

**Output environment variables available for devops-cli configuration.**

```bash
devops config output [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--export`, `-e` | `boolean` | - | Print environment variables as shell export statements. |
| `--json`, `-j` | `boolean` | - | Print environment variables as JSON. |

### `devops config auth-headless`

**Load secret tokens into ephemeral memory for headless CI environments lacking DBus.**

```bash
devops config auth-headless <key> <token>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<key>` | `string` | Yes | Dotted secret key, e.g. github.token. |
| `<token>` | `string` | Yes | Secret token string. |

### `devops config audit-stream`

**Stream stored audit records to SIEM destination URL.**

```bash
devops config audit-stream <destination>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<destination>` | `string` | Yes | Destination Syslog or HTTP URL. |

### `devops config audit-keys`

**Audit OS Keyring token health, backend status, and zero-plaintext secret compliance.**

```bash
devops config audit-keys [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## devops ci

Run tests, linting, formatting, and type-checks.

### `devops ci test`

**Run the pytest test suite in parallel leveraging all CPU cores.**

```bash
devops ci test [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--verbose`, `-v` | `boolean` | - | Enable detailed logging output. |
| `-k` | `string` | - | Filter tests by keyword expression. |
| `-x` | `boolean` | - | Stop after first failure. |
| `-n`, `--numprocesses` | `string` | `auto` | Number of parallel worker processes. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci coverage`

**Run pytest with parallel code coverage analysis over src/.**

```bash
devops ci coverage [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--html` | `boolean` | - | Generate HTML coverage report in .data/htmlcov/. |
| `--xml` | `boolean` | - | Generate XML coverage report in .data/coverage.xml. |
| `-n`, `--numprocesses` | `string` | `auto` | Number of parallel worker processes. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci lint`

**Run ruff linter across the project.**

```bash
devops ci lint [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` | `boolean` | - | Auto-fix violations where possible. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci format`

**Check (or apply) code formatting with ruff format.**

```bash
devops ci format [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` | `boolean` | - | Apply formatting changes in-place. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci typecheck`

**Run mypy static type-checker strictly targeting Python 3.14 over src/.**

```bash
devops ci typecheck [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci audit`

**Run uv audit to check for known package vulnerabilities.**

```bash
devops ci audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci security`

**Run bandit static security vulnerability analysis over src/.**

```bash
devops ci security [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--severity`, `-s` | `string` | `medium` | Minimum severity threshold (low, medium, high). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci actionlint`

**Run actionlint to validate GitHub Actions workflows for syntax and schema errors.**

```bash
devops ci actionlint [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci docs`

**Verify (or update with --fix) that documentation is up to date with CLI commands and configuration.**

```bash
devops ci docs [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` | `boolean` | - | Synchronize Complete Command Matrix in README.md. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci maintain`

**Run automated toolchain, dependency freshness, and lockfile maintenance checks.**

```bash
devops ci maintain [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` | `boolean` | - | Automatically synchronize dependencies and lockfile. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci run`

**Run full CI and return a single pass/fail status.**

```bash
devops ci run [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix`, `--no-fix` | `boolean` | `True` | Auto-fix lint/format before reporting status. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## devops uv

uv dependency management proxies.

### `devops uv sync`

**Sync project dependencies into the virtual environment.**

```bash
devops uv sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--frozen` | `boolean` | - | Do not update lockfile. |

### `devops uv lock`

**Regenerate the uv lockfile.**

```bash
devops uv lock [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--upgrade` | `boolean` | - | Upgrade dependencies while locking. |

### `devops uv python-install`

**Install project Python version with uv.**

```bash
devops uv python-install [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Python version to install (defaults to .python-version). |

### `devops uv run`

**Run an arbitrary command using `uv run`.**

Run an arbitrary command using `uv run`.

Example:
  devops uv run -- pytest -q

```bash
devops uv run
```

---

## devops scan

Security scanner suite: Trivy, Gitleaks, Semgrep, Checkov, Kubeconform.

### `devops scan trivy`

**Run Aqua Trivy vulnerability, secret, and misconfiguration scan.**

```bash
devops scan trivy [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory, file, or repository to scan. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--type`, `-t` | `string` | `fs` | Trivy scan mode: fs, image, iac, repo. |
| `--severity`, `-s` | `string` | `UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL` | Comma-separated severity levels to include. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops scan secrets`

**Run Gitleaks secret pre-filter scan across workspace or targets.**

```bash
devops scan secrets [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or file to scan for secrets. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops scan gitleaks`

**Alias for devops scan secrets.**

```bash
devops scan gitleaks [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or file to scan for secrets. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops scan semgrep`

**Run Semgrep multilingual static AST pattern matching scan.**

```bash
devops scan semgrep [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or file to scan with Semgrep AST rules. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--config`, `-c` | `string` | `p/default` | Semgrep ruleset config (e.g. p/default, p/security-audit). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops scan sast`

**Run static application security testing (SAST) via Semgrep.**

```bash
devops scan sast [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or file to scan with Semgrep AST rules. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--config`, `-c` | `string` | `p/default` | Semgrep ruleset config (e.g. p/default, p/security-audit). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops scan checkov`

**Run Checkov Infrastructure-as-Code (IaC) compliance scanner.**

```bash
devops scan checkov [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or file to scan with Checkov IaC rules. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--framework`, `-f` | `string` | - | Specific IaC framework (e.g. terraform). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops scan iac`

**Run Checkov IaC static policy and security compliance scan.**

```bash
devops scan iac [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or file to scan with Checkov IaC rules. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--framework`, `-f` | `string` | - | Specific IaC framework (e.g. terraform). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops scan complexity`

**Run AST-based cyclomatic complexity and indentation depth analysis.**

```bash
devops scan complexity [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or Python file to analyze for complexity. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--max-complexity`, `-c` | `integer` | `10` | Maximum acceptable cyclomatic complexity per function (default 10). |
| `--max-indent`, `-i` | `integer` | `5` | Maximum acceptable indentation / nesting depth (default 5). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops scan sbom`

**Generate Software Bill of Materials (SBOM) in CycloneDX, SPDX, or JSON format.**

```bash
devops scan sbom [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory, file, or repository to scan. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `cyclonedx` | SBOM format output (cyclonedx, spdx, json). |
| `--output`, `-o` | `path` | - | Destination file path for generated SBOM document. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops scan aibom`

**Generate AI Bill of Materials (AIBOM) with model licenses and hardware estimates.**

```bash
devops scan aibom [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or model repository to analyze for AI models and AIBOM. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `cyclonedx` | AIBOM format output (cyclonedx, json). |
| `--output`, `-o` | `path` | - | Destination file path for generated AIBOM manifest. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops scan fix`

**Remediate vulnerable dependencies via lockfile upgrades and optional git branch creation.**

```bash
devops scan fix [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target project directory containing lockfile or dependencies |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--package`, `-p` | `string` | - | Specific vulnerable package to remediate |
| `--min-severity`, `-s` | `string` | `HIGH` | Minimum vulnerability severity (LOW|MEDIUM|HIGH|CRITICAL) |
| `--apply` | `boolean` | - | Apply lockfile upgrades directly |
| `--create-branch`, `-b` | `boolean` | - | Create a git topic branch for the remediation |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## devops ai

Configure, test, chat, analyze, and review codebases (Ollama, Claude, Copilot).

### `devops ai config`

**Show or update AI provider configuration.**

```bash
devops ai config [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--provider`, `-p` | `string` | - | Provider: ollama, claude, copilot, openai |
| `--model`, `-m` | `string` | - | AI model identifier. |
| `--ollama-urls` | `string` | - | Ollama server base URLs (comma-separated). |
| `--ollama-max-parallel` | `integer` | - | Maximum number of simultaneous requests allowed per Ollama server node. |
| `--api-base-url` | `string` | - | Override API base URL for any provider. |
| `--api-key` | `string` | - | API key — stored in OS keyring, not config file. |
| `--max-retries` | `integer` | - | Maximum retry count for AI requests upon failure. |

### `devops ai models`

**List available models for the configured provider.**

```bash
devops ai models
```

### `devops ai preload`

**Preload configured model into VRAM across all configured Ollama servers.**

```bash
devops ai preload
```

### `devops ai test`

**Send a test prompt to verify AI provider connectivity across configured servers.**

```bash
devops ai test [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--prompt`, `-p` | `string` | `Hello, world!` | Test prompt to send to the provider. |
| `--url`, `-u` | `string` | - | Specific Ollama server URL to test. |

### `devops ai agents`

**Generate LLM/Agent instruction files (AGENTS.md, CLAUDE.md, copilot-instructions.md).**

```bash
devops ai agents [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `path` | `.` | Repository root directory (default: current directory). |
| `--template` | `boolean` | - | Generate from built-in template without calling the LLM. |
| `--file`, `-f` | `string` | `['AGENTS.md', 'CLAUDE.md', '.github/copilot-instructions.md']` | Files to generate (repeatable). |

### `devops ai chat`

**Start an interactive chat with a Pydantic AI persona (tools, thinking, streaming, RAG).**

```bash
devops ai chat [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--persona`, `-p` | `string` | `architect` | Persona to chat with: devsecops, architect, pm, auditor, qa, challenger |
| `--context`, `-c` | `path` | - | Optional file to inject as background context (e.g. AGENTS.md). |
| `--rag`, `--no-rag` | `boolean` | `True` | Retrieve relevant semantic RAG context. |
| `--stream`, `--no-stream` | `boolean` | `True` | Stream response tokens. |
| `--tools`, `--no-tools` | `boolean` | `True` | Enable DevOps agent tools. |
| `--thinking`, `--no-thinking` | `boolean` | `True` | Enable model reasoning/thinking. |
| `--prewarm`, `--no-prewarm` | `boolean` | `True` | Prewarm the model before starting chat. |
| `--explain`, `-e` | `boolean` | - | Explain chat personas, tools, and reasoning modes. |

### `devops ai bundle-models`

**Bundle Ollama model metadata into tarball for air-gapped DevContainers.**

```bash
devops ai bundle-models [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Directory path for generated output files. |

### `devops ai pipeline`

**Run a multi-agent Pydantic pipeline with shared DevOps tools and RAG context.**

```bash
devops ai pipeline [OPTIONS] <prompt>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<prompt>` | `string` | No | Initial goal or prompt for the multi-agent pipeline. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--personas`, `-p` | `string` | `devsecops,architect,qa` | Comma-separated persona pipeline sequence (e.g. devsecops,architect,qa). |
| `--max-turns` | `integer` | `5` | Maximum tool turns per agent stage. |
| `--rag`, `--no-rag` | `boolean` | `True` | Retrieve relevant semantic RAG context. |
| `--thinking`, `--no-thinking` | `boolean` | `True` | Enable model reasoning/thinking. |

### `devops ai token-count`

**Calculate exact BPE tokens for text or files using tiktoken context budgeting.**

```bash
devops ai token-count [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `string` | No | File path or text string to calculate tokens for. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--model`, `-m` | `string` | `gpt-4o` | AI model identifier. |
| `--budget`, `-b` | `integer` | `32768` | Max context token budget limit. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops ai route`

**Evaluate task complexity and determine the optimal LLM provider and model route.**

```bash
devops ai route [OPTIONS] <task>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<task>` | `string` | Yes | Task name (e.g. review, scan). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--tokens`, `-t` | `integer` | `<masked>` | Estimated tokens. |
| `--frontier`, `-f` | `boolean` | - | Force routing to frontier tier models. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops ai spec`

**Verify codebase against executable markdown architecture specification contracts.**

```bash
devops ai spec [OPTIONS] <spec_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<spec_path>` | `path` | No | Path to markdown architecture specification contract. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--target`, `-t` | `path` | - | Target source directory to verify or analyze. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops ai repomap`

**Generate compact whole-repository AST symbol and relationship map.**

```bash
devops ai repomap [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--target`, `-t`, `--dir`, `-d` | `path` | - | Target source directory to verify or analyze. |
| `--max-files`, `-n` | `integer` | `100` | Maximum source files to include. |
| `--include-tests` | `boolean` | - | Include test modules in symbol map. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai diagram`

**Generate visual Mermaid architecture topology or STRIDE threat modeling diagrams.**

```bash
devops ai diagram [OPTIONS] <diagram_type>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<diagram_type>` | `string` | No | Diagram type: 'arch' for architecture topology, 'threat' for STRIDE model. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--target`, `-t`, `--dir`, `-d` | `path` | - | Target source directory to verify or analyze. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai prompt-eval`

**Benchmark persona prompt variations against verified review feedback datasets.**

```bash
devops ai prompt-eval [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--persona`, `-p` | `string` | `devsecops` | Evaluate and benchmark code review quality against feedback dataset. |
| `--dataset`, `-d` | `path` | - | Path to feedback dataset jsonl. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai test-gen`

**Synthesize isolated pytest unit test suites for functions or source files.**

```bash
devops ai test-gen [OPTIONS] <target_file>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target_file>` | `path` | Yes | Target source file to synthesize unit tests for. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--function`, `-f` | `string` | - | Specific function to synthesize tests for. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai review`

**AI-powered multi-persona code review system.**

```bash
devops ai review [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |

#### `devops ai review path`

**Review source files directly (no git required).**

```bash
devops ai review path [OPTIONS] <targets>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<targets>` | `path` | No | File(s) or directory(ies) to review. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--pattern`, `-g` | `string` | `*` | Glob pattern for matching files. |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Reviewer persona to activate (devsecops, architect, pm, auditor, qa). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and adversarial debate. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--watch`, `-w` | `boolean` | - | Continuously watch target paths for changes and re-run reviews. |
| `--debounce-ms` | `integer` | `500` | Debounce window in milliseconds for filesystem watcher. |

#### `devops ai review branch`

**Review a git branch diff with one or all AI personas.**

```bash
devops ai review branch [OPTIONS] <branch_name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<branch_name>` | `string` | No | Branch to review (default: current branch). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-b` | `string` | `main` | Base git branch to diff against (default: main). |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Reviewer persona to activate (devsecops, architect, pm, auditor, qa). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--repo` | `path` | `.` | Repository root directory (default: current directory). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and adversarial debate. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |

#### `devops ai review pr`

**Review a GitHub pull request with one or all AI personas.**

```bash
devops ai review pr [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `string` | - | Target repository in OWNER/REPO format. |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Reviewer persona to activate (devsecops, architect, pm, auditor, qa). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--post` | `boolean` | - | Post the review as a comment on the GitHub PR. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and adversarial debate. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |

#### `devops ai review findings`

**Inspect structured findings for a review session.**

```bash
devops ai review findings [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | No | Session ID or substring (default: latest). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Session ID or substring (default: latest). |
| `--status` | `string` | - | Filter by status: VERIFIED | UNVERIFIED | INVALIDATED | MITIGATED. |
| `--unverified` | `boolean` | - | Show unverified findings only. |
| `--invalidated` | `boolean` | - | Show invalidated findings only. |
| `--verified` | `boolean` | - | Show verified findings only. |
| `--details`, `-d` | `boolean` | - | Display full finding descriptions and fix recommendations. |

#### `devops ai review verify`

**Validate or invalidate a review finding, persisting feedback reasons.**

```bash
devops ai review verify [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | No | Session ID or substring (default: latest). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Session ID or substring (default: latest). |
| `--index`, `-i` | `integer` | - | 1-based finding index in session to verify. |
| `--title`, `-t` | `string` | - | Match finding by substring in title. |
| `--status` | `string` | `INVALIDATED` | Target status: VERIFIED | INVALIDATED | MITIGATED | UNVERIFIED. |
| `--reason`, `-r` | `string` | `` | Explanation or justification for the status change. |

#### `devops ai review stats`

**Compute and display review accuracy statistics across saved sessions.**

```bash
devops ai review stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--reviews-dir` | `path` | - | Directory containing review sessions. |

#### `devops ai review export-feedback`

**Export review findings into a JSONL benchmark dataset for prompt tuning and fine-tuning.**

```bash
devops ai review export-feedback [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Output JSONL path for benchmark feedback dataset. |
| `--reviews-dir` | `path` | - | Directory containing review sessions. |
| `--status`, `-s` | `string` | `INVALIDATED` | Finding status to export: INVALIDATED, VERIFIED, MITIGATED, or ALL. |

#### `devops ai review apply-patch`

**Apply suggested LLM code fix for a verified finding.**

```bash
devops ai review apply-patch [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | Yes | Session ID or substring (default: latest). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--index`, `-idx` | `integer` | `1` | 1-based finding index in session to verify. |
| `--interactive`, `-i` | `boolean` | - | Preview patch diff interactively. |

#### `devops ai review auto-fix`

**Create a corrective topic branch with verified unit test patch for an approved finding.**

```bash
devops ai review auto-fix [OPTIONS] <finding_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<finding_id>` | `string` | Yes | Finding ID or title to create remediation branch for. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--file`, `-f` | `string` | `src/devops_cli/main.py` | Target source file to apply fix to. |
| `--branch`, `-b` | `string` | - | Custom topic branch name. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops ai analyze`

**Analyze codebase metadata and generate structural outlines.**

```bash
devops ai analyze [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology. |

#### `devops ai analyze path`

**Analyze all repository files under target path and save metadata to .data/analysis/.**

```bash
devops ai analyze path [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | File or directory path to analyze. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--pattern`, `-g` | `string` | `*` | Glob pattern for matching files. |
| `--enhanced`, `-e`, `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated). |
| `--update-all`, `-u` | `boolean` | - | Regenerate all enhanced metadata fields regardless of last_* timestamps. |
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology. |

#### `devops ai analyze branch`

**Analyze a git branch diff against base and save metadata to .data/analysis/.**

```bash
devops ai analyze branch [OPTIONS] <branch>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<branch>` | `string` | No | Branch to analyze (default: active branch). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-b` | `string` | `main` | Base git branch to diff against (default: main). |
| `--enhanced`, `-e`, `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated). |
| `--update-all`, `-u` | `boolean` | - | Regenerate all enhanced metadata fields regardless of last_* timestamps. |
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology. |

#### `devops ai analyze pr`

**Analyze a GitHub Pull Request and save metadata to .data/analysis/.**

```bash
devops ai analyze pr [OPTIONS] <pr_number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<pr_number>` | `integer` | Yes | GitHub PR number to analyze. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--enhanced`, `-e`, `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated). |
| `--update-all`, `-u` | `boolean` | - | Regenerate all enhanced metadata fields regardless of last_* timestamps. |
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology. |

### `devops ai rag`

**Manage RAG vector embeddings, indexing, and semantic search (Qdrant).**

```bash
devops ai rag [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--explain`, `-e` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology. |

#### `devops ai rag index`

**Scan and index workspace code and documentation into Qdrant vector database.**

```bash
devops ai rag index [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Directory or file to index into vector store. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--project`, `-p` | `string` | - | Project / repository name override. |
| `--force`, `-f` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--include-kb`, `--no-include-kb` | `boolean` | `True` | Include bundled DevOps CLI Knowledge Base in docs collection. |
| `--collection`, `-c` | `string` | - | Target collection override. |
| `--explain`, `-e` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology. |

#### `devops ai rag index-kb`

**Index the bundled DevOps CLI Knowledge Base into Qdrant for RAG agent retrieval.**

```bash
devops ai rag index-kb [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--force`, `-f` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--collection`, `-c` | `string` | - | Target collection override. |
| `--explain`, `-e` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology. |

#### `devops ai rag search`

**Perform semantic search across indexed workspace code and documentation.**

```bash
devops ai rag search [OPTIONS] <query>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<query>` | `string` | Yes | Natural language query or code search term. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--project`, `-p` | `string` | - | Project / repository name override. |
| `--language`, `-l` | `string` | - | Filter or target specific programming language. |
| `--category`, `-c` | `string` | - | Filter by category (code, docs, topics, tasks). |
| `--top-k`, `-k` | `integer` | `5` | Number of results to return. |
| `--min-score`, `-s` | `float` | `0.35` | Minimum similarity score (0.0 - 1.0). |
| `--collection` | `string` | - | Target collection override. |
| `--file`, `-f` | `string` | - | Filter by filepath glob pattern. |
| `--explain` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology. |

#### `devops ai rag query`

**Perform semantic search across indexed workspace code and documentation.**

```bash
devops ai rag query [OPTIONS] <query>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<query>` | `string` | Yes | Natural language query or code search term. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--project`, `-p` | `string` | - | Project / repository name override. |
| `--language`, `-l` | `string` | - | Filter or target specific programming language. |
| `--category`, `-c` | `string` | - | Filter by category (code, docs, topics, tasks). |
| `--top-k`, `-k` | `integer` | `5` | Number of results to return. |
| `--min-score`, `-s` | `float` | `0.35` | Minimum similarity score (0.0 - 1.0). |
| `--collection` | `string` | - | Target collection override. |
| `--file`, `-f` | `string` | - | Filter by filepath glob pattern. |
| `--explain` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology. |

#### `devops ai rag status`

**Display status of vector database collections and embedding configurations.**

```bash
devops ai rag status
```

#### `devops ai rag reset`

**Alias for clear — clear vector index collections and reset local cache.**

```bash
devops ai rag reset [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--collection`, `-c` | `string` | - | Target collection override. |
| `--force`, `-f` | `boolean` | - | Force execution ignoring non-blocking warnings. |

#### `devops ai rag clear`

**Clear vector index collections from Qdrant.**

```bash
devops ai rag clear [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--collection`, `-c` | `string` | - | Target collection override. |
| `--force`, `-f` | `boolean` | - | Force execution ignoring non-blocking warnings. |

### `devops ai benchmark`

**Benchmark, evaluate, and peer-grade candidate AI models across engineering tasks.**

```bash
devops ai benchmark [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--models`, `-m` | `string` | - | Comma-separated candidate models (e.g. 'qwen2.5:0.5b,llama3.1:8b@http://gpu2:11434'). |
| `--servers`, `--ollama-urls` | `string` | - | Comma-separated Ollama server URLs for concurrent execution (e.g. 'http://node1:11434,http://node2:11434'). |
| `--provider`, `-p` | `string` | - | AI or cloud provider. |
| `--type`, `--mode` | `string` | `auto` | Benchmark mode: 'auto', 'chat', 'embedding'. |
| `--tasks`, `-t` | `string` | - | Filter specific task categories or IDs (e.g. 'security,kubernetes'). |
| `--concurrency`, `-c` | `integer` | `4` | Number of concurrent model server workers (default: automatic per model count). |
| `--output`, `-o` | `path` | - | Destination path for output report or artifacts. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--explain`, `-e` | `boolean` | - | Explain benchmark metrics, terminology, and mathematical formulas. |
| `--document`, `-d` | `path` | - | Path to large test document for in-memory tokenization and section retrieval. |
| `--samples` | `integer` | `5` | Number of random sections to sample for retrieval evaluation. |

### `devops ai cache`

**Manage LLM response cache, performance metrics, and warm starting points.**

```bash
devops ai cache COMMAND [ARGS]...
```

#### `devops ai cache status`

**Display LLM response cache performance statistics, hit rates, and disk storage.**

```bash
devops ai cache status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

#### `devops ai cache clear`

**Purge all in-memory and persistent disk cache entries.**

```bash
devops ai cache clear
```

---

## devops review

AI-powered multi-persona code review and security audits.

### `devops review path`

**Review source files directly (no git required).**

```bash
devops review path [OPTIONS] <targets>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<targets>` | `path` | No | File(s) or directory(ies) to review. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--pattern`, `-g` | `string` | `*` | Glob pattern for matching files. |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Reviewer persona to activate (devsecops, architect, pm, auditor, qa). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and adversarial debate. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--watch`, `-w` | `boolean` | - | Continuously watch target paths for changes and re-run reviews. |
| `--debounce-ms` | `integer` | `500` | Debounce window in milliseconds for filesystem watcher. |

### `devops review branch`

**Review a git branch diff with one or all AI personas.**

```bash
devops review branch [OPTIONS] <branch_name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<branch_name>` | `string` | No | Branch to review (default: current branch). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-b` | `string` | `main` | Base git branch to diff against (default: main). |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Reviewer persona to activate (devsecops, architect, pm, auditor, qa). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--repo` | `path` | `.` | Repository root directory (default: current directory). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and adversarial debate. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |

### `devops review pr`

**Review a GitHub pull request with one or all AI personas.**

```bash
devops review pr [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `string` | - | Target repository in OWNER/REPO format. |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Reviewer persona to activate (devsecops, architect, pm, auditor, qa). |
| `--all` | `boolean` | - | Run all reviewer personas in sequence. |
| `--post` | `boolean` | - | Post the review as a comment on the GitHub PR. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and adversarial debate. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |

### `devops review findings`

**Inspect structured findings for a review session.**

```bash
devops review findings [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | No | Session ID or substring (default: latest). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Session ID or substring (default: latest). |
| `--status` | `string` | - | Filter by status: VERIFIED | UNVERIFIED | INVALIDATED | MITIGATED. |
| `--unverified` | `boolean` | - | Show unverified findings only. |
| `--invalidated` | `boolean` | - | Show invalidated findings only. |
| `--verified` | `boolean` | - | Show verified findings only. |
| `--details`, `-d` | `boolean` | - | Display full finding descriptions and fix recommendations. |

### `devops review verify`

**Validate or invalidate a review finding, persisting feedback reasons.**

```bash
devops review verify [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | No | Session ID or substring (default: latest). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Session ID or substring (default: latest). |
| `--index`, `-i` | `integer` | - | 1-based finding index in session to verify. |
| `--title`, `-t` | `string` | - | Match finding by substring in title. |
| `--status` | `string` | `INVALIDATED` | Target status: VERIFIED | INVALIDATED | MITIGATED | UNVERIFIED. |
| `--reason`, `-r` | `string` | `` | Explanation or justification for the status change. |

### `devops review stats`

**Compute and display review accuracy statistics across saved sessions.**

```bash
devops review stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--reviews-dir` | `path` | - | Directory containing review sessions. |

### `devops review export-feedback`

**Export review findings into a JSONL benchmark dataset for prompt tuning and fine-tuning.**

```bash
devops review export-feedback [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Output JSONL path for benchmark feedback dataset. |
| `--reviews-dir` | `path` | - | Directory containing review sessions. |
| `--status`, `-s` | `string` | `INVALIDATED` | Finding status to export: INVALIDATED, VERIFIED, MITIGATED, or ALL. |

### `devops review apply-patch`

**Apply suggested LLM code fix for a verified finding.**

```bash
devops review apply-patch [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | Yes | Session ID or substring (default: latest). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--index`, `-idx` | `integer` | `1` | 1-based finding index in session to verify. |
| `--interactive`, `-i` | `boolean` | - | Preview patch diff interactively. |

### `devops review auto-fix`

**Create a corrective topic branch with verified unit test patch for an approved finding.**

```bash
devops review auto-fix [OPTIONS] <finding_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<finding_id>` | `string` | Yes | Finding ID or title to create remediation branch for. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--file`, `-f` | `string` | `src/devops_cli/main.py` | Target source file to apply fix to. |
| `--branch`, `-b` | `string` | - | Custom topic branch name. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---

## devops mcp

FastMCP server and Model Context Protocol integrations.

### `devops mcp serve`

**Launch FastMCP server to expose devops-cli tools to MCP clients.**

```bash
devops mcp serve [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--transport`, `-t` | `string` | `stdio` | Transport protocol for FastMCP server (stdio | sse). |
| `--host`, `-h` | `string` | `127.0.0.1` | Host interface for SSE transport. |
| `--port`, `-p` | `integer` | `8000` | Port number for SSE transport. |
| `--allow-remote` | `boolean` | - | Permit binding SSE transport to non-loopback network interfaces. |

### `devops mcp tools`

**List all registered FastMCP tools and descriptions.**

```bash
devops mcp tools
```

---

## devops docs

Generate and validate CLI and architecture documentation.

### `devops docs generate`

**Generate comprehensive Markdown or JSON documentation for all CLI commands and tools.**

```bash
devops docs generate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | - | Target directory for generated documentation files (default: docs/). |
| `--format`, `-f` | `string` | `markdown` | Output format type (table, json, yaml, markdown). |
| `--sync-readme`, `--no-sync-readme` | `boolean` | `True` | Synchronize Complete Command Matrix in README.md. |
| `--check` | `boolean` | - | Verify that documentation is strictly up to date with CLI code. |

### `devops docs check`

**Check that generated documentation and README.md are up to date with codebase.**

```bash
devops docs check [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | - | Target directory for generated documentation files (default: docs/). |
| `--check-readme`, `--no-check-readme` | `boolean` | `True` | Synchronize Complete Command Matrix in README.md. |

### `devops docs sync-readme`

**Synchronize the Complete Command Matrix table in README.md with live CLI commands.**

```bash
devops docs sync-readme [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--readme-path`, `-r` | `path` | - | Path to README.md file (default: workspace root README.md). |
| `--check` | `boolean` | - | Verify that documentation is strictly up to date with CLI code. |

---

## devops release

Automate version bumps, changelogs, tags, and GitHub releases.

### `devops release status`

**Display current release status, versions, tags, changelog, and docs state.**

```bash
devops release status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--root`, `-r` | `path` | - | Project repository root directory. |
| `--watch`, `-w` | `boolean` | - | Continuously monitor release state in real-time. |
| `--interval`, `-i` | `float` | `2.0` | Watcher auto-refresh polling interval in seconds. |

### `devops release prepare`

**Bump version across pyproject.toml and source, update changelog, and sync docs.**

```bash
devops release prepare [OPTIONS] <version>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<version>` | `string` | Yes | Target semantic version (e.g., 0.1.8). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--sync-docs`, `--no-sync-docs` | `boolean` | `True` | Regenerate CLI reference docs and sync README matrix. |
| `--changelog`, `--no-changelog` | `boolean` | `True` | Ensure CHANGELOG.md contains release header with current date. |
| `--create-pr`, `-p` | `boolean` | - | Create release branch, commit changes, and open a GitHub Release PR. |
| `--type`, `-t` | `string` | `feat` | Conventional commit prefix (feat or fix). |
| `--breaking`, `-b` | `boolean` | - | Flag release as containing breaking changes (!). |
| `--root`, `-r` | `path` | - | Project repository root directory. |

### `devops release pr`

**Create release branch, commit version bumps, and open a GitHub Release Pull Request.**

```bash
devops release pr [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Target version string. |
| `--base`, `-b` | `string` | `main` | Base git branch to diff against (default: main). |
| `--draft` | `boolean` | - | Create pull request or entity as draft. |
| `--labels`, `-l` | `string` | `release` | Comma-separated labels to attach. |
| `--push`, `--no-push` | `boolean` | `True` | Push commits or tags to git remote. |
| `--type`, `-t` | `string` | `feat` | Conventional commit prefix (feat or fix). |
| `--breaking`, `-b` | `boolean` | - | Flag release as containing breaking changes (!). |
| `--root`, `-r` | `path` | - | Project repository root directory. |

### `devops release check`

**Verify release readiness (version consistency, docs freshness, and CI quality gates).**

```bash
devops release check [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--skip-ci` | `boolean` | - | Skip running the 7-gate CI test suite. |
| `--allow-dirty` | `boolean` | - | Allow uncommitted changes in git repository. |
| `--root`, `-r` | `path` | - | Project repository root directory. |

### `devops release notes`

**Print markdown release notes for a specified or current release version.**

```bash
devops release notes [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Target version string. |
| `--raw` | `boolean` | - | Output raw string without formatting or shell escapes. |
| `--root`, `-r` | `path` | - | Project repository root directory. |

### `devops release tag`

**Create release commit and annotated git tag.**

```bash
devops release tag [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Target version string. |
| `--push`, `-p` | `boolean` | - | Push commits or tags to git remote. |
| `--type`, `-t` | `string` | `feat` | Conventional commit prefix (feat or fix). |
| `--breaking`, `-b` | `boolean` | - | Flag release as containing breaking changes (!). |
| `--message`, `-m` | `string` | - | Custom tag annotation message. |
| `--root`, `-r` | `path` | - | Project repository root directory. |

---

## devops pr

GitHub Pull Request workflows and reviews.

### `devops pr list`

**List pull requests with base targeting and review status.**

```bash
devops pr list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--state`, `-s` | `string` | `open` | Filter by state (open, closed, merged, all). |
| `--limit`, `-n` | `integer` | `30` | Maximum number of items to return or display. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

### `devops pr view`

**View details of a pull request.**

```bash
devops pr view [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

### `devops pr checks`

**Check remote CI quality gate status on a pull request.**

```bash
devops pr checks [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

### `devops pr edit`

**Edit pull request base branch, title, or body.**

```bash
devops pr edit [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-B` | `string` | - | Change the base branch for this pull request. |
| `--title`, `-t` | `string` | - | Set the new title. |
| `--body`, `-b` | `string` | - | Set the new body. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

### `devops pr create`

**Create a pull request with automatic release branch target validation.**

```bash
devops pr create [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--title`, `-t` | `string` | - | Title for the item or entity. |
| `--body`, `-b` | `string` | `` | Body or description text. |
| `--base`, `-B` | `string` | - | Base git branch to diff against (default: main). |
| `--draft`, `-d` | `boolean` | - | Create pull request or entity as draft. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---

## devops tf

OpenTofu and Terraform Infrastructure-as-Code operations.

### `devops tf init`

**Initialize an OpenTofu working directory.**

```bash
devops tf init [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--upgrade`, `-u` | `boolean` | - | Upgrade modules and plugins. |
| `--reconfigure` | `boolean` | - | Reconfigure backend, ignoring existing state. |

### `devops tf plan`

**Generate and show an OpenTofu execution plan.**

```bash
devops tf plan [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--var-file`, `-v` | `path` | - | Path to variable definitions file. |
| `--out`, `-o` | `path` | - | Write generated plan to file. |
| `--destroy` | `boolean` | - | Generate a plan to destroy all resources. |

### `devops tf apply`

**Create or update OpenTofu infrastructure.**

```bash
devops tf apply [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--var-file`, `-v` | `path` | - | Path to variable definitions file. |
| `--plan-file`, `-p` | `path` | - | Explicit plan file to apply. |
| `--auto-approve` | `boolean` | - | Skip interactive confirmation prompts. |

### `devops tf destroy`

**Destroy OpenTofu-managed infrastructure.**

```bash
devops tf destroy [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--var-file`, `-v` | `path` | - | Path to variable definitions file. |
| `--auto-approve` | `boolean` | - | Skip interactive confirmation prompts. |

### `devops tf output`

**Read an output variable from the OpenTofu state.**

```bash
devops tf output [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |
| `--raw`, `-r` | `boolean` | - | Output raw string without formatting or shell escapes. |

### `devops tf validate`

**Validate the OpenTofu configuration files in a directory.**

```bash
devops tf validate [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--no-color` | `boolean` | - | Disable color codes. |

### `devops tf fmt`

**Rewrites OpenTofu configuration files to canonical format.**

```bash
devops tf fmt [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--check`, `-c` | `boolean` | - | Check formatting without writing files. |
| `--recursive`, `-r` | `boolean` | `True` | Format subdirectories recursively. |

### `devops tf status`

**Show OpenTofu directory state, initialization status, and provider plugins.**

```bash
devops tf status <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration. |

### `devops tf deploy-cloud`

**Deploy cloud Kubernetes infrastructure for AWS, Azure, or GCP.**

```bash
devops tf deploy-cloud [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--provider`, `-p` | `string` | - | AI or cloud provider. |
| `--auto-approve` | `boolean` | - | Skip interactive confirmation prompts. |
| `--var-file`, `-v` | `path` | - | Path to variable definitions file. |

### `devops tf lint`

**Run TFLint static analysis on Terraform/OpenTofu configurations.**

```bash
devops tf lint [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--config`, `-c` | `path` | - | Path to .tflint.hcl config file. |
| `--dry-run` | `boolean` | - | Simulate TFLint execution. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops tf notify-plan`

**Format and post structured, collapsible OpenTofu/Terraform plan diffs to PR comments.**

```bash
devops tf notify-plan [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--plan-file`, `-p` | `path` | - | Path to raw plan output or log file. |
| `--pr` | `integer` | - | Pull Request number to post plan comment to. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

---

## devops tls

Generate and manage homelab TLS certificates and CAs.

### `devops tls ca`

**Generate a self-signed Root Certificate Authority (CA) key pair.**

```bash
devops tls ca [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | `~/.config/devops-cli/tls` | Directory to save certificate and key files. |
| `--common-name`, `-cn` | `string` | `Homelab DevOps Root CA` | Common Name for the certificate (e.g. *.local.lan). |
| `--organization`, `-org` | `string` | `Homelab DevOps` | Organization name. |
| `--country`, `-c` | `string` | `US` | 2-letter country code. |
| `--validity-days`, `-d` | `integer` | `3650` | Validity period in days. |
| `--key-size`, `-k` | `integer` | `<masked>` | RSA key size in bits (2048 or 4096). |
| `--overwrite`, `-f` | `boolean` | - | Overwrite existing files. |

### `devops tls cert`

**Generate an X.509 TLS certificate signed by local CA or self-signed.**

```bash
devops tls cert [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--common-name`, `-cn` | `string` | `homelab.local` | Common Name for the certificate (e.g. *.local.lan). |
| `--san`, `-s` | `string` | - | Subject Alternative Names (DNS names or IP addresses). |
| `--ca-cert` | `path` | - | Path to signing CA certificate (ca.crt). |
| `--ca-key` | `path` | - | Path to signing CA private key (ca.key). |
| `--output-dir`, `-o` | `path` | `~/.config/devops-cli/tls` | Directory to save certificate and key files. |
| `--validity-days`, `-d` | `integer` | `365` | Validity period in days. |
| `--key-size`, `-k` | `integer` | `<masked>` | RSA key size in bits (2048 or 4096). |
| `--organization`, `-org` | `string` | `Homelab DevOps` | Organization name. |
| `--overwrite`, `-f` | `boolean` | - | Overwrite existing files. |

### `devops tls homelab`

**Generate complete Homelab TLS bundle (Root CA, Wildcard + Stack Services Cert).**

```bash
devops tls homelab [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | `~/.config/devops-cli/tls` | Directory to save certificate and key files. |
| `--domain`, `-d` | `string` | - | Additional custom domains to include in SANs. |
| `--ip`, `-i` | `string` | - | Additional custom IP addresses to include in SANs. |
| `--overwrite`, `-f` | `boolean` | - | Overwrite existing files. |

### `devops tls inspect`

**Inspect and display metadata of an X.509 certificate.**

```bash
devops tls inspect <cert_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<cert_path>` | `path` | Yes | Path to X.509 certificate file (.crt or .pem). |

### `devops tls verify`

**Verify an X.509 certificate cryptographic chain against a CA certificate.**

```bash
devops tls verify [OPTIONS] <cert_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<cert_path>` | `path` | Yes | Path to leaf certificate file (.crt or .pem). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--ca-cert`, `-ca` | `path` | `~/.config/devops-cli/tls/ca.crt` | Path to signing CA certificate (ca.crt). |

### `devops tls enable-k8s`

**Generate and apply TLS secrets (kubernetes.io/tls) across Kubernetes namespaces.**

```bash
devops tls enable-k8s [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--tls-dir` | `path` | `~/.config/devops-cli/tls` | Directory with generated TLS certificates. |
| `--secret-name` | `string` | `<masked>` | Kubernetes TLS secret name to create. |
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |
| `--overwrite`, `-f` | `boolean` | - | Overwrite existing files. |

---

## devops telemetry

OpenTelemetry tracing, metrics, and Jaeger observability.

### `devops telemetry status`

**Check OpenTelemetry collector health, Jaeger endpoint, and trace propagation status.**

```bash
devops telemetry status
```

### `devops telemetry test`

**Emit a test OpenTelemetry trace span and metric to the configured collector.**

```bash
devops telemetry test [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--name`, `-n` | `string` | `devops-cli.manual_test` | Name for test span. |

### `devops telemetry profile`

**Display terminal-rendered waterfall breakdown and latency heatmap of OpenTelemetry spans.**

```bash
devops telemetry profile [OPTIONS] <command>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<command>` | `string` | No | CLI command string to profile and render waterfall for (e.g. 'devops k8s contexts'). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--trace-id`, `-t` | `string` | - | Specific trace ID to visualize from in-memory span buffer. |
| `--last`, `-l` | `boolean` | - | Render waterfall for the most recently executed command trace. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops telemetry open-ui`

**Print and show the Jaeger Query UI endpoint for inspecting traces.**

```bash
devops telemetry open-ui
```

---

## devops serve

FastAPI REST & OpenAPI Service Engine for remote automation, health probes, and metrics.

### `devops serve`

**FastAPI REST & OpenAPI Service Engine for remote automation, health probes, and metrics.**

```bash
devops serve [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--host`, `-h` | `string` | `127.0.0.1` | Network interface host to bind the HTTP server. |
| `--port`, `-p` | `integer` | `8000` | TCP port to listen on. |
| `--reload`, `-r` | `boolean` | - | Enable auto-reload on code changes (development mode). |
| `--workers`, `-w` | `integer` | `1` | Number of worker processes. |
| `--log-level`, `-l` | `string` | `info` | Logging level (debug, info, warning, error). |
| `--docs`, `--no-docs` | `boolean` | `True` | Enable or disable Swagger UI (/docs) and ReDoc (/redoc). |

---

## devops test

Test suite orchestration, git-diff aware test selector, and load testing.

### `devops test run`

**Execute pytest test suite with optional git-diff aware test selection.**

```bash
devops test run [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target test file or test directory. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--changed`, `-c` | `boolean` | - | Run only tests related to files modified in git working tree or current branch. |
| `--cov` | `boolean` | - | Run with code coverage analysis. |
| `--fail-fast`, `-x` | `boolean` | - | Stop immediately on the first test failure. |
| `--verbose`, `-v` | `boolean` | - | Enable verbose pytest output (-vv). |
| `-k` | `string` | - | Filter tests by expression. |
| `--dry-run` | `boolean` | - | Simulate test execution. |

### `devops test load`

**Execute developer-centric load, spike, and latency tests against services using k6.**

```bash
devops test load [OPTIONS] <script_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<script_path>` | `path` | No | Path to k6 JavaScript test script or endpoint definition. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--vus`, `-u` | `integer` | `10` | Number of concurrent virtual users (VUs). |
| `--duration`, `-d` | `string` | `30s` | Test execution duration (e.g. 30s, 1m). |
| `--summary-export`, `-s` | `path` | - | Path to export JSON summary metrics. |
| `--dry-run` | `boolean` | - | Simulate test execution. |

### `devops test sandbox`

**Execute test command inside an isolated, disposable Docker container sandbox.**

```bash
devops test sandbox [OPTIONS] <command>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<command>` | `string` | Yes | Test command to execute inside container sandbox |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--image`, `-i` | `string` | `python:3.14-slim` | Docker container image to execute command within |
| `--workspace`, `-w` | `path` | `.` | Workspace directory to bind mount |
| `--memory`, `-m` | `string` | `2g` | Memory constraint limit (e.g. 2g, 512m) |
| `--cpus`, `-c` | `float` | `2.0` | CPU quota limit |
| `--network`, `-n` | `string` | `bridge` | Network mode: bridge | none | host |
| `--read-only` | `boolean` | - | Mount workspace as read-only |
| `--rootless`, `--root` | `boolean` | `True` | Run container with host user UID/GID |
| `--dry-run` | `boolean` | - | Simulate test execution. |

---

## devops pipeline

Programmable containerized pipeline execution (Dagger).

Execute reproducible, containerized developer pipelines with Dagger.

### `devops pipeline`

**Execute reproducible, containerized developer pipelines with Dagger.**

```bash
devops pipeline [OPTIONS] <pipeline_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<pipeline_path>` | `path` | No | Path to Dagger module directory or pipeline script. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--function`, `-f` | `string` | - | Target pipeline function to call. |
| `--args`, `-a` | `string` | - | Arguments to forward to the pipeline execution. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## devops vault

Enterprise HashiCorp Vault secret broker

Enterprise HashiCorp Vault secret broker commands

### `devops vault status`

**Inspect HashiCorp Vault cluster health and initialization status.**

```bash
devops vault status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--addr`, `-a` | `string` | - | Vault cluster HTTP API address |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops vault get`

**Fetch secret value from Vault or OS Keyring fallback.**

```bash
devops vault get [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `string` | Yes | Vault secret path (e.g. secret/data/myapp or vault://secret/data/myapp#token) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key`, `-k` | `string` | - | Specific secret field key to extract |
| `--show` | `boolean` | - | Display secret in plain text without masking |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops vault set`

**Store secret key-value pairs in HashiCorp Vault KV-v2 engine.**

```bash
devops vault set [OPTIONS] <path> <key_values>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `string` | Yes | Vault secret path (e.g. secret/data/myapp) |
| `<key_values>` | `string` | Yes | Key-value pairs to store (format: KEY=VALUE) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops vault sync`

**Synchronize secrets from Vault into OS Keyring for offline/local CLI operations.**

```bash
devops vault sync [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `string` | Yes | Vault secret path to synchronize into OS Keyring |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key`, `-k` | `string` | - | Specific keys to sync (syncs all keys if omitted) |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
