# DevOps CLI Reference

Complete command-line reference for `devops-cli`, automatically generated from CLI command specifications.

## Command Groups

- [`devops repos`](#devops-repos) — Clone and manage repositories.
- [`devops ssh`](#devops-ssh) — SSH key generation, rotation, and GitHub registration.
- [`devops branches`](#devops-branches) — Branch management and Jira workflows.
- [`devops devcontainer`](#devops-devcontainer) — Manage devcontainer configurations.
- [`devops workspace`](#devops-workspace) — Manage VS Code workspace files.
- [`devops install-tools`](#devops-install-tools) — Install DevOps tool binaries.
- [`devops k8s`](#devops-k8s) — Kubernetes resource management.
- [`devops kustomize`](#devops-kustomize) — Kustomize operations.
- [`devops docker`](#devops-docker) — Docker image management.
- [`devops grafana`](#devops-grafana) — Grafana dashboard and alert management.
- [`devops prometheus`](#devops-prometheus) — Prometheus query and rule management.
- [`devops argo`](#devops-argo) — Argo CD, Workflows, and Rollouts management.
- [`devops config`](#devops-config) — Manage devops-cli configuration.
- [`devops ci`](#devops-ci) — Run tests, linting, formatting, and type-checks.
- [`devops uv`](#devops-uv) — Run uv commands through devops.
- [`devops scan`](#devops-scan) — Security, vulnerability, secret, and IaC scanner.
- [`devops ai`](#devops-ai) — Configure and test AI providers.
- [`devops review`](#devops-review) — AI-powered code reviews using expert personas.
- [`devops mcp`](#devops-mcp) — FastMCP server for Model Context Protocol integration.
- [`devops docs`](#devops-docs) — Generate and validate CLI and API documentation.
- [`devops release`](#devops-release) — Manage release cycles, version bumping, changelogs, and release verification.
- [`devops pr`](#devops-pr) — Manage GitHub pull requests and base branch targeting.
- [`devops tf`](#devops-tf) — OpenTofu and Terraform Infrastructure-as-Code operations.
- [`devops tofu`](#devops-tofu) — OpenTofu and Terraform Infrastructure-as-Code operations (alias for tf).
- [`devops tls`](#devops-tls) — X.509 TLS certificate generation, inspection, verification, and Kubernetes secrets.
- [`devops cert`](#devops-cert) — TLS certificate generation and management (alias for tls).
- [`devops telemetry`](#devops-telemetry) — OpenTelemetry observability, tracing, and metrics management.
- [`devops otel`](#devops-otel) — OpenTelemetry observability and tracing (alias for telemetry).

---

## devops repos

Clone and manage repositories.

### `devops repos clone-org`

**Clone all repos from a GitHub org into repos/<org>/.**

```bash
devops repos clone-org [OPTIONS] <org>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<org>` | `string` | No | GitHub organisation name |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
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
| `<url>` | `string` | Yes | Repository URL (SSH or HTTPS) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |

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

SSH key generation, rotation, and GitHub registration.

### `devops ssh generate`

**Generate a new Ed25519 SSH key with today's date suffix.**

```bash
devops ssh generate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-dir` | `path` | - | - |
| `--comment`, `-c` | `string` | `` | - |

### `devops ssh register`

```bash
devops ssh register [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-file`, `-k` | `path` | - | Path to private key |
| `--title` | `string` | - | - |

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
| `--key-dir` | `path` | - | - |
| `--force`, `-f` | `boolean` | - | Rotate even if not yet due |

### `devops ssh list`

**List all managed SSH keys with their age and rotation status.**

```bash
devops ssh list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-dir` | `path` | - | - |

### `devops ssh audit`

**List all managed SSH keys with their age and rotation status.**

```bash
devops ssh audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-dir` | `path` | - | - |

### `devops ssh status`

**Show the active SSH key and days until rotation.**

```bash
devops ssh status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key-dir` | `path` | - | - |

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
| `--base-dir`, `-d` | `path` | - | - |

### `devops branches sync`

**Fetch and pull tracking branches across all repos.**

```bash
devops branches sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |

### `devops branches jira`

**Create a feature branch for a Jira ticket: feature/PROJ-123[-slug].**

```bash
devops branches jira [OPTIONS] <ticket_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<ticket_id>` | `string` | Yes | Jira ticket ID, e.g. PROJ-123 |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--slug`, `-s` | `string` | - | Short branch description |
| `--repo`, `-r` | `path` | - | Target repo (default: cwd) |

### `devops branches list`

**List branches across all repos.**

```bash
devops branches list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--all`, `-a` | `boolean` | - | Include remote branches |

### `devops branches clean`

**Delete local branches merged into main/master.**

```bash
devops branches clean [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--dry-run`, `-n` | `boolean` | - | Show what would be deleted |

---

## devops devcontainer

Manage devcontainer configurations.

### `devops devcontainer init`

**Scaffold .devcontainer/ in a repository using standard or published template.**

```bash
devops devcontainer init [OPTIONS] <repo_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo_path>` | `path` | No | Path to the repository |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--name`, `-n` | `string` | - | Project name |
| `--python` | `string` | `3.14` | Python version for base template |
| `--image`, `-i` | `string` | - | Base container image |
| `--published`, `-p` | `boolean` | - | Use published GHCR image (ghcr.io/dan-petty/devops-cli/devcontainer:latest) |
| `--home-volume` | `string` | - | Custom volume name for /home/vscode (defaults to <project_name>-home) |
| `--minikube`, `--no-minikube` | `boolean` | `True` | Include Minikube and Kubernetes tools in base features |
| `--force`, `-f` | `boolean` | - | Overwrite existing devcontainer.json and configurations |

### `devops devcontainer update`

**Update the Python image version in an existing devcontainer.json.**

```bash
devops devcontainer update [OPTIONS] <repo_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo_path>` | `path` | No | Path to the repository |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--python` | `string` | `3.14` | - |

### `devops devcontainer validate`

**Validate .devcontainer/devcontainer.json manifest syntax and configuration schema.**

```bash
devops devcontainer validate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | `.` | Path to workspace directory containing .devcontainer |
| `--config`, `-c` | `path` | - | Direct path to devcontainer.json |
| `--dry-run` | `boolean` | - | Simulate DevContainer manifest validation |

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
| `--workspace`, `-w` | `path` | `.` | Path to workspace directory |
| `--dry-run` | `boolean` | - | Simulate execution without modifying files |

### `devops devcontainer post-start`

**Execute DevContainer post-start tasks (SSH keys, git defaults, kubeconfig, MCP sync).**

```bash
devops devcontainer post-start [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | `.` | Path to workspace directory |
| `--dry-run` | `boolean` | - | Simulate execution without modifying files |

### `devops devcontainer run-lifecycle`

**Run specified DevContainer lifecycle hook tasks natively in Python.**

```bash
devops devcontainer run-lifecycle [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | `.` | Path to workspace directory |
| `--post-create` | `boolean` | - | Execute post-create setup tasks |
| `--post-start` | `boolean` | - | Execute post-start lifecycle tasks |
| `--all`, `-a` | `boolean` | - | Execute all DevContainer lifecycle tasks |
| `--dry-run` | `boolean` | - | Simulate execution without modifying files |

---

## devops workspace

Manage VS Code workspace files.

Manage multi-root VS Code workspace files (.code-workspace).

### `devops workspace add`

**Add a folder to the VS Code workspace file.**

```bash
devops workspace add [OPTIONS] <repo_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo_path>` | `path` | Yes | Folder path to add |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | - | - |

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
| `--workspace`, `-w` | `path` | - | - |

### `devops workspace generate`

**Regenerate the workspace file from all repos in the repos directory.**

```bash
devops workspace generate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--workspace`, `-w` | `path` | - | - |

### `devops workspace open`

**Open the workspace in VS Code.**

```bash
devops workspace open [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workspace`, `-w` | `path` | - | - |

---

## devops install-tools

Install DevOps tool binaries.

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

Kubernetes resource management.

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
| `<name>` | `string` | Yes | Target context name to switch to |

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
| `<path>` | `string` | Yes | Manifest file or directory path |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | - |
| `--namespace`, `-n` | `string` | - | - |

### `devops k8s logs`

**Stream pod logs (delegates to kubectl).**

```bash
devops k8s logs [OPTIONS] <pod>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<pod>` | `string` | Yes | Pod name |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--container`, `-c` | `string` | - | - |
| `--namespace`, `-n` | `string` | - | - |
| `--follow`, `-f` | `boolean` | - | - |
| `--tail` | `integer` | `100` | - |

### `devops k8s bootstrap`

**Bootstrap minikube Kubernetes cluster and deploy infrastructure/LLM stack.**

```bash
devops k8s bootstrap [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--k8s-dir` | `path` | `k8s` | Path to k8s/ config directory |
| `--auto-start`, `--no-auto-start` | `boolean` | `True` | Auto-start minikube if stopped |
| `--stack`, `-s` | `string` | `infra` | Stack to deploy (infra, llm, all) |

### `devops k8s deploy-stack`

**Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to Kubernetes.**

```bash
devops k8s deploy-stack [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--k8s-dir` | `path` | `k8s` | Path to k8s/ config directory |
| `--stack`, `-s` | `string` | `infra` | Stack to deploy (infra, llm, all) |
| `--context`, `-c` | `string` | - | Kubernetes cluster context |

### `devops k8s configure-urls`

**Auto-detect Kubernetes stack URLs and update CLI config.**

```bash
devops k8s configure-urls [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `infra` | Stack to configure URLs for (infra, llm, all) |
| `--context`, `-c` | `string` | - | Kubernetes cluster context |

### `devops k8s port-forward`

**Port-forward k8s monitoring / LLM stack services to localhost ports and update CLI config.**

```bash
devops k8s port-forward [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `infra` | Stack services to port-forward (infra, llm, all) |
| `--context`, `-c` | `string` | - | Kubernetes cluster context |
| `--argocd-port` | `integer` | `8080` | Local port for ArgoCD |
| `--grafana-port` | `integer` | `8030` | Local port for Grafana |
| `--prometheus-port` | `integer` | `8090` | Local port for Prometheus |
| `--jaeger-port` | `integer` | `16686` | Local port for Jaeger Query UI |
| `--otel-port` | `integer` | `4318` | Local port for OpenTelemetry OTLP Traces (HTTP) |
| `--ollama-port` | `integer` | `11434` | Local port for Ollama |
| `--open-webui-port` | `integer` | `3000` | Local port for Open-WebUI |
| `--qdrant-port` | `integer` | `6333` | Local port for Qdrant HTTP |
| `--valkey-port` | `integer` | `6379` | Local port for Valkey |
| `--address` | `string` | `127.0.0.1` | Local address to bind for port-forwarding |

### `devops k8s teardown-stack`

**Uninstall the k8s infrastructure / LLM stack and delete namespaces.**

```bash
devops k8s teardown-stack [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--k8s-dir` | `path` | `k8s` | Path to k8s/ config directory |
| `--stack`, `-s` | `string` | `infra` | Stack to teardown (infra, llm, all) |
| `--context`, `-c` | `string` | - | Kubernetes cluster context |

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
| `<target>` | `path` | No | Target K8s manifest file or directory to lint |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Simulate manifest linting. |

### `devops k8s audit`

**Sanitize active K8s/Minikube cluster resource health using Derailed Popeye.**

```bash
devops k8s audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Simulate cluster health audit. |

### `devops k8s check-deprecated`

**Scan manifests for deprecated/removed K8s API versions using Fairwinds Pluto.**

```bash
devops k8s check-deprecated [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target manifest file or directory to scan for deprecated APIs |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Simulate deprecated API detection. |

### `devops k8s create-tls-secret`

**Create or update a kubernetes.io/tls secret from certificate and private key files.**

```bash
devops k8s create-tls-secret [OPTIONS] <secret_name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<secret_name>` | `string` | Yes | Name of the Kubernetes TLS secret to create or update |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | `default` | Target Kubernetes namespace |
| `--cert` | `path` | `~/.config/devops-cli/tls/tls.crt` | Path to TLS certificate file (.crt or .pem) |
| `--key` | `path` | `~/.config/devops-cli/tls/tls.key` | Path to TLS private key file (.key or .pem) |
| `--context`, `-c` | `string` | - | Kubernetes cluster context |

### `devops k8s enable-tls`

**Generate Homelab certificates and apply TLS secrets across Kubernetes cluster namespaces.**

```bash
devops k8s enable-tls [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--context`, `-c` | `string` | - | Kubernetes cluster context |
| `--tls-dir` | `path` | `~/.config/devops-cli/tls` | Directory with generated TLS certificates |
| `--secret-name` | `string` | `homelab-tls` | TLS secret name across namespaces |
| `--stack`, `-s` | `string` | `all` | Stack to deploy TLS secrets into (infra, llm, all) |
| `--overwrite`, `-f` | `boolean` | - | Regenerate certs if missing |

---

## devops kustomize

Kustomize operations.

Kustomize build and apply operations.

### `devops kustomize build`

**Build kustomize overlays (delegates to kustomize build).**

```bash
devops kustomize build [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Path to kustomization directory |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `string` | - | Output file or directory |

### `devops kustomize diff`

**Show a diff of pending changes (delegates to kubectl diff -k).**

```bash
devops kustomize diff <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Path to kustomization directory |

### `devops kustomize apply`

**Apply a kustomization (delegates to kubectl apply -k).**

```bash
devops kustomize apply [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Path to kustomization directory |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | - |
| `--namespace`, `-n` | `string` | - | - |

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
| `--name`, `-n` | `string` | - | Filter by name |

### `devops docker build`

**Build a Docker image.**

```bash
devops docker build [OPTIONS] <context>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<context>` | `path` | No | Build context directory |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--tag`, `-t` | `string` | - | - |
| `--file`, `-f` | `path` | - | - |
| `--no-cache` | `boolean` | - | - |

### `devops docker push`

**Push a Docker image to a registry.**

```bash
devops docker push <image>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<image>` | `string` | Yes | Image name[:tag] to push |

### `devops docker prune`

**Remove unused containers, images, and networks.**

```bash
devops docker prune [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--volumes` | `boolean` | - | Also remove unused volumes |
| `--force`, `-f` | `boolean` | - | Skip confirmation |

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
| `--query`, `-q` | `string` | `` | Search query |

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

**Manage Grafana dashboards.**

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
| `<uid>` | `string` | Yes | Dashboard UID |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | - |

#### `devops grafana dashboards import`

**Import a dashboard from JSON.**

```bash
devops grafana dashboards import [OPTIONS] <file>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<file>` | `path` | Yes | Dashboard JSON file |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--folder-id` | `integer` | `0` | - |

#### `devops grafana dashboards sync`

**Sync all bundled/local dashboards to Grafana.**

```bash
devops grafana dashboards sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | - | Directory containing dashboard JSON files |

---

## devops prometheus

Prometheus query and rule management.

### `devops prometheus query`

**Execute an instant PromQL query.**

```bash
devops prometheus query [OPTIONS] <expr>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<expr>` | `string` | Yes | PromQL expression |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--time`, `-t` | `string` | - | Evaluation time (RFC3339 or Unix) |

### `devops prometheus query-range`

**Execute a range PromQL query and summarise the result.**

```bash
devops prometheus query-range [OPTIONS] <expr>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<expr>` | `string` | Yes | PromQL expression |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--start`, `-s` | `string` | `1h` | Start: duration ago (e.g. 1h) or Unix ts |
| `--end`, `-e` | `string` | - | - |
| `--step` | `string` | `60s` | - |

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

**ArgoCD application management.**

```bash
devops argo cd COMMAND [ARGS]...
```

#### `devops argo cd apps`

**Manage ArgoCD applications.**

```bash
devops argo cd apps COMMAND [ARGS]...
```

##### `devops argo cd apps list`

**List all ArgoCD applications.**

```bash
devops argo cd apps list
```

##### `devops argo cd apps sync`

**Trigger a sync for an ArgoCD application.**

```bash
devops argo cd apps sync [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Application name |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--prune` | `boolean` | - | - |
| `--force` | `boolean` | - | - |

##### `devops argo cd apps status`

**Show sync and health status for an ArgoCD application.**

```bash
devops argo cd apps status <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Application name |

### `devops argo workflows`

**Argo Workflows management.**

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
| `--namespace`, `-n` | `string` | - | - |

#### `devops argo workflows submit`

**Submit an Argo Workflow from a YAML file.**

```bash
devops argo workflows submit [OPTIONS] <file>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<file>` | `path` | Yes | Workflow YAML file |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | - |
| `--wait`, `-w` | `boolean` | - | - |

#### `devops argo workflows logs`

**Stream logs for an Argo Workflow.**

```bash
devops argo workflows logs [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Workflow name |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | - |
| `--follow`, `-f` | `boolean` | - | - |

### `devops argo rollouts`

**Argo Rollouts management.**

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
| `--namespace`, `-n` | `string` | - | - |

#### `devops argo rollouts status`

**Show status for an Argo Rollout.**

```bash
devops argo rollouts status [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Rollout name |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | - |
| `--watch`, `-w` | `boolean` | - | - |

---

## devops config

Manage devops-cli configuration.

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
| `<key>` | `string` | Yes | Dotted config key, e.g. github.default_org |

### `devops config set`

**Set a configuration value. Tokens are stored in the OS keyring.**

```bash
devops config set <key> <value>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<key>` | `string` | Yes | Dotted config key, e.g. github.token |
| `<value>` | `string` | Yes | Value to set |

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
| `<key>` | `string` | Yes | Dotted secret key, e.g. github.token |
| `<token>` | `string` | Yes | Secret token string |

### `devops config audit-stream`

**Stream stored audit records to SIEM destination URL.**

```bash
devops config audit-stream <destination>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<destination>` | `string` | Yes | Destination Syslog or HTTP URL |

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
| `--verbose`, `-v` | `boolean` | - | Verbose output |
| `-k` | `string` | - | Filter tests by keyword expression |
| `-x` | `boolean` | - | Stop after first failure |
| `-n`, `--numprocesses` | `string` | `auto` | Number of parallel worker processes |

### `devops ci coverage`

**Run pytest with parallel code coverage analysis over src/.**

```bash
devops ci coverage [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--html` | `boolean` | - | Generate HTML coverage report in htmlcov/ |
| `-n`, `--numprocesses` | `string` | `auto` | Number of parallel worker processes |

### `devops ci lint`

**Run ruff linter across the project.**

```bash
devops ci lint [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` | `boolean` | - | Auto-fix violations where possible |

### `devops ci format`

**Check (or apply) code formatting with ruff format.**

```bash
devops ci format [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` | `boolean` | - | Apply formatting changes in-place |

### `devops ci typecheck`

**Run mypy static type-checker strictly targeting Python 3.14 over src/.**

```bash
devops ci typecheck
```

### `devops ci audit`

**Run uv audit to check for known package vulnerabilities.**

```bash
devops ci audit
```

### `devops ci security`

**Run bandit static security vulnerability analysis over src/.**

```bash
devops ci security [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--severity`, `-s` | `string` | `medium` | Minimum severity threshold (low, medium, high) |

### `devops ci actionlint`

**Run actionlint to validate GitHub Actions workflows for syntax and schema errors.**

```bash
devops ci actionlint
```

### `devops ci docs`

**Verify that documentation is up to date with CLI commands and configuration.**

```bash
devops ci docs
```

### `devops ci run`

**Run full CI and return a single pass/fail status.**

```bash
devops ci run [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix`, `--no-fix` | `boolean` | `True` | Auto-fix lint/format before reporting status |

---

## devops uv

Run uv commands through devops.

uv dependency management proxies.

### `devops uv sync`

**Sync project dependencies into the virtual environment.**

```bash
devops uv sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--frozen` | `boolean` | - | Do not update lockfile |

### `devops uv lock`

**Regenerate the uv lockfile.**

```bash
devops uv lock [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--upgrade` | `boolean` | - | Upgrade dependencies while locking |

### `devops uv python-install`

**Install project Python version with uv.**

```bash
devops uv python-install [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Python version to install (defaults to .python-version) |

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

Security, vulnerability, secret, and IaC scanner.

Security, vulnerability, secret, and IaC scanner via Aqua Trivy.

### `devops scan`

**Security, vulnerability, secret, and IaC scanner via Aqua Trivy.**

```bash
devops scan [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory, file, or repository to scan |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--type`, `-t` | `string` | `fs` | Trivy scan mode: fs, image, iac, repo |
| `--severity`, `-s` | `string` | `UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL` | Comma-separated severity levels to include |
| `--dry-run` | `boolean` | - | Simulate security scan execution. |
| `--json` | `boolean` | - | Output raw findings as JSON |

---

## devops ai

Configure and test AI providers.

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
| `--model`, `-m` | `string` | - | Model name, e.g. gemma4:26b, claude-opus-4-5 |
| `--ollama-urls` | `string` | - | Ollama server base URLs (comma-separated) |
| `--ollama-max-parallel` | `integer` | - | Maximum number of simultaneous requests allowed per Ollama server node |
| `--api-base-url` | `string` | - | Override API base URL for any provider |
| `--api-key` | `string` | - | API key — stored in OS keyring, not config file |
| `--max-retries` | `integer` | - | Maximum retry count for AI requests upon failure |

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
| `--prompt`, `-p` | `string` | `Reply with exactly one word: OK` | Test prompt to send to the provider |
| `--url`, `-u` | `string` | - | Specific Ollama server URL to test |

### `devops ai agents`

**Generate LLM/Agent instruction files (AGENTS.md, CLAUDE.md, copilot-instructions.md).**

```bash
devops ai agents [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `path` | `.` | Repository root (default: current directory) |
| `--template` | `boolean` | - | Generate from built-in template without calling the LLM |
| `--file`, `-f` | `string` | `['AGENTS.md', 'CLAUDE.md', '.github/copilot-instructions.md']` | Files to generate (repeatable) |

### `devops ai chat`

**Start an interactive chat with a Pydantic AI persona (tools, thinking, streaming, RAG).**

```bash
devops ai chat [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--persona`, `-p` | `string` | `architect` | Persona to chat with: devsecops, architect, pm, auditor, qa |
| `--context`, `-c` | `path` | - | Optional file to inject as background context (e.g. AGENTS.md) |
| `--rag`, `--no-rag` | `boolean` | `True` | Retrieve relevant semantic RAG context |
| `--stream`, `--no-stream` | `boolean` | `True` | Stream response tokens |
| `--tools`, `--no-tools` | `boolean` | `True` | Enable DevOps agent tools |
| `--thinking`, `--no-thinking` | `boolean` | `True` | Enable model reasoning/thinking |
| `--prewarm`, `--no-prewarm` | `boolean` | `True` | Prewarm the model before starting chat |
| `--explain`, `-e` | `boolean` | - | Explain chat personas, tools, and reasoning modes |

### `devops ai bundle-models`

**Bundle Ollama model metadata into tarball for air-gapped DevContainers.**

```bash
devops ai bundle-models [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Output directory for model archive bundle |

### `devops ai pipeline`

**Run a multi-agent Pydantic pipeline with shared DevOps tools and RAG context.**

```bash
devops ai pipeline [OPTIONS] <prompt>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<prompt>` | `string` | No | Initial goal or prompt for the multi-agent pipeline |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--personas`, `-p` | `string` | `devsecops,architect,qa` | Comma-separated persona pipeline sequence (e.g. devsecops,architect,qa) |
| `--max-turns` | `integer` | `5` | Maximum tool turns per agent stage |
| `--rag`, `--no-rag` | `boolean` | `True` | Retrieve relevant semantic RAG context |
| `--thinking`, `--no-thinking` | `boolean` | `True` | Enable reasoning/thinking per agent |

### `devops ai review`

**AI-powered multi-persona code review system.**

```bash
devops ai review [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology |

#### `devops ai review path`

**Review source files directly (no git required).**

```bash
devops ai review path [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | File or directory to review |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--pattern`, `-g` | `string` | `*` | Glob pattern for files (default: all files) |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa)` | - | Reviewer persona |
| `--all` | `boolean` | - | Run all four reviewer personas |
| `--dry-run` | `boolean` | - | Print commands and AI request payloads without executing. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology |

#### `devops ai review branch`

**Review a git branch diff with one or all AI personas.**

```bash
devops ai review branch [OPTIONS] <branch_name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<branch_name>` | `string` | No | Branch to review (default: current branch) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-b` | `string` | `main` | Base branch to diff against |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa)` | - | Reviewer persona |
| `--all` | `boolean` | - | Run all four reviewer personas |
| `--repo` | `path` | `.` | Path to the git repository |
| `--dry-run` | `boolean` | - | Print commands and AI request payloads without executing. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology |

#### `devops ai review pr`

**Review a GitHub pull request with one or all AI personas.**

```bash
devops ai review pr [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `string` | - | owner/repo (default: detected from git remote) |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa)` | - | Reviewer persona |
| `--all` | `boolean` | - | Run all four reviewer personas |
| `--post` | `boolean` | - | Post the review as a comment on the GitHub PR |
| `--dry-run` | `boolean` | - | Print commands and AI request payloads without executing. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology |

#### `devops ai review findings`

**Inspect structured findings for a review session.**

```bash
devops ai review findings [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Session ID or substring (default: latest) |
| `--status` | `string` | - | Filter by status: VERIFIED | UNVERIFIED | INVALIDATED | MITIGATED |
| `--unverified` | `boolean` | - | Show unverified findings only |
| `--invalidated` | `boolean` | - | Show invalidated findings only |
| `--verified` | `boolean` | - | Show verified findings only |

#### `devops ai review verify`

**Validate or invalidate a review finding, persisting feedback reasons.**

```bash
devops ai review verify [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | Yes | Session ID or substring |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--index`, `-i` | `integer` | - | 1-based index of the finding to update |
| `--title`, `-t` | `string` | - | Title substring to match finding |
| `--status` | `string` | `INVALIDATED` | Target status: VERIFIED | INVALIDATED | MITIGATED | UNVERIFIED |
| `--reason`, `-r` | `string` | `` | Explanation or justification for the status change |

#### `devops ai review stats`

**Compute and display review accuracy statistics across saved sessions.**

```bash
devops ai review stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--reviews-dir` | `path` | - | Directory containing review sessions |

#### `devops ai review export-feedback`

**Export review findings into a JSONL benchmark dataset for prompt tuning and fine-tuning.**

```bash
devops ai review export-feedback [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Output JSONL path for benchmark feedback dataset |
| `--reviews-dir` | `path` | - | Directory containing review sessions |
| `--status`, `-s` | `string` | `INVALIDATED` | Finding status to export: INVALIDATED, VERIFIED, MITIGATED, or ALL |

#### `devops ai review apply-patch`

**Apply suggested LLM code fix for a verified finding (v0.1.3).**

```bash
devops ai review apply-patch [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | Yes | Review session ID |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--index`, `-idx` | `integer` | `1` | Finding index (1-based) |
| `--interactive`, `-i` | `boolean` | - | Preview patch diff interactively |

### `devops ai analyze`

**Analyze codebase metadata and generate structural outlines.**

```bash
devops ai analyze [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology |

#### `devops ai analyze path`

**Analyze a local directory path or single file and save metadata to .data/analysis/.**

```bash
devops ai analyze path [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | File or directory path to analyze |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--pattern`, `-g` | `string` | `*` | Glob pattern for files (default: all files) |
| `--enhanced`, `-e`, `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated) |
| `--update-all`, `-u` | `boolean` | - | Regenerate all enhanced metadata fields regardless of last_* timestamps |
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology |

#### `devops ai analyze branch`

**Analyze a git branch diff against base and save metadata to .data/analysis/.**

```bash
devops ai analyze branch [OPTIONS] <branch>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<branch>` | `string` | No | Branch to analyze (default: active branch) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-b` | `string` | `main` | Base branch for diff |
| `--enhanced`, `-e`, `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated) |
| `--update-all`, `-u` | `boolean` | - | Regenerate all enhanced metadata fields regardless of last_* timestamps |
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology |

#### `devops ai analyze pr`

**Analyze a GitHub Pull Request and save metadata to .data/analysis/.**

```bash
devops ai analyze pr [OPTIONS] <pr_number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<pr_number>` | `integer` | Yes | GitHub PR number to analyze |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--enhanced`, `-e`, `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated) |
| `--update-all`, `-u` | `boolean` | - | Regenerate all enhanced metadata fields regardless of last_* timestamps |
| `--explain`, `-x` | `boolean` | - | Explain static code analysis metrics and terminology |

### `devops ai rag`

**Manage RAG vector embeddings, indexing, and semantic search (Qdrant).**

```bash
devops ai rag [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--explain`, `-e` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology |

#### `devops ai rag index`

**Scan and index workspace code and documentation into Qdrant vector database.**

```bash
devops ai rag index [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Directory or file to index into vector store |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--project`, `-p` | `string` | - | Project / repository name override |
| `--force`, `-f` | `boolean` | - | Re-index all files ignoring content hash cache |
| `--collection`, `-c` | `string` | - | Target collection override |
| `--explain`, `-e` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology |

#### `devops ai rag query`

**Perform semantic search across indexed workspace code and documentation.**

```bash
devops ai rag query [OPTIONS] <query>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<query>` | `string` | Yes | Semantic search query string |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--project`, `-p` | `string` | - | Filter results to a specific project |
| `--language`, `-l` | `string` | - | Filter by programming language |
| `--category` | `string` | - | Filter by category (code, docs, iac, config) |
| `--top-k`, `-k` | `integer` | `5` | Number of results to retrieve |
| `--min-score`, `-s` | `float` | `0.35` | Minimum cosine similarity threshold |
| `--collection`, `-c` | `string` | - | Search only a specific collection |
| `--file`, `-f` | `string` | - | Filter results to a specific file |
| `--explain`, `-e` | `boolean` | - | Explain RAG vector embeddings, Qdrant indexing, and terminology |

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
| `--collection`, `-c` | `string` | - | Specific collection to delete (default: all) |
| `--force`, `-f` | `boolean` | - | Bypass confirmation prompt |

#### `devops ai rag clear`

**Clear vector index collections from Qdrant.**

```bash
devops ai rag clear [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--collection`, `-c` | `string` | - | Specific collection to delete (default: all) |
| `--force`, `-f` | `boolean` | - | Bypass confirmation prompt |

### `devops ai benchmark`

**Benchmark, evaluate, and peer-grade candidate AI models across engineering tasks.**

```bash
devops ai benchmark [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--models`, `-m` | `string` | - | Comma-separated candidate models (e.g. 'qwen2.5:0.5b,llama3.1:8b@http://gpu2:11434') |
| `--servers`, `--ollama-urls` | `string` | - | Comma-separated Ollama server URLs for concurrent execution (e.g. 'http://node1:11434,http://node2:11434') |
| `--provider`, `-p` | `string` | - | AI provider (ollama, claude, copilot, openai) |
| `--type`, `--mode` | `string` | `auto` | Benchmark mode: 'auto', 'chat', 'embedding' (default: auto) |
| `--tasks`, `-t` | `string` | - | Filter specific task categories or IDs (e.g. 'security,kubernetes') |
| `--concurrency`, `-c` | `integer` | `4` | Number of concurrent model server workers (default: automatic per model count) |
| `--output`, `-o` | `path` | - | Destination JSON report filepath |
| `--format`, `-f` | `string` | `table` | Output format: table, json, markdown |
| `--dry-run` | `boolean` | - | Simulate benchmark without sending remote LLM requests |
| `--explain`, `-e` | `boolean` | - | Explain benchmark metrics, terminology, and mathematical formulas |
| `--document`, `-d` | `path` | - | Path to large test document for in-memory tokenization and section retrieval |
| `--samples` | `integer` | `5` | Number of random sections to sample for retrieval evaluation |

---

## devops review

AI-powered code reviews using expert personas.

AI Code Review across branches, paths, and pull requests.

### `devops review path`

**Review source files directly (no git required).**

```bash
devops review path [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | File or directory to review |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--pattern`, `-g` | `string` | `*` | Glob pattern for files (default: all files) |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa)` | - | Reviewer persona |
| `--all` | `boolean` | - | Run all four reviewer personas |
| `--dry-run` | `boolean` | - | Print commands and AI request payloads without executing. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology |

### `devops review branch`

**Review a git branch diff with one or all AI personas.**

```bash
devops review branch [OPTIONS] <branch_name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<branch_name>` | `string` | No | Branch to review (default: current branch) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-b` | `string` | `main` | Base branch to diff against |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa)` | - | Reviewer persona |
| `--all` | `boolean` | - | Run all four reviewer personas |
| `--repo` | `path` | `.` | Path to the git repository |
| `--dry-run` | `boolean` | - | Print commands and AI request payloads without executing. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology |

### `devops review pr`

**Review a GitHub pull request with one or all AI personas.**

```bash
devops review pr [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `string` | - | owner/repo (default: detected from git remote) |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa)` | - | Reviewer persona |
| `--all` | `boolean` | - | Run all four reviewer personas |
| `--post` | `boolean` | - | Post the review as a comment on the GitHub PR |
| `--dry-run` | `boolean` | - | Print commands and AI request payloads without executing. |
| `--summary`, `-s` | `boolean` | - | Show segment metadata without running a full review. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology |

### `devops review findings`

**Inspect structured findings for a review session.**

```bash
devops review findings [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Session ID or substring (default: latest) |
| `--status` | `string` | - | Filter by status: VERIFIED | UNVERIFIED | INVALIDATED | MITIGATED |
| `--unverified` | `boolean` | - | Show unverified findings only |
| `--invalidated` | `boolean` | - | Show invalidated findings only |
| `--verified` | `boolean` | - | Show verified findings only |

### `devops review verify`

**Validate or invalidate a review finding, persisting feedback reasons.**

```bash
devops review verify [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | Yes | Session ID or substring |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--index`, `-i` | `integer` | - | 1-based index of the finding to update |
| `--title`, `-t` | `string` | - | Title substring to match finding |
| `--status` | `string` | `INVALIDATED` | Target status: VERIFIED | INVALIDATED | MITIGATED | UNVERIFIED |
| `--reason`, `-r` | `string` | `` | Explanation or justification for the status change |

### `devops review stats`

**Compute and display review accuracy statistics across saved sessions.**

```bash
devops review stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--reviews-dir` | `path` | - | Directory containing review sessions |

### `devops review export-feedback`

**Export review findings into a JSONL benchmark dataset for prompt tuning and fine-tuning.**

```bash
devops review export-feedback [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Output JSONL path for benchmark feedback dataset |
| `--reviews-dir` | `path` | - | Directory containing review sessions |
| `--status`, `-s` | `string` | `INVALIDATED` | Finding status to export: INVALIDATED, VERIFIED, MITIGATED, or ALL |

### `devops review apply-patch`

**Apply suggested LLM code fix for a verified finding (v0.1.3).**

```bash
devops review apply-patch [OPTIONS] <session>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<session>` | `string` | Yes | Review session ID |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--index`, `-idx` | `integer` | `1` | Finding index (1-based) |
| `--interactive`, `-i` | `boolean` | - | Preview patch diff interactively |

---

## devops mcp

FastMCP server for Model Context Protocol integration.

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

Generate and validate CLI and API documentation.

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
| `--format`, `-f` | `string` | `markdown` | Documentation output format ('markdown' or 'json'). |
| `--sync-readme`, `--no-sync-readme` | `boolean` | `True` | Synchronize Complete Command Matrix in README.md. |
| `--check` | `boolean` | - | Validate that existing documentation is up to date without writing files. |

### `devops docs check`

**Check that generated documentation and README.md are up to date with codebase.**

```bash
devops docs check [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | - | Directory containing documentation to check (default: docs/). |
| `--check-readme`, `--no-check-readme` | `boolean` | `True` | Verify README.md Command Matrix synchronization as well. |

### `devops docs sync-readme`

**Synchronize the Complete Command Matrix table in README.md with live CLI commands.**

```bash
devops docs sync-readme [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--readme-path`, `-r` | `path` | - | Path to README.md file (default: workspace root README.md). |
| `--check` | `boolean` | - | Verify README.md table is synchronized without writing changes. |

---

## devops release

Manage release cycles, version bumping, changelogs, and release verification.

### `devops release status`

**Display current release status, versions, tags, changelog, and docs state.**

```bash
devops release status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--root`, `-r` | `path` | - | Project repository root directory |

### `devops release prepare`

**Bump version across pyproject.toml and source, update changelog, and sync docs.**

```bash
devops release prepare [OPTIONS] <version>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<version>` | `string` | Yes | Target semantic version (e.g., 0.1.8) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--sync-docs`, `--no-sync-docs` | `boolean` | `True` | Regenerate CLI reference docs and sync README matrix |
| `--changelog`, `--no-changelog` | `boolean` | `True` | Ensure CHANGELOG.md contains release header with current date |
| `--create-pr`, `-p` | `boolean` | - | Create release branch, commit changes, and open a GitHub Release PR |
| `--type`, `-t` | `string` | `feat` | Conventional commit prefix (feat or fix) |
| `--breaking`, `-b` | `boolean` | - | Flag release as containing breaking changes (!) |
| `--root`, `-r` | `path` | - | Project repository root directory |

### `devops release pr`

**Create release branch, commit version bumps, and open a GitHub Release Pull Request.**

```bash
devops release pr [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Target release version (defaults to pyproject.toml) |
| `--base`, `-b` | `string` | `main` | Target base branch for Pull Request |
| `--draft` | `boolean` | - | Create Pull Request as a draft |
| `--labels`, `-l` | `string` | `release` | Comma-separated labels to attach to PR |
| `--push`, `--no-push` | `boolean` | `True` | Push release branch to origin |
| `--type`, `-t` | `string` | `feat` | Conventional commit prefix (feat or fix) |
| `--breaking`, `-b` | `boolean` | - | Flag release as containing breaking changes (!) |
| `--root`, `-r` | `path` | - | Project repository root directory |

### `devops release check`

**Verify release readiness (version consistency, docs freshness, and CI quality gates).**

```bash
devops release check [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--skip-ci` | `boolean` | - | Skip running the 7-gate CI test suite |
| `--allow-dirty` | `boolean` | - | Allow uncommitted changes in git repository |
| `--root`, `-r` | `path` | - | Project repository root directory |

### `devops release notes`

**Print markdown release notes for a specified or current release version.**

```bash
devops release notes [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Release version to extract notes for |
| `--raw` | `boolean` | - | Output raw markdown text without formatting panel |
| `--root`, `-r` | `path` | - | Project repository root directory |

### `devops release tag`

**Create release commit and annotated git tag.**

```bash
devops release tag [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Release version (defaults to pyproject.toml) |
| `--push`, `-p` | `boolean` | - | Push release commit and git tag to origin |
| `--type`, `-t` | `string` | `feat` | Conventional commit prefix (feat or fix) |
| `--breaking`, `-b` | `boolean` | - | Flag release as containing breaking changes (!) |
| `--message`, `-m` | `string` | - | Custom tag annotation message |
| `--root`, `-r` | `path` | - | Project repository root directory |

---

## devops pr

Manage GitHub pull requests and base branch targeting.

Manage GitHub pull requests, base branch targeting, and review gates.

### `devops pr list`

**List pull requests with base targeting and review status.**

```bash
devops pr list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--state`, `-s` | `string` | `open` | Filter by state (open, closed, merged, all) |
| `--limit`, `-n` | `integer` | `10` | Maximum number of pull requests to display |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format |

### `devops pr view`

**View details of a pull request.**

```bash
devops pr view [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format |

### `devops pr checks`

**Check remote CI quality gate status on a pull request.**

```bash
devops pr checks [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format |

### `devops pr edit`

**Edit pull request base branch, title, or body.**

```bash
devops pr edit [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base`, `-B` | `string` | - | Change the base branch for this pull request |
| `--title`, `-t` | `string` | - | Set the new title |
| `--body`, `-b` | `string` | - | Set the new body |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format |

### `devops pr create`

**Create a pull request with automatic release branch target validation.**

```bash
devops pr create [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--title`, `-t` | `string` | - | Pull request title |
| `--body`, `-b` | `string` | `` | Pull request body text |
| `--base`, `-B` | `string` | - | Target base branch (defaults to active release branch) |
| `--draft`, `-d` | `boolean` | - | Create pull request as draft |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format |

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
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--upgrade`, `-u` | `boolean` | - | Upgrade modules and plugins |
| `--reconfigure` | `boolean` | - | Reconfigure backend, ignoring existing state |

### `devops tf plan`

**Generate and show an OpenTofu execution plan.**

```bash
devops tf plan [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--var-file`, `-v` | `path` | - | Path to variable definitions file |
| `--out`, `-o` | `path` | - | Write generated plan to file |
| `--destroy` | `boolean` | - | Generate a plan to destroy all resources |

### `devops tf apply`

**Create or update OpenTofu infrastructure.**

```bash
devops tf apply [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--var-file`, `-v` | `path` | - | Path to variable definitions file |
| `--plan-file`, `-p` | `path` | - | Explicit plan file to apply |
| `--auto-approve` | `boolean` | - | Skip interactive approval before applying |

### `devops tf destroy`

**Destroy OpenTofu-managed infrastructure.**

```bash
devops tf destroy [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--var-file`, `-v` | `path` | - | Path to variable definitions file |
| `--auto-approve` | `boolean` | - | Skip interactive approval before destroying |

### `devops tf output`

**Read an output variable from the OpenTofu state.**

```bash
devops tf output [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json`, `-j` | `boolean` | - | Output values formatted as JSON |
| `--raw`, `-r` | `boolean` | - | Output raw string without shell escapes |

### `devops tf validate`

**Validate the OpenTofu configuration files in a directory.**

```bash
devops tf validate [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--no-color` | `boolean` | - | Disable color codes |

### `devops tf fmt`

**Rewrites OpenTofu configuration files to canonical format.**

```bash
devops tf fmt [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--check`, `-c` | `boolean` | - | Check formatting without writing files |
| `--recursive`, `-r` | `boolean` | `True` | Format subdirectories recursively |

### `devops tf status`

**Show OpenTofu directory state, initialization status, and provider plugins.**

```bash
devops tf status <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

### `devops tf deploy-cloud`

**Deploy cloud Kubernetes infrastructure for AWS, Azure, or GCP.**

```bash
devops tf deploy-cloud [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--provider`, `-p` | `string` | - | Target cloud provider: aws, azure, or gcp |
| `--auto-approve` | `boolean` | - | Automatically approve apply without prompt |
| `--var-file`, `-v` | `path` | - | Path to custom tfvars file |

---

## devops tofu

OpenTofu and Terraform Infrastructure-as-Code operations (alias for tf).

OpenTofu and Terraform Infrastructure-as-Code operations.

### `devops tofu init`

**Initialize an OpenTofu working directory.**

```bash
devops tofu init [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--upgrade`, `-u` | `boolean` | - | Upgrade modules and plugins |
| `--reconfigure` | `boolean` | - | Reconfigure backend, ignoring existing state |

### `devops tofu plan`

**Generate and show an OpenTofu execution plan.**

```bash
devops tofu plan [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--var-file`, `-v` | `path` | - | Path to variable definitions file |
| `--out`, `-o` | `path` | - | Write generated plan to file |
| `--destroy` | `boolean` | - | Generate a plan to destroy all resources |

### `devops tofu apply`

**Create or update OpenTofu infrastructure.**

```bash
devops tofu apply [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--var-file`, `-v` | `path` | - | Path to variable definitions file |
| `--plan-file`, `-p` | `path` | - | Explicit plan file to apply |
| `--auto-approve` | `boolean` | - | Skip interactive approval before applying |

### `devops tofu destroy`

**Destroy OpenTofu-managed infrastructure.**

```bash
devops tofu destroy [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--var-file`, `-v` | `path` | - | Path to variable definitions file |
| `--auto-approve` | `boolean` | - | Skip interactive approval before destroying |

### `devops tofu output`

**Read an output variable from the OpenTofu state.**

```bash
devops tofu output [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json`, `-j` | `boolean` | - | Output values formatted as JSON |
| `--raw`, `-r` | `boolean` | - | Output raw string without shell escapes |

### `devops tofu validate`

**Validate the OpenTofu configuration files in a directory.**

```bash
devops tofu validate [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--no-color` | `boolean` | - | Disable color codes |

### `devops tofu fmt`

**Rewrites OpenTofu configuration files to canonical format.**

```bash
devops tofu fmt [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--check`, `-c` | `boolean` | - | Check formatting without writing files |
| `--recursive`, `-r` | `boolean` | `True` | Format subdirectories recursively |

### `devops tofu status`

**Show OpenTofu directory state, initialization status, and provider plugins.**

```bash
devops tofu status <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration |

### `devops tofu deploy-cloud`

**Deploy cloud Kubernetes infrastructure for AWS, Azure, or GCP.**

```bash
devops tofu deploy-cloud [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--provider`, `-p` | `string` | - | Target cloud provider: aws, azure, or gcp |
| `--auto-approve` | `boolean` | - | Automatically approve apply without prompt |
| `--var-file`, `-v` | `path` | - | Path to custom tfvars file |

---

## devops tls

X.509 TLS certificate generation, inspection, verification, and Kubernetes secrets.

### `devops tls ca`

**Generate a self-signed Root Certificate Authority (CA) key pair.**

```bash
devops tls ca [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | `~/.config/devops-cli/tls` | Directory to save CA certificate and key |
| `--common-name`, `-cn` | `string` | `Homelab DevOps Root CA` | Common Name for the Root CA |
| `--organization`, `-org` | `string` | `Homelab DevOps` | Organization name |
| `--country`, `-c` | `string` | `US` | 2-letter country code |
| `--validity-days`, `-d` | `integer` | `3650` | Validity period in days |
| `--key-size`, `-k` | `integer` | `2048` | RSA key size in bits (2048 or 4096) |
| `--overwrite`, `-f` | `boolean` | - | Overwrite existing CA certificate and key |

### `devops tls cert`

**Generate an X.509 TLS certificate signed by local CA or self-signed.**

```bash
devops tls cert [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--common-name`, `-cn` | `string` | `localhost` | Primary Common Name or domain |
| `--san`, `-s` | `string` | - | Subject Alternative Names (DNS names or IP addresses) |
| `--ca-cert` | `path` | - | Path to signing CA certificate (ca.crt) |
| `--ca-key` | `path` | - | Path to signing CA private key (ca.key) |
| `--output-dir`, `-o` | `path` | `~/.config/devops-cli/tls` | Directory to save certificate and key |
| `--validity-days`, `-d` | `integer` | `365` | Validity period in days |
| `--key-size`, `-k` | `integer` | `2048` | RSA key size in bits (2048 or 4096) |
| `--organization`, `-org` | `string` | `Homelab DevOps` | Organization name |
| `--overwrite`, `-f` | `boolean` | - | Overwrite existing files |

### `devops tls homelab`

**Generate complete Homelab TLS bundle (Root CA, Wildcard + Stack Services Cert).**

```bash
devops tls homelab [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | `~/.config/devops-cli/tls` | Directory to save certificates |
| `--domain`, `-d` | `string` | - | Additional custom domains to include in SANs |
| `--ip`, `-i` | `string` | - | Additional custom IP addresses to include in SANs |
| `--overwrite`, `-f` | `boolean` | - | Regenerate all existing certificates |

### `devops tls inspect`

**Inspect and display metadata of an X.509 certificate.**

```bash
devops tls inspect <cert_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<cert_path>` | `path` | Yes | Path to X.509 certificate file (.crt or .pem) |

### `devops tls verify`

**Verify an X.509 certificate cryptographic chain against a CA certificate.**

```bash
devops tls verify [OPTIONS] <cert_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<cert_path>` | `path` | Yes | Path to leaf certificate file (.crt or .pem) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--ca-cert`, `-ca` | `path` | `~/.config/devops-cli/tls/ca.crt` | Path to Root CA certificate file (ca.crt) |

### `devops tls enable-k8s`

**Generate and apply TLS secrets (kubernetes.io/tls) across Kubernetes namespaces.**

```bash
devops tls enable-k8s [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--context`, `-c` | `string` | - | Kubernetes cluster context (e.g. minikube, default) |
| `--tls-dir` | `path` | `~/.config/devops-cli/tls` | Directory with generated TLS certificates |
| `--secret-name` | `string` | `homelab-tls` | Kubernetes TLS secret name to create |
| `--namespace`, `-n` | `string` | - | Target namespaces to deploy TLS secret into |
| `--overwrite`, `-f` | `boolean` | - | Regenerate certs if missing |

---

## devops cert

TLS certificate generation and management (alias for tls).

X.509 TLS certificate generation, inspection, verification, and Kubernetes secrets.

### `devops cert ca`

**Generate a self-signed Root Certificate Authority (CA) key pair.**

```bash
devops cert ca [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | `~/.config/devops-cli/tls` | Directory to save CA certificate and key |
| `--common-name`, `-cn` | `string` | `Homelab DevOps Root CA` | Common Name for the Root CA |
| `--organization`, `-org` | `string` | `Homelab DevOps` | Organization name |
| `--country`, `-c` | `string` | `US` | 2-letter country code |
| `--validity-days`, `-d` | `integer` | `3650` | Validity period in days |
| `--key-size`, `-k` | `integer` | `2048` | RSA key size in bits (2048 or 4096) |
| `--overwrite`, `-f` | `boolean` | - | Overwrite existing CA certificate and key |

### `devops cert cert`

**Generate an X.509 TLS certificate signed by local CA or self-signed.**

```bash
devops cert cert [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--common-name`, `-cn` | `string` | `localhost` | Primary Common Name or domain |
| `--san`, `-s` | `string` | - | Subject Alternative Names (DNS names or IP addresses) |
| `--ca-cert` | `path` | - | Path to signing CA certificate (ca.crt) |
| `--ca-key` | `path` | - | Path to signing CA private key (ca.key) |
| `--output-dir`, `-o` | `path` | `~/.config/devops-cli/tls` | Directory to save certificate and key |
| `--validity-days`, `-d` | `integer` | `365` | Validity period in days |
| `--key-size`, `-k` | `integer` | `2048` | RSA key size in bits (2048 or 4096) |
| `--organization`, `-org` | `string` | `Homelab DevOps` | Organization name |
| `--overwrite`, `-f` | `boolean` | - | Overwrite existing files |

### `devops cert homelab`

**Generate complete Homelab TLS bundle (Root CA, Wildcard + Stack Services Cert).**

```bash
devops cert homelab [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | `~/.config/devops-cli/tls` | Directory to save certificates |
| `--domain`, `-d` | `string` | - | Additional custom domains to include in SANs |
| `--ip`, `-i` | `string` | - | Additional custom IP addresses to include in SANs |
| `--overwrite`, `-f` | `boolean` | - | Regenerate all existing certificates |

### `devops cert inspect`

**Inspect and display metadata of an X.509 certificate.**

```bash
devops cert inspect <cert_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<cert_path>` | `path` | Yes | Path to X.509 certificate file (.crt or .pem) |

### `devops cert verify`

**Verify an X.509 certificate cryptographic chain against a CA certificate.**

```bash
devops cert verify [OPTIONS] <cert_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<cert_path>` | `path` | Yes | Path to leaf certificate file (.crt or .pem) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--ca-cert`, `-ca` | `path` | `~/.config/devops-cli/tls/ca.crt` | Path to Root CA certificate file (ca.crt) |

### `devops cert enable-k8s`

**Generate and apply TLS secrets (kubernetes.io/tls) across Kubernetes namespaces.**

```bash
devops cert enable-k8s [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--context`, `-c` | `string` | - | Kubernetes cluster context (e.g. minikube, default) |
| `--tls-dir` | `path` | `~/.config/devops-cli/tls` | Directory with generated TLS certificates |
| `--secret-name` | `string` | `homelab-tls` | Kubernetes TLS secret name to create |
| `--namespace`, `-n` | `string` | - | Target namespaces to deploy TLS secret into |
| `--overwrite`, `-f` | `boolean` | - | Regenerate certs if missing |

---

## devops telemetry

OpenTelemetry observability, tracing, and metrics management.

### `devops telemetry status`

**Display OpenTelemetry collector endpoint, Jaeger UI URL, and connection health.**

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
| `--name`, `-n` | `string` | `devops-cli.manual_test` | Name for test span |

### `devops telemetry open-ui`

**Print and show the Jaeger Query UI endpoint for inspecting traces.**

```bash
devops telemetry open-ui
```

---

## devops otel

OpenTelemetry observability and tracing (alias for telemetry).

OpenTelemetry observability, tracing, and metrics management.

### `devops otel status`

**Display OpenTelemetry collector endpoint, Jaeger UI URL, and connection health.**

```bash
devops otel status
```

### `devops otel test`

**Emit a test OpenTelemetry trace span and metric to the configured collector.**

```bash
devops otel test [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--name`, `-n` | `string` | `devops-cli.manual_test` | Name for test span |

### `devops otel open-ui`

**Print and show the Jaeger Query UI endpoint for inspecting traces.**

```bash
devops otel open-ui
```

---
