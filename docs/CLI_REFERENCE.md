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
- [`devops roadmap`](#devops-roadmap) — Read and write the roadmap on GitHub, its source of truth: issues, milestones and the project board.
- [`devops pr`](#devops-pr) — GitHub Pull Request workflows and reviews.
- [`devops gh`](#devops-gh) — GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation.
- [`devops tf`](#devops-tf) — OpenTofu and Terraform Infrastructure-as-Code operations.
- [`devops tls`](#devops-tls) — Generate and manage homelab TLS certificates and CAs.
- [`devops telemetry`](#devops-telemetry) — OpenTelemetry tracing, metrics, and Jaeger observability.
- [`devops cloudflare`](#devops-cloudflare) — Cloudflare Zero Trust tunnels and DNS management.
- [`devops serve`](#devops-serve) — FastAPI REST & OpenAPI Service Engine for remote automation, health probes, and metrics.
- [`devops test`](#devops-test) — Test suite orchestration, git-diff aware test selector, and load testing.
- [`devops pipeline`](#devops-pipeline) — Programmable containerized pipeline execution (Dagger).
- [`devops vault`](#devops-vault) — Enterprise HashiCorp Vault secret broker
- [`devops valkey`](#devops-valkey) — Valkey workstation caching and in-memory data store
- [`devops sandbox`](#devops-sandbox) — Isolated workload sandbox container lifecycle engine.
- [`devops dashboard`](#devops-dashboard) — Interactive terminal UI dashboard for workstation situational awareness.
- [`devops tui`](#devops-tui) — Interactive terminal UI dashboard (alias)
- [`devops status`](#devops-status) — Inspect published operational status of upstream platforms (GitHub, Cloudflare)
- [`devops format`](#devops-format) — Automatically apply code formatting in-place (ruff format).
- [`devops lint`](#devops-lint) — Run static analysis checks and automatically apply fixes (ruff check --fix).

---

## devops repos

Clone, synchronize, and manage organization repositories.

### `devops repos clone-org`

**Clone all repos from a GitHub org into `repos/<org>/.`.**

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
| `--private` / `--no-private` | `boolean` | `True` | - |
| `--forks` / `--no-forks` | `boolean` | - | - |

### `devops repos clone`

**Clone an individual repository into `repos/<org>/<name>/.` (or `repos/_standalone/<name>/.`).**

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
| `--pull` / `--no-pull` | `boolean` | `True` | - |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops repos sync`

**Fetch (and optionally pull) all tracking branches across repos.**

```bash
devops repos sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--pull` / `--no-pull` | `boolean` | `True` | - |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

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
| `--minikube` / `--no-minikube` | `boolean` | `True` | Install the kubectl, helm and minikube devcontainer feature. |
| `--home-volume` | `string` | - | Custom volume name for /home/vscode (defaults to `<project_name>-home`). |
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

### `devops devcontainer unlock-keyring`

**Create or unlock the gnome-keyring login keyring that gh, git and devops store secrets in.**

```bash
devops devcontainer unlock-keyring
```

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
| `--skip-tools` | `boolean` | - | Skip bootstrapping missing DevOps tool binaries. |

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
| `--deploy` / `--no-deploy` | `boolean` | `True` | Auto-deploy Kubernetes stack after cluster startup. |
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

**Clean stale reviews, analysis, logs, traces, benchmarks and cache under the data directory.**

Clean stale reviews, analysis, logs, traces, benchmarks and cache under the data directory.

Child directories configured on their own, such as `data.reviews_dir`, are left alone.

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

**Show each tool's locked version and where its command is installed, without a request.**

```bash
devops install-tools status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--target-dir`, `-d` | `path` | `~/.local/bin` | Target directory path for operation. |

---

## devops k8s

Manage Kubernetes clusters, pods, services, and workloads.

### `devops k8s contexts`

**List kubeconfig contexts and mark the active one.**

```bash
devops k8s contexts
```

### `devops k8s switch-context`

**Switch active kubeconfig context and ensure cluster is running.**

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
| `--template`, `-t` | `boolean` | - | Render manifest as a template substituting domain from config or --domain before applying. |
| `--domain`, `-d` | `string` | - | Domain to substitute for template (defaults to k8s.domain in config.yaml). |

### `devops k8s render`

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

### `devops k8s logs`

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

### `devops k8s bootstrap`

**Bootstrap minikube Kubernetes cluster and deploy infrastructure/LLM stack.**

```bash
devops k8s bootstrap [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | `k8s` | Directory containing Kubernetes manifests. |
| `--auto-start` / `--no-auto-start` | `boolean` | `True` | Auto-start minikube if stopped. |
| `--stack`, `-s` | `string` | `all` | Stack to operate on: infra | llm | all. |

### `devops k8s bootstrap-openwebui`

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

### `devops k8s deploy-stack`

**Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to Kubernetes.**

Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to Kubernetes.

Right after the namespaces, it pushes the Secrets of the base rows, its stacks and every
detached stack whose namespace exists (`devops k8s push-secrets`), before anything that
reads them. A locked or missing keyring stops it before it applies anything.

```bash
devops k8s deploy-stack [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--k8s-dir` | `path` | `k8s` | Path to k8s/ config directory. |
| `--stack`, `-s` | `string` | `infra` | Stack to operate on: infra | llm | all. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--domain`, `-d` | `string` | - | Domain to substitute for template (defaults to k8s.domain in config.yaml). |
| `--wait` / `--no-wait` | `boolean` | `True` | Wait for Helm releases and workloads to become ready before returning. |
| `--timeout`, `-t` | `string` | `10m` | Timeout for Helm operations when waiting. |
| `--port-forward` / `--no-port-forward` | `boolean` | - | Start background port-forwarding daemons for deployed services. |
| `--configure-urls` / `--no-configure-urls` | `boolean` | - | Auto-configure devops-cli settings with detected Kubernetes service URLs. |
| `--push-secrets` / `--no-push-secrets` | `boolean` | `True` | Push the stacks' Secrets from the OS keyring before applying anything (--no-push-secrets for a cluster without a keyring). |
| `--argocd-revision` | `string` | - | Derive the Argo CD host overrides from this Git revision instead of each Application's targetRevision, to stage them before a release merges (Argo CD-managed clusters only). |
| `--dry-run` | `boolean` | - | Print the releases, manifests and Secrets (key names only) a deploy would apply, and run nothing. |

### `devops k8s sync-secrets`

**Copy chart-generated admin credentials (Argo CD, Grafana) from the cluster into the OS keyring.**

Copy chart-generated admin credentials (Argo CD, Grafana) from the cluster into the OS keyring.

The direction is cluster → workstation keyring, the reverse of `push-secrets`.

```bash
devops k8s sync-secrets [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `infra` | Stack to operate on: infra | llm | all. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops k8s push-secrets`

**Write the cluster's Secrets from the OS keyring (workstation keyring → cluster, the reverse of sync-secrets). Adopts live values the keyring lacks, generates the ones nobody types, and never replaces a live value without --rotate.**

```bash
devops k8s push-secrets [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `all` | Push the Secrets of one stack: base, infra, llm, logging, devops, or all (default). |
| `--only` | `string` | - | Push only this Secret, as NAMESPACE/NAME. Repeatable; replaces --stack. |
| `--github-account` | `string` | - | Machine account whose gh token becomes GH_TOKEN (default: k8s.github_account). |
| `--rotate` | `boolean` | - | Replace live values that differ from the keyring's. |
| `--restart` / `--no-restart` | `boolean` | `True` | Restart the workloads of each existing Secret whose data changed; --no-restart prints the commands instead. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |
| `--plan` | `boolean` | - | Read the keyring, the live Secrets and, for the machine account's token, gh's own record of the account (read-only; gh checks the token on github.com); print each key's state and the workloads a change would restart, and write nothing. |
| `--dry-run` | `boolean` | - | Make no request, reads included: print the requests a push would make, in order, with placeholders for every value. Wins over --plan. |

### `devops k8s run-job`

**Run a devops command as a Job in namespace devops, from CronJob devops-cli's template with only its arguments changed, follow its log and exit with its exit code.**

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
| `--wait` / `--no-wait` | `boolean` | `True` | Follow the Job's log and exit with its exit code; --no-wait prints the Job's name. |
| `--start-timeout` | `float` | `120.0` | Seconds to wait for the Job's pod to leave Pending. |
| `--dry-run` | `boolean` | - | Make no request, not even the CronJob read: print the kubectl requests a run would make, in order, with the Job's template parts as placeholders. |

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
| `--addressing`, `-a` | `string` | - | How to record endpoints: 'nodeport' writes a cluster-specific host and port, 'proxy' writes portable k8s:// service addresses needing no port-forward, 'fqdn' discovers Ingress hostnames and writes domain-based URLs. |

### `devops k8s service-url`

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
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops k8s port-forward`

**Port-forward k8s monitoring / LLM stack services to localhost ports.**

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
| `--pyroscope-port` | `integer` | `4040` | Local port for Pyroscope Continuous Profiling UI. |
| `--otel-port` | `integer` | `4318` | Local port for OpenTelemetry OTLP Traces (HTTP). |
| `--ollama-port` | `integer` | `11434` | Local port for Ollama. |
| `--open-webui-port` | `integer` | `3000` | Local port for Open-WebUI. |
| `--qdrant-port` | `integer` | `6333` | Local port for Qdrant HTTP. |
| `--valkey-port` | `integer` | `6379` | Local port for Valkey. |
| `--address` | `string` | `127.0.0.1` | Local address to bind for port-forwarding. |
| `--update-config` / `--no-update-config` | `boolean` | - | Update devops-cli configuration with port-forwarded service URLs. |

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
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops k8s rbac-audit`

**Audit RBAC RoleBindings and ServiceAccounts for overprivileged access.**

```bash
devops k8s rbac-audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | Audit only this namespace's RoleBindings and Roles; ClusterRoleBindings are always read. |

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
| `--key` | `path` | `~/.config/devops-cli/tls/tls.key` | Path to TLS private key file (.key or .pem). |
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
| `--secret-name` | `string` | `homelab-tls` | Name of the Kubernetes TLS secret to create or update. |
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
| `--strict` / `--no-strict` | `boolean` | `True` | Disallow additional undeclared properties. |
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
| `--follow`, `-f` / `--no-follow` | `boolean` | - | Continuously stream live log output. |
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

### `devops k8s security-stream`

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
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--output`, `-o` | `path` | - | Export discovered alerts to JSON file |

### `devops k8s gpu-matrix`

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

### `devops k8s doctor`

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
| `--template`, `-t` | `boolean` | - | Render manifest as a template substituting domain from config or --domain before applying. |
| `--domain`, `-d` | `string` | - | Domain to substitute for template (defaults to k8s.domain in config.yaml). |

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

### `devops docker cache`

**Introspect BuildKit multi-stage layer cache occupancy, reuse, and reclaimable space.**

```bash
devops docker cache [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--prune` | `boolean` | - | Reclaim unused BuildKit build cache records after reporting. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
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
| `--network`, `-n` | `string` | `isolated` | Network mode: isolated | sandbox_namespace | public_whitelist | local_whitelist | bridge |
| `--network-mode` | `string` | - | Multi-tier network mode: isolated | sandbox_namespace | public_whitelist | local_whitelist | bridge |
| `--public-whitelist` | `string` | - | Comma-separated public domains/IPs allowed for egress |
| `--local-whitelist` | `string` | - | Comma-separated local URLs/IPs allowed for egress |
| `--read-only` | `boolean` | - | Mount workspace as read-only |
| `--rootless` / `--root` | `boolean` | `True` | Run container with host user UID/GID |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops docker sign`

**Sign a container image using Sigstore Cosign (keyless or keyed).**

```bash
devops docker sign [OPTIONS] <image>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<image>` | `string` | Yes | Target container image reference (name:tag or digest) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key`, `-k` | `string` | - | Path to private key or keyring:\<name\> |
| `--keyless` / `--keyed` | `boolean` | `True` | Sign keylessly using OIDC/Fulcio |
| `--oidc-token` | `string` | - | OIDC identity token or keyring:\<name\> for keyless signing |
| `--annotation`, `-a` | `string` | - | Custom supply chain key=value annotations |
| `--upload` / `--no-upload` | `boolean` | `True` | Upload signature to remote registry |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops docker verify`

**Verify container image signature or attestation using Sigstore Cosign.**

```bash
devops docker verify [OPTIONS] <image>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<image>` | `string` | Yes | Target container image reference to verify |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--key`, `-k` | `string` | - | Path to public key or keyring:\<name\> |
| `--certificate-identity` | `string` | - | Expected signer certificate identity (SAN/email/URI) |
| `--certificate-oidc-issuer` | `string` | - | Expected OIDC certificate issuer URL |
| `--attestation` | `boolean` | - | Verify in-toto attestation predicate instead of signature |
| `--type` | `string` | - | Attestation predicate type (e.g. slsaprovenance, spdx, custom) |
| `--insecure-ignore-tlog` | `boolean` | - | Ignore Rekor transparency log verification |
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

**Sync every dashboard JSON file in a directory to Grafana.**

Sync every dashboard JSON file in a directory to Grafana.

Tries every file, then exits 1 if any failed. A dashboard Grafana holds as provisioned,
such as one the dashboard sidecar loads from a ConfigMap, is skipped rather than failed.

```bash
devops grafana dashboards sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | - | Directory path containing dashboard definitions. |

#### `devops grafana dashboards lint`

**Statically check dashboard JSON for layout, query, and binding defects.**

Statically check dashboard JSON for layout, query, and binding defects.

Catches overlapping panels, duplicate ids, unbound datasources, malformed PromQL, and a
uid two dashboards share before a dashboard reaches Grafana, where the only symptom is a
blank, wrong, or overwritten dashboard.

```bash
devops grafana dashboards lint [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Dashboard JSON file or directory to lint. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

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

### `devops prometheus analyze`

**Detect anomalies and project the trend of a metric series, computed locally.**

```bash
devops prometheus analyze [OPTIONS] <expr>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<expr>` | `string` | Yes | PromQL expression. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--start`, `-s` | `string` | `1h` | Start: duration ago (e.g. 1h) or Unix ts. |
| `--step` | `string` | `60s` | Query resolution step interval. |
| `--threshold`, `-t` | `float` | `3.0` | Z-score threshold before a sample is reported as anomalous. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

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

### `devops argo sync`

**Synchronize an ArgoCD application (or multi-cluster fleet when --fleet is passed).**

```bash
devops argo sync [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Application name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fleet` | `boolean` | - | Synchronize application across multi-cluster fleet |
| `--clusters`, `-c` | `string` | `dev,staging,prod` | Comma-separated list of target cluster names (e.g. dev,staging,prod) |
| `--fleet-name` | `string` | `default-fleet` | Fleet identifier group name |
| `--concurrency`, `-p` | `integer` | `3` | Maximum concurrent cluster synchronization workers |
| `--prune` | `boolean` | - | Allow deletion of resources omitted from the source repository. |
| `--force` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

### `devops argo cd`

```bash
devops argo cd COMMAND [ARGS]...
```

#### `devops argo cd fleet`

```bash
devops argo cd fleet COMMAND [ARGS]...
```

##### `devops argo cd fleet sync`

**Synchronize an application across a fleet of Kubernetes clusters with bounded concurrency.**

```bash
devops argo cd fleet sync [OPTIONS] <app_name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<app_name>` | `string` | Yes | Application name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--clusters`, `-c` | `string` | `dev,staging,prod` | Comma-separated list of target cluster names (e.g. dev,staging,prod) |
| `--fleet` | `string` | `default-fleet` | Fleet identifier group name |
| `--concurrency`, `-p` | `integer` | `3` | Maximum concurrent cluster synchronization workers |
| `--prune` | `boolean` | - | Allow deletion of resources omitted from the source repository. |
| `--force` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

#### `devops argo cd gitops`

```bash
devops argo cd gitops COMMAND [ARGS]...
```

##### `devops argo cd gitops watch`

**Monitor Kubernetes and Helm manifests for drift and trigger instant ArgoCD sync.**

```bash
devops argo cd gitops watch [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--path`, `-p` | `string` | `k8s` | Comma-separated paths or directories of manifests to monitor |
| `--app-name`, `-a` | `string` | `cluster` | Application name. |
| `--debounce-ms` | `integer` | `500` | Debounce delay in milliseconds to aggregate rapid modifications |
| `--interval`, `-i` | `float` | `1.0` | Watch polling interval in seconds |
| `--max-events` | `integer` | - | Maximum change events to process before exiting |
| `--once` | `boolean` | - | Check manifest drift once, trigger sync if drifted, and exit immediately |
| `--mode`, `-m` | `string` | `api` | Synchronization trigger mode ('api' or 'webhook') |
| `--prune` | `boolean` | - | Allow deletion of resources omitted from the source repository. |
| `--force` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

##### `devops argo cd gitops drift`

**Inspect and report local manifest state and detect any unstaged or modified files.**

```bash
devops argo cd gitops drift [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--path`, `-p` | `string` | `k8s` | Comma-separated paths or directories of manifests to inspect |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

##### `devops argo cd gitops sync`

**Trigger an immediate GitOps synchronization for an ArgoCD application.**

```bash
devops argo cd gitops sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--app-name`, `-a` | `string` | `cluster` | Application name. |
| `--mode`, `-m` | `string` | `api` | Synchronization trigger mode ('api' or 'webhook') |
| `--prune` | `boolean` | - | Allow deletion of resources omitted from the source repository. |
| `--force` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

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
| `--root-app`, `-f` | `path` | `k8s/argocd/bootstrap/bootstrap.yaml` | Path to root ArgoCD App-of-Apps manifest. |
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

#### `devops argo rollouts promote`

**Promote an in-progress Argo Rollout to the next progressive step or full release.**

```bash
devops argo rollouts promote [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Rollout name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | `default` | Kubernetes namespace. |
| `--full` | `boolean` | - | Skip all remaining steps and promote directly to full release |

#### `devops argo rollouts abort`

**Abort an in-progress Argo Rollout and revert immediately to the stable replica set.**

```bash
devops argo rollouts abort [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Rollout name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | `default` | Kubernetes namespace. |

#### `devops argo rollouts restart`

**Perform a restart rollout across all pods in an Argo Rollout.**

```bash
devops argo rollouts restart [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Rollout name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | `default` | Kubernetes namespace. |

#### `devops argo rollouts analyze`

**Evaluate metric rollback gates and trigger automated rollback on threshold violation.**

```bash
devops argo rollouts analyze [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Rollout name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | `default` | Kubernetes namespace. |
| `--error-rate-threshold`, `-e` | `float` | `1.0` | Maximum allowable HTTP 5xx error rate percentage before triggering automated rollback |
| `--auto-abort` / `--no-auto-abort` | `boolean` | `True` | Automatically trigger rollout abort when metric analysis violates threshold |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

### `devops argo fleet`

```bash
devops argo fleet COMMAND [ARGS]...
```

#### `devops argo fleet sync`

**Synchronize an application across a fleet of Kubernetes clusters with bounded concurrency.**

```bash
devops argo fleet sync [OPTIONS] <app_name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<app_name>` | `string` | Yes | Application name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--clusters`, `-c` | `string` | `dev,staging,prod` | Comma-separated list of target cluster names (e.g. dev,staging,prod) |
| `--fleet` | `string` | `default-fleet` | Fleet identifier group name |
| `--concurrency`, `-p` | `integer` | `3` | Maximum concurrent cluster synchronization workers |
| `--prune` | `boolean` | - | Allow deletion of resources omitted from the source repository. |
| `--force` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

### `devops argo gitops`

```bash
devops argo gitops COMMAND [ARGS]...
```

#### `devops argo gitops watch`

**Monitor Kubernetes and Helm manifests for drift and trigger instant ArgoCD sync.**

```bash
devops argo gitops watch [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--path`, `-p` | `string` | `k8s` | Comma-separated paths or directories of manifests to monitor |
| `--app-name`, `-a` | `string` | `cluster` | Application name. |
| `--debounce-ms` | `integer` | `500` | Debounce delay in milliseconds to aggregate rapid modifications |
| `--interval`, `-i` | `float` | `1.0` | Watch polling interval in seconds |
| `--max-events` | `integer` | - | Maximum change events to process before exiting |
| `--once` | `boolean` | - | Check manifest drift once, trigger sync if drifted, and exit immediately |
| `--mode`, `-m` | `string` | `api` | Synchronization trigger mode ('api' or 'webhook') |
| `--prune` | `boolean` | - | Allow deletion of resources omitted from the source repository. |
| `--force` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

#### `devops argo gitops drift`

**Inspect and report local manifest state and detect any unstaged or modified files.**

```bash
devops argo gitops drift [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--path`, `-p` | `string` | `k8s` | Comma-separated paths or directories of manifests to inspect |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

#### `devops argo gitops sync`

**Trigger an immediate GitOps synchronization for an ArgoCD application.**

```bash
devops argo gitops sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--app-name`, `-a` | `string` | `cluster` | Application name. |
| `--mode`, `-m` | `string` | `api` | Synchronization trigger mode ('api' or 'webhook') |
| `--prune` | `boolean` | - | Allow deletion of resources omitted from the source repository. |
| `--force` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

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

**Set a configuration value. Credentials go to the OS keyring; omit VALUE to type one hidden.**

```bash
devops config set <key> <value>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<key>` | `string` | Yes | Dotted config key, e.g. github.default_org. |
| `<value>` | `string` | No | Value to set. Omit it for a credential to type it at a hidden prompt, keeping it out of the shell history and the process list. |

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
| `<key>` | `string` | Yes | Dotted secret key, e.g. grafana.token. |
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

**Audit OS Keyring token health, backend status, and zero-plaintext secret compliance. Exits 1 when a config file cannot be read or parsed, reporting it unaudited.**

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

**Run the test suite, or only the tests covering the given source files.**

Run the test suite, or only the tests covering the given source files.

Passing paths narrows the run to the tests that import or conventionally cover them,
which is what makes this usable as a pre-commit hook on staged files.

```bash
devops ci test [OPTIONS] <paths>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<paths>` | `path` | No | Source or test files to verify. Narrows the run to covering tests; omit to run the full suite. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--verbose`, `-v` | `boolean` | - | Enable detailed logging output. |
| `-k` | `string` | - | Filter tests by keyword expression. |
| `-x` | `boolean` | - | Stop after first failure. |
| `-n`, `--numprocesses` | `string` | - | Number of parallel worker processes. |
| `--fallback` / `--no-fallback` | `boolean` | `True` | Run the full suite when a changed source has no covering tests, rather than reporting success without verifying it. |
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
| `--build-index` | `boolean` | - | Build on-demand coverage reverse index for fast test selection. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci lint`

**Run ruff linter across the project, automatically applying fixes by default.**

```bash
devops ci lint [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` / `--no-fix` | `boolean` | `True` | Auto-fix violations where possible. |
| `--check` | `boolean` | - | Check linting without applying automated fixes. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci format`

**Format codebase with ruff format (or verify in check-only mode with --check).**

```bash
devops ci format [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--check` | `boolean` | - | Check formatting without writing changes to files. |
| `--fix` / `--no-fix` | `boolean` | `True` | Apply formatting changes in-place. |
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

### `devops ci uv-check`

**Run uv check for fast static type checking and project validation.**

```bash
devops ci uv-check [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci lockfile`

**Verify lockfile consistency and freshness via uv lock --check.**

```bash
devops ci lockfile [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci outdated`

**Display outdated dependencies and packages via uv tree --outdated.**

```bash
devops ci outdated [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ci devcontainer`

**Validate devcontainer manifest configuration syntax.**

```bash
devops ci devcontainer [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
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
| `--fix` / `--no-fix` | `boolean` | `True` | Auto-fix lint/format before reporting status. |
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

### `devops scan report`

**Run every registered scanner and report deduplicated, correlated findings.**

```bash
devops scan report [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or file to scan with all registered scanners. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--scanner`, `-s` | `string` | - | Limit the run to these scanners (repeatable). Defaults to all registered. |
| `--sarif` | `path` | - | Write findings to this path as a SARIF 2.1.0 document. |
| `--min-severity` | `string` | - | Drop findings below this severity (CRITICAL|HIGH|MEDIUM|LOW|INFO). |
| `--suppress` | `path` | - | Suppression policy file; inherited policies are resolved via 'extends'. |
| `--show-suppressed` | `boolean` | - | List findings hidden by the suppression policy and the rule that hid them. |
| `--fail-on` | `string` | - | Exit non-zero when a finding at or above this severity survives suppression. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops scan sarif`

**Ingest a SARIF document from any tool and report it in the unified taxonomy.**

```bash
devops scan sarif [OPTIONS] <document>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<document>` | `path` | Yes | SARIF document to ingest, from this or any other SARIF-emitting tool. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--min-severity` | `string` | - | Drop findings below this severity (CRITICAL|HIGH|MEDIUM|LOW|INFO). |
| `--suppress` | `path` | - | Suppression policy file; inherited policies are resolved via 'extends'. |
| `--show-suppressed` | `boolean` | - | List findings hidden by the suppression policy and the rule that hid them. |
| `--fail-on` | `string` | - | Exit non-zero when a finding at or above this severity survives suppression. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

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
| `--provider`, `-p` | `string` | - | Provider: ollama, claude, copilot, openai, gateway |
| `--model`, `-m` | `string` | - | AI model identifier. |
| `--ollama-urls` | `string` | - | Ollama server base URLs (comma-separated). |
| `--ollama-max-parallel` | `integer` | - | Maximum number of simultaneous requests allowed per Ollama server node. |
| `--api-base-url` | `string` | - | Override the provider's API base URL (provider gateway uses ai.gateway_url). |
| `--api-key` | `string` | - | API key — stored in OS keyring, not config file. |
| `--max-retries` | `integer` | - | Maximum retry count for AI requests upon failure. |
| `--task`, `-t` | `string` | - | Set these for one task (chat, metadata, analysis, verification, compose, embedding) instead of every AI call. |

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

### `devops ai prewarm`

**Prewarm local models into GPU VRAM or evict idle models across cluster nodes.**

```bash
devops ai prewarm [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--model`, `-m` | `string` | - | Model name to prewarm or evict (defaults to configured AI model). |
| `--keep-alive`, `-k` | `string` | `1h` | Keep-alive duration for loaded model (e.g. 1h, 24h, forever, or 0 for eviction). |
| `--all-nodes`, `-a` / `--single-node` | `boolean` | `True` | Prewarm or evict model across all configured Ollama cluster nodes. |
| `--evict` | `boolean` | - | Evict the model from GPU VRAM immediately (sets keep_alive to 0). |
| `--url`, `-u` | `string` | - | Specific Ollama node URL to target instead of all candidate nodes. |
| `--json` | `boolean` | - | Output results as structured JSON. |

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
| `--force` | `boolean` | - | Overwrite existing instruction files (such as AGENTS.md). |
| `--file`, `-f` | `string` | - | Files to generate (repeatable). |

### `devops ai chat`

**Start an interactive chat with a Pydantic AI persona (tools, thinking, streaming, RAG).**

```bash
devops ai chat [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--persona`, `-p` | `string` | `architect` | Persona to chat with: devsecops, architect, pm, auditor, qa, challenger |
| `--model`, `-m` | `string` | - | AI model identifier. |
| `--context`, `-c` | `path` | - | Optional file to inject as background context (e.g. AGENTS.md). |
| `--rag` / `--no-rag` | `boolean` | `True` | Retrieve relevant semantic RAG context. |
| `--stream` / `--no-stream` | `boolean` | `True` | Stream response tokens. |
| `--tools` / `--no-tools` | `boolean` | `True` | Enable DevOps agent tools. |
| `--thinking` / `--no-thinking` | `boolean` | `True` | Enable model reasoning/thinking. |
| `--prewarm` / `--no-prewarm` | `boolean` | `True` | Prewarm the model before starting chat. |
| `--explain`, `-e` | `boolean` | - | Explain chat personas, tools, and reasoning modes. |

### `devops ai bundle-models`

**Bundle Ollama model metadata into tarball for air-gapped DevContainers.**

```bash
devops ai bundle-models [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | Bundle directory; a relative path is a data path under the main worktree, like data.models_dir (default: the configured models directory). |

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
| `--rag` / `--no-rag` | `boolean` | `True` | Retrieve relevant semantic RAG context. |
| `--thinking` / `--no-thinking` | `boolean` | `True` | Enable model reasoning/thinking. |
| `--stage-context-tokens` | `integer` | `4096` | Maximum context tokens from previous stages to carry into each pipeline stage (0 to disable budget). |

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
| `--multilingual`, `-m` | `boolean` | - | Enable multilingual polyglot scanning across Python, TypeScript, JavaScript, Go, Rust, Java, C#, C, C++, HCL, shell and Markdown. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai audit-library-usage`

**Audit workspace code for library API drift and deprecated calls.**

```bash
devops ai audit-library-usage [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--package`, `-p` | `string` | - | Filter by package distribution name. |
| `--target`, `-t`, `--dir`, `-d` | `path` | - | Target source directory to verify or analyze. |
| `--contracts-dir` | `path` | - | Path to directory containing exported library contract JSON files (default: libraries/ under the data directory where review data is kept). |
| `--fail-on-breaking` | `boolean` | - | Exit with code 1 if any breaking API drift issues are detected. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai pack-context`

**Pack and prune source code context to fit token budget while preserving signatures.**

```bash
devops ai pack-context [OPTIONS] <target_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target_path>` | `path` | Yes | Path to source code file to pack and prune. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--referenced`, `-r` | `string` | - | Comma-separated list of symbols referenced by caller to prioritize during pruning. |
| `--max-tokens` | `integer` | `1500` | Maximum token budget for packed context output. |
| `--strip-private` / `--no-strip-private` | `boolean` | `True` | Strip unreferenced private functions, methods, and attributes. |
| `--skeletonize` / `--no-skeletonize` | `boolean` | `True` | Replace function and method bodies with ellipsis (...) while preserving signatures. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai read`

**Inspect and read source code across 3 multi-scale focal zoom levels (Topology, Structural Outline, Deep Focal Window).**

```bash
devops ai read [OPTIONS] <target_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target_path>` | `path` | Yes | Target file path to read or inspect. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--inspect`, `-i` | `boolean` | - | Enable multi-scale semantic outline and inspection scanner. |
| `--level`, `-l` | `integer` | - | Focal zoom level: 0 (Topology: classes, functions, exports & hotspots), 1 (Structural Outline: control flow & signatures), 2 (Deep Focal Window: line slice). |
| `--lines`, `-L` | `string` | - | Line range for Level 2 focal window (e.g. '40:80'). |
| `--symbol`, `-s` | `string` | - | Target symbol name to inspect or focus on. |
| `--format`, `-f` | `string` | `markdown` | Output format: 'text', 'markdown', or 'json'. |
| `--repo`, `-r` | `path` | - | Repository or workspace root directory. |
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

**Measure the deterministic suppression layer against recorded review verdicts.**

Measure the deterministic suppression layer against recorded review verdicts.

The counts are reported for each labeller, and a label a deterministic check wrote is left
out unless --include-deterministic: scoring the layer against its own labels is circular.

```bash
devops ai prompt-eval [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--persona`, `-p` | `string` | `devsecops` | Persona whose recorded findings to measure the layer against. |
| `--dataset`, `-d` | `path` | - | Feedback dataset JSONL; a relative path resolves where review data is kept, like data.feedback_dataset_path: under the main worktree in devops-cli's own repository, else under ~/.local/share/devops-cli (default: the configured feedback dataset). |
| `--include-deterministic` | `boolean` | - | Also count records a deterministic check labelled; scoring the layer against its own labels is circular, so they are excluded by default. |
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

### `devops ai chaos-model`

**Model dependency chaos engineering suite simulating provider faults and validating local failovers.**

```bash
devops ai chaos-model [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--mode`, `-m` | `string` | `all` | Chaos fault mode to simulate (latency, rate-limit, timeout, malformed-json, all). |
| `--latency-ms` | `integer` | `500` | Synthetic network latency to inject in milliseconds. |
| `--error-rate` | `float` | `1.0` | Probability of fault injection between 0.0 and 1.0. |
| `--primary-provider` | `string` | `openai` | AI or cloud provider. |
| `--primary-model` | `string` | `gpt-4o` | AI model identifier. |
| `--fallback-provider` | `string` | `ollama` | Fallback AI provider to route execution to upon fault. |
| `--fallback-model` | `string` | `qwen2.5-coder:7b` | Fallback AI model to route execution to upon fault. |
| `--prompt` | `string` | `def test_health(): return True` | Prompt text or workload payload to evaluate. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai quiesce`

**Set the constellation quiesce flag with a reason; it stops nothing.**

```bash
devops ai quiesce [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--reason`, `-r` | `string` | `Operator requested emergency quiesce` | Reason recorded with the constellation quiesce flag. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai failover`

**Record a fallback route in the constellation flag; `devops ai gateway failover` reroutes requests.**

```bash
devops ai failover [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--target-provider` | `string` | `ollama` | Fallback AI provider to route execution to upon fault. |
| `--target-model` | `string` | `qwen2.5-coder:7b` | Fallback AI model to route execution to upon fault. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai resume`

**Clear the constellation quiesce or failover flag.**

```bash
devops ai resume [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai constellation`

**Show the constellation flag: state, reason and recorded fallback route.**

```bash
devops ai constellation [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

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
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Persona to review with: devsecops, architect, pm, auditor, qa or challenger; it wins over --all. Without it or --all, devsecops reviews alone. |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Has no effect: every review runs the staged pipeline, which does not read it. |
| `--full` | `boolean` | - | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and false-positive filtering. |
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
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |
| `--parallel` / `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire` / `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

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
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Persona to review with: devsecops, architect, pm, auditor, qa or challenger; it wins over --all. Without it or --all, devsecops reviews alone. |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--repo` | `path` | `.` | Repository root directory (default: current directory). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Has no effect: every review runs the staged pipeline, which does not read it. |
| `--full` | `boolean` | - | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and false-positive filtering. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |
| `--parallel` / `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire` / `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

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
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Persona to review with: devsecops, architect, pm, auditor, qa or challenger; it wins over --all. Without it or --all, devsecops reviews alone. |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--post` | `boolean` | - | Post the review as a comment on the GitHub PR. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Has no effect: every review runs the staged pipeline, which does not read it. |
| `--full` | `boolean` | - | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and false-positive filtering. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |
| `--parallel` / `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire` / `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

#### `devops ai review findings`

**Inspect structured findings for a review session.**

Inspect structured findings for a review session.

Each finding keeps its number, its place in findings.json, whatever filter the list
applies, and `devops review verify --index` takes that number. With `--candidates` the list
is candidates.json: every finding the review raised, the ones verification invalidated
included, numbered for `devops review verify --candidate`.

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
| `--invalidated` | `boolean` | - | Show INVALIDATED findings only. findings.json holds only those a later verdict invalidated; add --candidates for the ones verification invalidated. |
| `--verified` | `boolean` | - | Show verified findings only. |
| `--mitigated` | `boolean` | - | Filter findings by MITIGATED status |
| `--candidates` | `boolean` | - | List candidates.json: every finding the review raised, with the ones verification dropped. |
| `--severity` | `string` | - | Show only findings of this severity: CRITICAL, HIGH, MEDIUM, LOW or INFO (repeatable). |
| `--details`, `-d` | `boolean` | - | Display full finding descriptions and fix recommendations. |

#### `devops ai review verify`

**Record a person's or an agent's verdict on a review finding or candidate.**

Record a person's or an agent's verdict on a review finding or candidate.

Name one finding: `--index` takes the number `devops review findings` shows, `--title` a
substring of exactly one title, and `--candidate` the number `review findings --candidates`
shows. There is no default verdict, so `--status` is required. A candidate given VERIFIED
or MITIGATED moves into findings.json, unless findings.json already reports its defect under
another title: give that finding the verdict instead.

A verdict on a finding in findings.json is recorded on the candidate it reports too, and a
verdict on a candidate on its copy in findings.json, so both lists agree. When that copy also
reports another candidate of the same persona, title, location and description, give the
verdict to the copy with `--index`. Verdicts given on one session at once take turns.

`--adjudicator` records who gave the verdict: `human`, the default, or `agent`, which an AI
agent passes and the MCP `verify_finding` tool always sends. An agent cannot change a
person's verdict. Only a person's verdict ranks review history, teaches the learned catalog
(INVALIDATED) or records a mitigation in the ledger (MITIGATED). A later verdict withdraws
what the finding's earlier verdicts recorded there that it no longer stands behind: the
catalog entry once the finding is not INVALIDATED, so later reviews stop suppressing its
claim, and the ledger entry once it is not MITIGATED. An entry another verdict also recorded
stays, and one nothing else recorded is removed.

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
| `--index`, `-i` | `integer` | - | Number `review findings` shows for the finding: its place in findings.json, whatever filter the list applied. |
| `--title`, `-t` | `string` | - | Substring of exactly one finding title in findings.json. |
| `--candidate` | `integer` | - | Number `review findings --candidates` shows; a VERIFIED or MITIGATED verdict moves the candidate into findings.json. |
| `--status` | `string` | - | Verdict to record (required): VERIFIED | INVALIDATED | MITIGATED | UNVERIFIED. It withdraws what a person's earlier verdicts recorded that it no longer stands behind: the catalog entry of an INVALIDATED one, the ledger entry of a MITIGATED one. |
| `--adjudicator` | `choice (human|agent)` | `human` | Who gives the verdict: human, or agent for an AI agent, which cannot change a person's verdict. Only a person's verdict ranks review history and teaches the learned catalog and mitigations ledger. |
| `--reason`, `-r` | `string` | `` | Explanation or justification for the status change. |
| `--perimeter`, `-p` | `string` | - | Perimeter file path(s) protecting against finding recurrence (repeatable). |
| `--regression-test` | `string` | - | Path to regression test guarding against finding recurrence. |

#### `devops ai review stats`

**Compute and display review accuracy statistics across saved sessions.**

```bash
devops ai review stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--reviews-dir` | `path` | - | Directory containing review sessions. |

#### `devops ai review benchmark`

**Review the same files several times and report median time, LLM calls, tokens and backend busy share per stage.**

```bash
devops ai review benchmark [OPTIONS] <targets>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<targets>` | `path` | Yes | File(s) or directory(ies) to review on every run; keep them fixed to compare benchmarks. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--runs`, `-n` | `integer` | `3` | Number of reviews to run; the report takes medians across them. |
| `--pattern`, `-g` | `string` | `*` | Glob pattern for matching files. |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Persona to review with: devsecops, architect, pm, auditor, qa or challenger; it wins over --all. Without it or --all, devsecops reviews alone. |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |

#### `devops ai review score`

**Score saved review sessions against a label file: precision, recall and stability, each with its n.**

```bash
devops ai review score [OPTIONS] <sessions>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<sessions>` | `path` | No | Review session directories to score. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--labels` | `path` | - | Label file: the labelled inputs, the row map of each mapped session and the labels, such as tests/fixtures/review_labels/labels.json. |
| `--materialise-golden` | `path` | - | Write the label file's golden set into this directory as a git repository with one fixed commit, for a path review, and list the defects no tool can express. Takes no sessions. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

#### `devops ai review export-feedback`

**Append review verdicts to the JSONL feedback dataset, which `devops ai prompt-eval` reads.**

Append review verdicts to the JSONL feedback dataset, which `devops ai prompt-eval` reads.

Each session's findings.json and candidates.json are read, and only the findings whose
verdict the dataset does not hold yet are appended. An export that finds none leaves the
dataset as it was. Without --status only INVALIDATED verdicts are exported. The dataset
changes no prompt and no later review.

```bash
devops ai review export-feedback [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | JSONL dataset to append to (default: the configured data.feedback_dataset_path). |
| `--reviews-dir` | `path` | - | Directory containing review sessions. |
| `--status`, `-s` | `string` | `INVALIDATED` | Finding status to export: INVALIDATED, VERIFIED, MITIGATED, or ALL. |

#### `devops ai review corpus`

```bash
devops ai review corpus COMMAND [ARGS]...
```

##### `devops ai review corpus generate`

**Copy source files with one known defect injected into each, and record where.**

```bash
devops ai review corpus generate [OPTIONS] <sources>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<sources>` | `path` | Yes | Clean file(s) or directory(ies) to inject defects into; each becomes a folder of the corpus. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--out`, `-o` | `path` | - | Corpus directory to create (default: corpora/\<source\>-\<seed\> under the reviews directory). |
| `--seed` | `integer` | `1` | Seed choosing each file's defect; the same seed and files give the same corpus. |
| `--pattern`, `-g` | `string` | `*` | Glob pattern for matching files. |
| `--template`, `-t` | `string` | - | Defect template to inject (repeatable; default: all). |

##### `devops ai review corpus score`

**Score one arm of reviews of a corpus: which injected defects each run found, and what verification kept.**

```bash
devops ai review corpus score [OPTIONS] <corpus_dir>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<corpus_dir>` | `path` | Yes | Corpus directory created by `devops review corpus generate`. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Review session to score (repeatable; default: the latest review of the corpus). The sessions must have run the same review prompts. |
| `--runs`, `-n` | `integer` | - | Score the latest N reviews of the corpus together as one arm: how many runs found each injection, and each figure's mean and range across the runs. Refused with --session. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

#### `devops ai review samples`

```bash
devops ai review samples COMMAND [ARGS]...
```

##### `devops ai review samples list`

**List the sample catalog, and whether each sample is fetched at its commit.**

```bash
devops ai review samples list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |

##### `devops ai review samples fetch`

**Fetch samples at their pinned commits, verifying commit, licence files and paths.**

```bash
devops ai review samples fetch [OPTIONS] <names>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<names>` | `string` | No | Sample(s) to fetch (default: every sample, or every one in --category). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |

##### `devops ai review samples validate`

**Run devops ai tooling over fetched samples and save a JSON report per category.**

```bash
devops ai review samples validate [OPTIONS] <names>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<names>` | `string` | No | Sample(s) to validate (default: every sample, or every one in --category). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |
| `--review` | `boolean` | - | Also review each category's synthetic defect corpus and score it (calls the configured LLM). |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--seed` | `integer` | `1` | Seed choosing each file's defect; the same seed and files give the same corpus. |

#### `devops ai review templates`

```bash
devops ai review templates COMMAND [ARGS]...
```

##### `devops ai review templates list`

**List registered synthetic defect templates and their supported languages.**

```bash
devops ai review templates list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

##### `devops ai review templates sweep`

**Sweep synthetic defect templates over sample repositories, validating syntax and comment isolation.**

```bash
devops ai review templates sweep [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `string` | - | Specific defect template(s) to check (default: all registered templates). |
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |
| `--sample`, `-s` | `string` | - | Specific sample name(s) to check. |
| `--save` / `--no-save` | `boolean` | `True` | Save sweep results into the evaluation run store (default: true). |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

##### `devops ai review templates check`

**Sweep synthetic defect templates over sample repositories, validating syntax and comment isolation.**

```bash
devops ai review templates check [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `string` | - | Specific defect template(s) to check (default: all registered templates). |
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |
| `--sample`, `-s` | `string` | - | Specific sample name(s) to check. |
| `--save` / `--no-save` | `boolean` | `True` | Save sweep results into the evaluation run store (default: true). |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops ai review hallucinations`

```bash
devops ai review hallucinations COMMAND [ARGS]...
```

##### `devops ai review hallucinations list`

**List catalog entries: builtin ones shipped with the tool, and learned ones from this workspace.**

```bash
devops ai review hallucinations list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--learned` | `boolean` | - | Show learned entries only. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

##### `devops ai review hallucinations remove`

**Remove learned catalog entries; builtin entries cannot be removed.**

```bash
devops ai review hallucinations remove [OPTIONS] <ids>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<ids>` | `string` | No | Ids of learned entries to remove. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all-learned` | `boolean` | - | Remove every learned entry. |

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
| `--enhanced`, `-e` / `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated). |
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
| `--enhanced`, `-e` / `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated). |
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
| `--enhanced`, `-e` / `--no-enhanced` | `boolean` | `True` | Generate AI-enhanced metadata (pseudocode, complexity, last_updated). |
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
| `--include-kb` / `--no-include-kb` | `boolean` | `True` | Include bundled DevOps CLI Knowledge Base in docs collection. |
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

#### `devops ai rag drift`

**Detect staleness and drift between the working tree and the Qdrant vector index.**

```bash
devops ai rag drift [OPTIONS] <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Directory or file to index into vector store. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--auto-sync`, `--reindex`, `-s` | `boolean` | - | Automatically re-index stale and newly added files. |
| `--fail-on-drift` | `boolean` | - | Exit with code 1 if index drift or git commit divergence is detected. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai benchmark`

**Benchmark, evaluate, and peer-grade candidate AI models across engineering tasks.**

```bash
devops ai benchmark [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--models`, `-m` | `string` | - | Comma-separated candidate models (e.g. 'qwen2.5:0.5b,llama3.1:8b@http://gpu2:11434'). A model@url runs on that server, which gets the AI key only when it is the configured api_base_url, gateway_url or provider API. |
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

### `devops ai harness`

**Manage agent harness slots, sub-agent local offloading, and tiered synthesis.**

```bash
devops ai harness COMMAND [ARGS]...
```

#### `devops ai harness status`

**Display the harness slots as configured; nothing here checks a model is reachable.**

```bash
devops ai harness status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

#### `devops ai harness offload`

**Offload AST exploration, symbol cataloging, or file scouting to local sub-agent slot.**

```bash
devops ai harness offload [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `path` | `.` | Path to repository or source directory. |
| `--symbol`, `-s` | `string` | - | Symbol name (class or function) to inspect or search. |
| `--pattern`, `-p` | `string` | - | File glob pattern to scout. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

#### `devops ai harness run`

**Run the sub-agent's local AST or glob search for a task and report what it found.**

```bash
devops ai harness run [OPTIONS] <task>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<task>` | `string` | Yes | Task description to execute via 3-tier synthesis protocol |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-r` | `path` | `.` | Path to repository or source directory. |
| `--symbol`, `-s` | `string` | - | Symbol name (class or function) to inspect or search. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai ingest`

**Ingest library API contracts, type stubs, and documentation.**

```bash
devops ai ingest COMMAND [ARGS]...
```

#### `devops ai ingest library`

**Introspect an installed Python package and extract its public API contract.**

```bash
devops ai ingest library [OPTIONS] <package_name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<package_name>` | `string` | Yes | Introspect an installed Python package and extract its public API contract. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--max-depth`, `-d` | `integer` | `1` | Maximum module recursion depth for package introspection. |
| `--output-dir`, `-o` | `path` | - | Directory path for generated output files. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

#### `devops ai ingest docs`

**Ingest local or remote documentation into chunked markdown knowledge files.**

```bash
devops ai ingest docs [OPTIONS] <source>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<source>` | `string` | Yes | Ingest local or remote documentation into chunked markdown knowledge files. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | - | Directory path for generated output files. |
| `--max-pages`, `-p` | `integer` | `10` | Maximum number of items to return or display. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

#### `devops ai ingest index-libraries`

**Index exported library API contracts into Qdrant vector collection and Valkey cache.**

```bash
devops ai ingest index-libraries [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | - | Path to directory containing exported library contract JSON files (default: libraries/ under the data directory where review data is kept). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

#### `devops ai ingest query-library`

**Search library contracts and documentation via semantic search or exact symbol lookup.**

```bash
devops ai ingest query-library [OPTIONS] <query>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<query>` | `string` | Yes | Search library contracts and documentation via semantic search or exact symbol lookup. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--package`, `-p` | `string` | - | Filter by package distribution name. |
| `--exact`, `-e` | `boolean` | - | Perform exact qualified symbol lookup instead of semantic vector search. |
| `--top-k`, `-k` | `integer` | `5` | Maximum number of items to return or display. |
| `--contracts-dir` | `path` | - | Path to directory containing exported library contract JSON files (default: libraries/ under the data directory where review data is kept). |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

### `devops ai ast`

**Tree-Sitter multilingual AST concrete syntax tree parsing and code graph synthesis.**

```bash
devops ai ast COMMAND [ARGS]...
```

#### `devops ai ast parse`

**Parse source file concrete syntax tree and extract structural symbols.**

```bash
devops ai ast parse [OPTIONS] <file_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<file_path>` | `path` | Yes | Parse source file concrete syntax tree and extract structural symbols. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--query`, `-q` | `string` | `` | Optional Tree-Sitter S-expression query to execute against the syntax tree. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

#### `devops ai ast graph`

**Synthesize whole-repository symbol dependency and reference graph.**

```bash
devops ai ast graph [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | - | Target source directory to verify or analyze. |
| `--max-files`, `-n` | `integer` | `100` | Maximum source files to include. |
| `--output`, `-o` | `path` | - | Destination file path for output report or artifacts. |
| `--format`, `-f` | `string` | `json` | Output format for synthesized code graph: 'json' or 'dot'. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops ai gateway`

**LLM Gateway and distributed inference mesh management.**

```bash
devops ai gateway COMMAND [ARGS]...
```

#### `devops ai gateway status`

**Probe LLM Gateway health, latency, and circuit breaker metrics.**

```bash
devops ai gateway status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--gateway-url`, `-u` | `string` | - | Optional gateway base URL override. |
| `--provider`, `-p` | `string` | - | Gateway provider: litellm or portkey. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops ai gateway routes`

**List registered virtual models and target backend inference instances.**

```bash
devops ai gateway routes [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--gateway-url`, `-u` | `string` | - | Optional gateway base URL override. |
| `--provider`, `-p` | `string` | - | Gateway provider: litellm or portkey. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops ai gateway connect`

**Find the cluster's LLM gateway NodePort, verify it answers, and configure LAN review calls.**

```bash
devops ai gateway connect [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--context` | `string` | - | Kubernetes context to query (defaults to current). |
| `--namespace`, `-n` | `string` | `llm` | Kubernetes namespace. |
| `--service` | `string` | `llm-gateway` | Name of the Service running the gateway. |
| `--timeout` | `float` | `5.0` | Health probe timeout in seconds. |

#### `devops ai gateway failover`

**Trigger or test circuit-breaker failover of a virtual model to secondary backends.**

```bash
devops ai gateway failover [OPTIONS] <virtual_model>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<virtual_model>` | `string` | Yes | Virtual model alias to trigger failover for (devops-chat, devops-coder, devops-reasoning, devops-embedding). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--simulate` / `--no-simulate` | `boolean` | `True` | Simulate failover without altering active routing table. |
| `--force` | `boolean` | - | Bypass model capability tier minimum checks during failover. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops ai gateway scale`

**Inspect or scale vLLM inference backend serving configuration.**

```bash
devops ai gateway scale [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--replicas`, `-r` | `integer` | - | Replica count for backend deployment. |
| `--tensor-parallel-size`, `-tp` | `integer` | - | Tensor Parallelism degree for vLLM (e.g. 2). |
| `--apply` / `--no-apply` | `boolean` | - | Apply replica scale mutation to Kubernetes deployment via kubectl. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops ai gateway probe-backend`

**Directly probe health and latency of an inference backend.**

```bash
devops ai gateway probe-backend [OPTIONS] <backend>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<backend>` | `string` | Yes | Backend to probe: vllm or ollama. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--backend-url`, `-u` | `string` | - | Optional backend base URL override. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops ai gateway tune`

**Measure each deployment of a gateway model group and recommend routing weights.**

Measure each deployment of a gateway model group and recommend routing weights.

Each deployment is measured on its own from an ephemeral container attached to the gateway
pod, since the backends admit only the gateway. Read-only: the gateway configuration is not
changed.

```bash
devops ai gateway tune [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--model`, `-m` | `string` | `devops-review` | Gateway model group to measure. |
| `--concurrency`, `-c` | `string` | `1,4,8` | Comma-separated concurrency levels to measure. |
| `--rounds` | `integer` | `2` | Requests per worker at each concurrency level. |
| `--prompt-tokens` | `integer` | - | Prompt size in tokens (default: one review page for the analysis task). |
| `--max-tokens` | `integer` | `200` | Completion tokens requested per call. |
| `--gateway-url`, `-u` | `string` | - | Optional gateway base URL override. |
| `--namespace`, `-n` | `string` | `llm` | Namespace of the gateway deployment. |
| `--deployment` | `string` | `llm-gateway` | Gateway deployment to run the sweep in. |
| `--context` | `string` | - | Kubernetes context override. |
| `--image` | `string` | `python:3.14-slim` | Python image for the sweep container. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops ai gateway load`

**Report how busy each LLM backend and GPU was over a window, from Prometheus.**

Report how busy each LLM backend and GPU was over a window, from Prometheus.

Mean in flight is the gateway's call seconds per second on each deployment, so it covers the
Ollama nodes too; busy share and queue come from the vLLM servers themselves.

```bash
devops ai gateway load [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--window`, `-w` | `string` | `1h` | How far back to look, e.g. 30m, 2h or 1d. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops ai runs`

**Benchmark and evaluation runs, kept in the data directory and shared through Valkey.**

```bash
devops ai runs COMMAND [ARGS]...
```

#### `devops ai runs reindex`

**Rebuild the shared run index in Valkey from the run records in the data directory.**

```bash
devops ai runs reindex [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--mechanism`, `-m` | `choice (review-benchmark|sample-validation|corpus-score|review-score|gateway-tune|prompt-eval|ai-benchmark|template-sweep)` | - | Only index runs of this mechanism. |

#### `devops ai runs connect`

**Find the cluster's run index, check it answers, share runs through it, and index them.**

```bash
devops ai runs connect [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--context` | `string` | - | Kubernetes context (default: current). |
| `--namespace`, `-n` | `string` | `llm` | Namespace of the run index. |
| `--service` | `string` | `valkey-runs` | Service of the run index's Valkey. |
| `--secret-name` | `string` | `valkey-runs-auth` | Name of the Secret holding the Valkey password. |

#### `devops ai runs list`

**List recorded benchmark and evaluation runs.**

```bash
devops ai runs list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--mechanism`, `-m` | `choice (review-benchmark|sample-validation|corpus-score|review-score|gateway-tune|prompt-eval|ai-benchmark|template-sweep)` | - | Only list runs of this mechanism. |
| `--subject-key`, `-s` | `string` | - | Only list runs matching this subject key or prefix. |
| `--limit`, `-n` | `integer` | `20` | Maximum number of runs to show. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops ai runs show`

**Show details of a recorded run.**

```bash
devops ai runs show [OPTIONS] <run_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<run_id>` | `string` | Yes | Run ID or prefix to show. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops ai runs compare`

**Compare two runs or a run against its subject's baseline.**

```bash
devops ai runs compare [OPTIONS] <run_a> <run_b>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<run_a>` | `string` | Yes | First run ID (or current run if second run is omitted). |
| `<run_b>` | `string` | No | Second run ID (optional; defaults to subject baseline). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops ai runs check`

**Check a run against baseline for regressions past tolerances.**

```bash
devops ai runs check [OPTIONS] <run_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<run_id>` | `string` | Yes | Run ID to check against baseline. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--baseline`, `-b` | `string` | - | Override baseline run ID to compare against. |
| `--max-recall-drop` | `float` | `0.0` | Maximum allowable relative drop in recall (e.g. 0.05 for 5%). |
| `--max-duration-increase` | `float` | `0.15` | Maximum allowable relative increase in duration (e.g. 0.15 for 15%). |
| `--max-tokens-increase` | `float` | `0.2` | Maximum allowable relative increase in prompt tokens (e.g. 0.20 for 20%). |
| `--max-precision-drop` | `float` | `0.0` | Maximum allowable relative drop in a review score's lenient and strict precision (e.g. 0.05 for 5%). |
| `--max-stability-drop` | `float` | `0.0` | Maximum allowable relative drop in a review score's Jaccard and Fleiss kappa (e.g. 0.05 for 5%). |
| `--max-calls-increase` | `float` | `0.2` | Maximum allowable relative increase in model calls, a review's cost (e.g. 0.20 for 20%). |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops ai runs baseline`

```bash
devops ai runs baseline COMMAND [ARGS]...
```

##### `devops ai runs baseline set`

**Set a run as the baseline for its subject.**

```bash
devops ai runs baseline set <run_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<run_id>` | `string` | Yes | Run ID to designate as baseline. |

##### `devops ai runs baseline list`

**List all configured baselines.**

```bash
devops ai runs baseline list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

##### `devops ai runs baseline show`

**Show the baseline for a subject or run.**

```bash
devops ai runs baseline show [OPTIONS] <subject_or_run>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<subject_or_run>` | `string` | Yes | Subject key or run ID to inspect baseline for. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--mechanism`, `-m` | `choice (review-benchmark|sample-validation|corpus-score|review-score|gateway-tune|prompt-eval|ai-benchmark|template-sweep)` | - | Mechanism for subject lookup. |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops ai cost`

**Track approximate lifetime spend and manage model pricing.**

```bash
devops ai cost [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--by`, `-b` | `string` | `server` | Breakdown grouping dimension: server, model, provider, backend, stage, all. |
| `--days`, `-d` | `integer` | - | Filter usage to the last N days (default: all lifetime). |
| `--reference-model`, `-m` | `string` | - | Reference model for counterfactual pricing (default: gpt-4o-mini). |
| `--hardware-cost`, `-H` | `float` | - | Hardware purchase cost in USD to track pay-off against. |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml, markdown. |
| `--json` | `boolean` | - | First-class alias for --format json. |

#### `devops ai cost report`

**Generate detailed spend and token report across backend services and servers.**

```bash
devops ai cost report [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--by`, `-b` | `string` | `server` | Breakdown grouping dimension: server, model, provider, backend, stage, all. |
| `--days`, `-d` | `integer` | - | Filter usage to the last N days (default: all lifetime). |
| `--reference-model`, `-m` | `string` | - | Reference model for counterfactual pricing (default: gpt-4o-mini). |
| `--hardware-cost`, `-H` | `float` | - | Hardware purchase cost in USD to track pay-off against. |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml, prometheus. |
| `--json` | `boolean` | - | First-class alias for --format json. |

#### `devops ai cost roi`

**Monitor pay-off in value for local hardware purchases and local LLM savings.**

```bash
devops ai cost roi [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--hardware-cost`, `-H` | `float` | - | Total hardware purchase cost in USD (e.g. 1599.0 for GPU/workstation). |
| `--reference-model`, `-m` | `string` | - | Reference model for counterfactual pricing (default: gpt-4o-mini). |
| `--days`, `-d` | `integer` | - | Filter usage to the last N days (default: all lifetime). |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml. |
| `--json` | `boolean` | - | First-class alias for --format json. |

#### `devops ai cost prometheus`

**Export AI spend and usage metrics in Prometheus exposition format.**

```bash
devops ai cost prometheus
```

#### `devops ai cost update-pricing`

**Synchronize open-source industrial average pricing catalog from remote registry.**

```bash
devops ai cost update-pricing [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--source`, `-s` | `string` | - | Custom URL or file path for open-source model pricing dataset. |
| `--timeout`, `-t` | `float` | `15.0` | Request timeout in seconds. |

#### `devops ai cost list-pricing`

**List active token pricing rates per model and backend server.**

```bash
devops ai cost list-pricing [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--search`, `-s` | `string` | - | Substring or pattern filter for model/endpoint names. |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml. |
| `--json` | `boolean` | - | First-class alias for --format json. |

#### `devops ai cost set-price`

**Set custom token pricing override for a model or backend server.**

```bash
devops ai cost set-price <target> <prompt_rate> <completion_rate>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `string` | Yes | Target model identifier or backend server address (e.g. 'qwen2.5-coder:14b', 'localhost:11434'). |
| `<prompt_rate>` | `float` | Yes | Prompt token cost in USD per 1,000,000 tokens. |
| `<completion_rate>` | `float` | Yes | Completion token cost in USD per 1,000,000 tokens. |

#### `devops ai cost reset`

**Reset the lifetime AI spend ledger records.**

```bash
devops ai cost reset [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--yes`, `-y` | `boolean` | - | Confirm deletion of lifetime spend ledger records. |

### `devops ai spend`

**Alias for 'cost' command.**

```bash
devops ai spend [OPTIONS] COMMAND [ARGS]...
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--by`, `-b` | `string` | `server` | Breakdown grouping dimension: server, model, provider, backend, stage, all. |
| `--days`, `-d` | `integer` | - | Filter usage to the last N days (default: all lifetime). |
| `--reference-model`, `-m` | `string` | - | Reference model for counterfactual pricing (default: gpt-4o-mini). |
| `--hardware-cost`, `-H` | `float` | - | Hardware purchase cost in USD to track pay-off against. |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml, markdown. |
| `--json` | `boolean` | - | First-class alias for --format json. |

#### `devops ai spend report`

**Generate detailed spend and token report across backend services and servers.**

```bash
devops ai spend report [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--by`, `-b` | `string` | `server` | Breakdown grouping dimension: server, model, provider, backend, stage, all. |
| `--days`, `-d` | `integer` | - | Filter usage to the last N days (default: all lifetime). |
| `--reference-model`, `-m` | `string` | - | Reference model for counterfactual pricing (default: gpt-4o-mini). |
| `--hardware-cost`, `-H` | `float` | - | Hardware purchase cost in USD to track pay-off against. |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml, prometheus. |
| `--json` | `boolean` | - | First-class alias for --format json. |

#### `devops ai spend roi`

**Monitor pay-off in value for local hardware purchases and local LLM savings.**

```bash
devops ai spend roi [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--hardware-cost`, `-H` | `float` | - | Total hardware purchase cost in USD (e.g. 1599.0 for GPU/workstation). |
| `--reference-model`, `-m` | `string` | - | Reference model for counterfactual pricing (default: gpt-4o-mini). |
| `--days`, `-d` | `integer` | - | Filter usage to the last N days (default: all lifetime). |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml. |
| `--json` | `boolean` | - | First-class alias for --format json. |

#### `devops ai spend prometheus`

**Export AI spend and usage metrics in Prometheus exposition format.**

```bash
devops ai spend prometheus
```

#### `devops ai spend update-pricing`

**Synchronize open-source industrial average pricing catalog from remote registry.**

```bash
devops ai spend update-pricing [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--source`, `-s` | `string` | - | Custom URL or file path for open-source model pricing dataset. |
| `--timeout`, `-t` | `float` | `15.0` | Request timeout in seconds. |

#### `devops ai spend list-pricing`

**List active token pricing rates per model and backend server.**

```bash
devops ai spend list-pricing [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--search`, `-s` | `string` | - | Substring or pattern filter for model/endpoint names. |
| `--format`, `-f` | `string` | `table` | Output format: table, json, yaml. |
| `--json` | `boolean` | - | First-class alias for --format json. |

#### `devops ai spend set-price`

**Set custom token pricing override for a model or backend server.**

```bash
devops ai spend set-price <target> <prompt_rate> <completion_rate>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `string` | Yes | Target model identifier or backend server address (e.g. 'qwen2.5-coder:14b', 'localhost:11434'). |
| `<prompt_rate>` | `float` | Yes | Prompt token cost in USD per 1,000,000 tokens. |
| `<completion_rate>` | `float` | Yes | Completion token cost in USD per 1,000,000 tokens. |

#### `devops ai spend reset`

**Reset the lifetime AI spend ledger records.**

```bash
devops ai spend reset [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--yes`, `-y` | `boolean` | - | Confirm deletion of lifetime spend ledger records. |

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
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Persona to review with: devsecops, architect, pm, auditor, qa or challenger; it wins over --all. Without it or --all, devsecops reviews alone. |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Has no effect: every review runs the staged pipeline, which does not read it. |
| `--full` | `boolean` | - | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and false-positive filtering. |
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
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |
| `--parallel` / `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire` / `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

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
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Persona to review with: devsecops, architect, pm, auditor, qa or challenger; it wins over --all. Without it or --all, devsecops reviews alone. |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--repo` | `path` | `.` | Repository root directory (default: current directory). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Has no effect: every review runs the staged pipeline, which does not read it. |
| `--full` | `boolean` | - | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and false-positive filtering. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |
| `--parallel` / `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire` / `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

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
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Persona to review with: devsecops, architect, pm, auditor, qa or challenger; it wins over --all. Without it or --all, devsecops reviews alone. |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--post` | `boolean` | - | Post the review as a comment on the GitHub PR. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--summary`, `-s` | `boolean` | - | Has no effect: every review runs the staged pipeline, which does not read it. |
| `--full` | `boolean` | - | Print the whole report to the terminal: every finding with its details, every dependency and every network reference. By default the terminal lists CRITICAL to MEDIUM findings, with details for CRITICAL and HIGH, and gives LOW and INFO findings, dependencies and network references one line each that points at review.md. |
| `--explain`, `-e` | `boolean` | - | Explain code review personas, severity levels, and terminology. |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--pre-analysis-only` | `boolean` | - | Run pre-analysis only and skip subsequent stages. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--static-scan-only` | `boolean` | - | Run static scanning only and skip subsequent stages. |
| `--no-persona-review` | `boolean` | - | Disable multi-persona LLM inspection. |
| `--persona-review-only` | `boolean` | - | Run persona review only and skip subsequent stages. |
| `--no-verification` | `boolean` | - | Disable finding verification and false-positive filtering. |
| `--verification-only` | `boolean` | - | Run verification only and skip subsequent stages. |
| `--no-reranking` | `boolean` | - | Disable finding re-ranking and deduplication. |
| `--reranking-only` | `boolean` | - | Run re-ranking only and skip subsequent stages. |
| `--no-reporting` | `boolean` | - | Disable consolidated report generation. |
| `--reporting-only` | `boolean` | - | Run report generation only. |
| `--no-cache` | `boolean` | - | Bypass LLM response cache and force fresh inference. |
| `--force`, `-f` | `boolean` | - | Force fresh review execution without cache. |
| `--append-cache` | `boolean` | - | Append cached response to the LLM prompt as context instead of using it directly as the final response. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |
| `--parallel` / `--no-parallel` | `boolean` | `True` | Execute multi-file review stages concurrently using async worker pool. |
| `--logfire` / `--no-logfire` | `boolean` | - | Enable or disable Logfire structured observability and agent turn tracing. |

### `devops review findings`

**Inspect structured findings for a review session.**

Inspect structured findings for a review session.

Each finding keeps its number, its place in findings.json, whatever filter the list
applies, and `devops review verify --index` takes that number. With `--candidates` the list
is candidates.json: every finding the review raised, the ones verification invalidated
included, numbered for `devops review verify --candidate`.

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
| `--invalidated` | `boolean` | - | Show INVALIDATED findings only. findings.json holds only those a later verdict invalidated; add --candidates for the ones verification invalidated. |
| `--verified` | `boolean` | - | Show verified findings only. |
| `--mitigated` | `boolean` | - | Filter findings by MITIGATED status |
| `--candidates` | `boolean` | - | List candidates.json: every finding the review raised, with the ones verification dropped. |
| `--severity` | `string` | - | Show only findings of this severity: CRITICAL, HIGH, MEDIUM, LOW or INFO (repeatable). |
| `--details`, `-d` | `boolean` | - | Display full finding descriptions and fix recommendations. |

### `devops review verify`

**Record a person's or an agent's verdict on a review finding or candidate.**

Record a person's or an agent's verdict on a review finding or candidate.

Name one finding: `--index` takes the number `devops review findings` shows, `--title` a
substring of exactly one title, and `--candidate` the number `review findings --candidates`
shows. There is no default verdict, so `--status` is required. A candidate given VERIFIED
or MITIGATED moves into findings.json, unless findings.json already reports its defect under
another title: give that finding the verdict instead.

A verdict on a finding in findings.json is recorded on the candidate it reports too, and a
verdict on a candidate on its copy in findings.json, so both lists agree. When that copy also
reports another candidate of the same persona, title, location and description, give the
verdict to the copy with `--index`. Verdicts given on one session at once take turns.

`--adjudicator` records who gave the verdict: `human`, the default, or `agent`, which an AI
agent passes and the MCP `verify_finding` tool always sends. An agent cannot change a
person's verdict. Only a person's verdict ranks review history, teaches the learned catalog
(INVALIDATED) or records a mitigation in the ledger (MITIGATED). A later verdict withdraws
what the finding's earlier verdicts recorded there that it no longer stands behind: the
catalog entry once the finding is not INVALIDATED, so later reviews stop suppressing its
claim, and the ledger entry once it is not MITIGATED. An entry another verdict also recorded
stays, and one nothing else recorded is removed.

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
| `--index`, `-i` | `integer` | - | Number `review findings` shows for the finding: its place in findings.json, whatever filter the list applied. |
| `--title`, `-t` | `string` | - | Substring of exactly one finding title in findings.json. |
| `--candidate` | `integer` | - | Number `review findings --candidates` shows; a VERIFIED or MITIGATED verdict moves the candidate into findings.json. |
| `--status` | `string` | - | Verdict to record (required): VERIFIED | INVALIDATED | MITIGATED | UNVERIFIED. It withdraws what a person's earlier verdicts recorded that it no longer stands behind: the catalog entry of an INVALIDATED one, the ledger entry of a MITIGATED one. |
| `--adjudicator` | `choice (human|agent)` | `human` | Who gives the verdict: human, or agent for an AI agent, which cannot change a person's verdict. Only a person's verdict ranks review history and teaches the learned catalog and mitigations ledger. |
| `--reason`, `-r` | `string` | `` | Explanation or justification for the status change. |
| `--perimeter`, `-p` | `string` | - | Perimeter file path(s) protecting against finding recurrence (repeatable). |
| `--regression-test` | `string` | - | Path to regression test guarding against finding recurrence. |

### `devops review stats`

**Compute and display review accuracy statistics across saved sessions.**

```bash
devops review stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--reviews-dir` | `path` | - | Directory containing review sessions. |

### `devops review benchmark`

**Review the same files several times and report median time, LLM calls, tokens and backend busy share per stage.**

```bash
devops review benchmark [OPTIONS] <targets>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<targets>` | `path` | Yes | File(s) or directory(ies) to review on every run; keep them fixed to compare benchmarks. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--runs`, `-n` | `integer` | `3` | Number of reviews to run; the report takes medians across them. |
| `--pattern`, `-g` | `string` | `*` | Glob pattern for matching files. |
| `--persona`, `-p` | `choice (devsecops|architect|pm|auditor|qa|challenger)` | - | Persona to review with: devsecops, architect, pm, auditor, qa or challenger; it wins over --all. Without it or --all, devsecops reviews alone. |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--no-pre-analysis` | `boolean` | - | Disable pre-analysis and metadata refresh. |
| `--no-static-scan` | `boolean` | - | Disable static security scanning. |
| `--concurrency`, `-c` | `integer` | - | Max concurrent workers for parallel review and verification. |

### `devops review score`

**Score saved review sessions against a label file: precision, recall and stability, each with its n.**

```bash
devops review score [OPTIONS] <sessions>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<sessions>` | `path` | No | Review session directories to score. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--labels` | `path` | - | Label file: the labelled inputs, the row map of each mapped session and the labels, such as tests/fixtures/review_labels/labels.json. |
| `--materialise-golden` | `path` | - | Write the label file's golden set into this directory as a git repository with one fixed commit, for a path review, and list the defects no tool can express. Takes no sessions. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops review export-feedback`

**Append review verdicts to the JSONL feedback dataset, which `devops ai prompt-eval` reads.**

Append review verdicts to the JSONL feedback dataset, which `devops ai prompt-eval` reads.

Each session's findings.json and candidates.json are read, and only the findings whose
verdict the dataset does not hold yet are appended. An export that finds none leaves the
dataset as it was. Without --status only INVALIDATED verdicts are exported. The dataset
changes no prompt and no later review.

```bash
devops review export-feedback [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output`, `-o` | `path` | - | JSONL dataset to append to (default: the configured data.feedback_dataset_path). |
| `--reviews-dir` | `path` | - | Directory containing review sessions. |
| `--status`, `-s` | `string` | `INVALIDATED` | Finding status to export: INVALIDATED, VERIFIED, MITIGATED, or ALL. |

### `devops review corpus`

```bash
devops review corpus COMMAND [ARGS]...
```

#### `devops review corpus generate`

**Copy source files with one known defect injected into each, and record where.**

```bash
devops review corpus generate [OPTIONS] <sources>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<sources>` | `path` | Yes | Clean file(s) or directory(ies) to inject defects into; each becomes a folder of the corpus. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--out`, `-o` | `path` | - | Corpus directory to create (default: corpora/\<source\>-\<seed\> under the reviews directory). |
| `--seed` | `integer` | `1` | Seed choosing each file's defect; the same seed and files give the same corpus. |
| `--pattern`, `-g` | `string` | `*` | Glob pattern for matching files. |
| `--template`, `-t` | `string` | - | Defect template to inject (repeatable; default: all). |

#### `devops review corpus score`

**Score one arm of reviews of a corpus: which injected defects each run found, and what verification kept.**

```bash
devops review corpus score [OPTIONS] <corpus_dir>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<corpus_dir>` | `path` | Yes | Corpus directory created by `devops review corpus generate`. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--session`, `-s` | `string` | - | Review session to score (repeatable; default: the latest review of the corpus). The sessions must have run the same review prompts. |
| `--runs`, `-n` | `integer` | - | Score the latest N reviews of the corpus together as one arm: how many runs found each injection, and each figure's mean and range across the runs. Refused with --session. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops review samples`

```bash
devops review samples COMMAND [ARGS]...
```

#### `devops review samples list`

**List the sample catalog, and whether each sample is fetched at its commit.**

```bash
devops review samples list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |

#### `devops review samples fetch`

**Fetch samples at their pinned commits, verifying commit, licence files and paths.**

```bash
devops review samples fetch [OPTIONS] <names>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<names>` | `string` | No | Sample(s) to fetch (default: every sample, or every one in --category). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |

#### `devops review samples validate`

**Run devops ai tooling over fetched samples and save a JSON report per category.**

```bash
devops review samples validate [OPTIONS] <names>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<names>` | `string` | No | Sample(s) to validate (default: every sample, or every one in --category). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |
| `--review` | `boolean` | - | Also review each category's synthetic defect corpus and score it (calls the configured LLM). |
| `--all` | `boolean` | - | Review with devsecops, architect, qa, auditor and pm (not challenger). |
| `--seed` | `integer` | `1` | Seed choosing each file's defect; the same seed and files give the same corpus. |

### `devops review templates`

```bash
devops review templates COMMAND [ARGS]...
```

#### `devops review templates list`

**List registered synthetic defect templates and their supported languages.**

```bash
devops review templates list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops review templates sweep`

**Sweep synthetic defect templates over sample repositories, validating syntax and comment isolation.**

```bash
devops review templates sweep [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `string` | - | Specific defect template(s) to check (default: all registered templates). |
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |
| `--sample`, `-s` | `string` | - | Specific sample name(s) to check. |
| `--save` / `--no-save` | `boolean` | `True` | Save sweep results into the evaluation run store (default: true). |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

#### `devops review templates check`

**Sweep synthetic defect templates over sample repositories, validating syntax and comment isolation.**

```bash
devops review templates check [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `string` | - | Specific defect template(s) to check (default: all registered templates). |
| `--category`, `-c` | `choice (python|typescript-javascript|go|rust|java|csharp-dotnet|c-cpp|terraform|kubernetes-helm|dockerfile|shell|documentation)` | - | Only samples of this category (repeatable). |
| `--sample`, `-s` | `string` | - | Specific sample name(s) to check. |
| `--save` / `--no-save` | `boolean` | `True` | Save sweep results into the evaluation run store (default: true). |
| `--format`, `-f` | `string` | `table` | Output format: table or json. |

### `devops review hallucinations`

```bash
devops review hallucinations COMMAND [ARGS]...
```

#### `devops review hallucinations list`

**List catalog entries: builtin ones shipped with the tool, and learned ones from this workspace.**

```bash
devops review hallucinations list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--learned` | `boolean` | - | Show learned entries only. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

#### `devops review hallucinations remove`

**Remove learned catalog entries; builtin entries cannot be removed.**

```bash
devops review hallucinations remove [OPTIONS] <ids>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<ids>` | `string` | No | Ids of learned entries to remove. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all-learned` | `boolean` | - | Remove every learned entry. |

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

### `devops mcp export-schemas`

**Export FastMCP tool JSON schemas and instructions for MCP clients.**

```bash
devops mcp export-schemas [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | - | Destination directory for tool schema JSON files. |

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
| `--sync-readme` / `--no-sync-readme` | `boolean` | `True` | Synchronize Complete Command Matrix in README.md. |
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
| `--check-readme` / `--no-check-readme` | `boolean` | `True` | Synchronize Complete Command Matrix in README.md. |

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

### `devops docs compact`

**Compact historical documentation for completed release series.**

```bash
devops docs compact [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--series`, `-s` | `string` | `v0.2` | Release series prefix to compact (e.g., 'v0.2', 'v0.1'). |
| `--docs-dir`, `-d` | `path` | - | Path to repository docs/ directory (default: docs/). |
| `--archive-dir`, `-a` | `path` | - | Path to historical archive directory (default: docs/agent/archive/). |
| `--check` | `boolean` | - | Check if documentation compaction would make changes without modifying files. |
| `--roadmap-only` | `boolean` | - | Only compact docs/ROADMAP.md. |
| `--release-notes-only` | `boolean` | - | Only compact docs/RELEASE_NOTES.md. |
| `--log-only` | `boolean` | - | Only compact docs/LOG.md. |
| `--dry-run` | `boolean` | - | Show debug output of commands and AI requests without executing delegated subcommands or external write actions. |

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
| `--sync-docs` / `--no-sync-docs` | `boolean` | `True` | Regenerate CLI reference docs and sync README matrix. |
| `--changelog` / `--no-changelog` | `boolean` | `True` | Ensure CHANGELOG.md contains release header with current date. |
| `--create-pr`, `-p` | `boolean` | - | Create release branch, commit changes, and open a GitHub Release PR. |
| `--type`, `-t` | `string` | `feat` | Conventional commit prefix (feat or fix). |
| `--breaking`, `-b` | `boolean` | - | Flag release as containing breaking changes (!). |
| `--draft` / `--no-draft` | `boolean` | `True` | Create pull request or entity as draft. |
| `--root`, `-r` | `path` | - | Project repository root directory. |

### `devops release pr`

**Create release cut branch, commit version bumps, and open a GitHub Release Pull Request.**

```bash
devops release pr [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Target version string. |
| `--base`, `-b` | `string` | `main` | Base git branch to diff against (default: main). |
| `--draft` / `--no-draft` | `boolean` | `True` | Create pull request or entity as draft. |
| `--labels`, `-l` | `string` | `release` | Comma-separated labels to attach. |
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
| `--skip-ci` | `boolean` | - | Skip running the Gated CI test suite. |
| `--allow-dirty` | `boolean` | - | Allow uncommitted changes in git repository. |
| `--root`, `-r` | `path` | - | Project repository root directory. |

### `devops release notes`

**Print markdown release notes for a specified or current release version.**

Print markdown release notes for a specified or current release version.

Notes over GitHub's 125,000-character Release body limit are printed compact: each
category and entry title without its sub-bullets, then a link to the version's section
of CHANGELOG.md at its tag.

```bash
devops release notes [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Target version string. |
| `--raw` | `boolean` | - | Output raw string without formatting or shell escapes. |
| `--root`, `-r` | `path` | - | Project repository root directory. |

### `devops release sync-notes`

**Republish GitHub release descriptions from CHANGELOG.md.**

Republish GitHub release descriptions from CHANGELOG.md.

A release body is written once at publish time. Nothing in the repository could change
it afterwards, so a release published before the workflow disabled GitHub's generated
summary keeps carrying it, and an edited changelog entry never reaches the release it
describes. Notes over the Release body limit are sent in the compact form `release notes`
prints.

```bash
devops release sync-notes [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Target version string. |
| `--all` | `boolean` | - | Sync every published release rather than one version. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--root`, `-r` | `path` | - | Project repository root directory. |

### `devops release changelog`

**Compile and generate changelog entries from git commits or PR deliverables.**

```bash
devops release changelog [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--version`, `-v` | `string` | - | Target semantic version (e.g., 0.1.8). |
| `--update`, `-u` | `boolean` | - | Update CHANGELOG.md in-place with generated release notes. |
| `--from-tag` | `string` | - | Starting git tag or ref for changelog compilation. |
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

## devops roadmap

Read and write the roadmap on GitHub, its source of truth: issues, milestones and the project board.

### `devops roadmap migrate`

**Make GitHub the roadmap's source, once: bring the board in line with its template, fill unset Status, Priority, Value and Effort, retire release epics and milestones beyond the planning horizon, and record rejected roadmap ideas as issues closed as not planned. Prints the plan and a report, which lists the option renames, additions and removals a person makes in the board's field settings; writes only with --confirm, once the renames and additions are made.**

```bash
devops roadmap migrate [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml, the board template and docs/ROADMAP.md at (default: the repository's default branch). |
| `--confirm` | `boolean` | - | Make the planned writes to GitHub. Without it, migrate prints its plan only. |
| `--dry-run` | `boolean` | - | Make no request: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--plan` | `boolean` | - | Read GitHub, print the plan and report, write nothing, and end with the GraphQL points spent and left. Migrate without a mode flag does this. |

### `devops roadmap render`

**Write docs/ROADMAP.md from GitHub: the current release, the planned releases and the backlog by priority.**

```bash
devops roadmap render [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml, the board template and docs/ROADMAP.md at (default: the repository's default branch). |
| `--output`, `-o` | `path` | `docs/ROADMAP.md` | File render writes. |
| `--dry-run` | `boolean` | - | Make no request and write no file: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--plan` | `boolean` | - | Read GitHub and print the rendered file to stdout instead of writing it, ending with the GraphQL points spent and left. |

### `devops roadmap reprioritize`

**Hold the current release to its rules: after it starts only a critical fix joins it, a fix that takes it over the cap descopes one unstarted item, and Blocked, dependent, needs-split and stalled items are descoped, each with a reason comment. Once the release ships, close it, branch the next one and fill or trim it to the cap. The first run records the admitted set and moves nothing. Writes only with --confirm.**

```bash
devops roadmap reprioritize [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml, the board template and docs/ROADMAP.md at (default: the repository's default branch). |
| `--confirm` | `boolean` | - | Make the changes on GitHub. Without it, reprioritize prints its plan only. |
| `--dry-run` | `boolean` | - | Make no request: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--plan` | `boolean` | - | Read GitHub, print each change with its reason, write nothing, and end with the GraphQL points spent and left. Reprioritize without a mode flag does this. |

### `devops roadmap intake`

**Turn candidates into items: every open issue not on the board, and every board item intake left without a Priority. Each is checked for a duplicate among the board's items and the issues closed as not planned, gets a type, a priority, Value and Effort from the model with a reason comment, and goes to the backlog, or a critical fix to the release #740's admission rule allows. An open issue whose board card a person archived is a candidate too: intake restores the card, which keeps its values and milestone; close the issue as not planned to keep it off the roadmap. A candidate an agent files with --title and --body-file is labeled source/agent and held to the agent filing quota; a text that looks like it holds a secret is refused. --dry-run makes no request and prints the requests a run makes; --plan, the default, reads GitHub and calls the model, writes nothing and reports what it spent; --confirm makes the writes.**

```bash
devops roadmap intake [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml, the board template and docs/ROADMAP.md at (default: the repository's default branch). |
| `--issue` | `integer` | - | Only this issue (repeatable). |
| `--title` | `string` | - | Title of a candidate that is not an issue yet; intake files it only when it is not a duplicate. Needs --body-file. |
| `--body-file` | `path` | - | File holding the new candidate's body. Needs --title. |
| `--borrow-reason` | `choice (split|follow-up)` | - | Why the new candidate may open beyond the quota's allowance: a split of an item too big for one pull request, or a follow-up a reviewer or readiness check requires. Needs --source. |
| `--source` | `string` | - | Link the new candidate came from, such as the item it splits or the review that found it; the filed body ends with it. |
| `--filed-by` | `choice (agent|person)` | `agent` | Who files the new candidate: an agent's is labeled source/agent and counts toward the quota; a person's never does. |
| `--limit` | `integer` | - | Decide at most this many candidates, the oldest first, and leave the rest for a later run. Without it, intake decides every candidate. It keeps no record of what it decided; the intake that devops roadmap run and the Service run keeps one, so a candidate it left undecided waits behind the fresh ones. |
| `--dry-run` | `boolean` | - | Make no request, to GitHub or a model: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--plan` | `boolean` | - | Read GitHub and call the model, print each planned change and what the run spent, and write nothing. Intake without a mode flag does this. |
| `--confirm` | `boolean` | - | Plan as --plan does, then make the writes on GitHub. |

### `devops roadmap close`

**Close each item delivered to the current release, and cut the release once it holds no open item. Reads every pull request merged into release/vX.Y.Z and closes as completed each open issue a body closes with a closing keyword, commenting what changed and how it was verified (check runs and the task file's Acceptance Criteria). Reads each closed Release that still holds an open issue the same way first, closing the items of that Release its pull requests deliver, except one a person reopened, and naming the rest, which hold no cut. Once the release has no open item, one item closed as completed and no release pull request, writes docs/ROADMAP.md on release/vX.Y.Z in the clone at --root, bumps the version, pushes to release/vX.Y.Z (requiring Write role bypass on release ruleset 23059172), and opens the release pull request into the default branch. Lists completed items with no changelog fragment. Writes only with --confirm.**

```bash
devops roadmap close [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml, the board template and docs/ROADMAP.md at (default: the repository's default branch). |
| `--root` | `path` | `.` | The clone the cut runs git in (default: the current directory). |
| `--confirm` | `boolean` | - | Close the issues and make the cut. Without it, close prints its plan only. |
| `--dry-run` | `boolean` | - | Make no request and change no git ref: print the requests a run makes, in order, with placeholders for values a read gives. |
| `--plan` | `boolean` | - | Read GitHub, print each issue the run closes with its comment and the cut or what holds it, write nothing, and end with the GraphQL points spent and left once its store has sent a GraphQL request. Close without a mode flag does this. |

### `devops roadmap refine`

**Refine roadmap items to Ready with proposed design, tasks, and acceptance criteria. Evaluates Next-release and Backlog New items using code, documentation, and external research. An item whose model call fails is skipped and reported; the others are still refined, and refine then exits 1.**

```bash
devops roadmap refine [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml, the board template and docs/ROADMAP.md at (default: the repository's default branch). |
| `--source` | `path` | `.` | Path to the repository checkout (defaults to current directory). |
| `--item` | `integer` | - | Specific issue number to refine instead of selecting by priority. |
| `--limit` | `integer` | `3` | Maximum number of New items to refine in this run (default 3). |
| `--dry-run` | `boolean` | - | Make no request and change no git ref: print what refine would plan and run, with placeholders. |
| `--confirm` | `boolean` | - | Refine the items and write the proposed designs to GitHub. Without it, refine prints its plan only. |

### `devops roadmap run`

**Run the roadmap jobs that are due, in order: close, reprioritize and metrics, then intake and refine, and record each one's last success. Reprioritize is due on a ship, a cut or an un-cut the poll reads, on a change to an item in the current release, and once a day; intake decides at most 5 candidates a run and keeps a record of those it left beside the schedule. Without --confirm, or with --dry-run, prints the due list and runs nothing.**

```bash
devops roadmap run [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Repository as owner/name (default: this checkout's origin). |
| `--ref` | `string` | - | Branch, tag or commit to read .github/roadmap.toml, the board template and docs/ROADMAP.md at (default: the repository's default branch). |
| `--dry-run` | `boolean` | - | Make no request: print the due list of jobs and the reason each is due, and run nothing. |
| `--confirm` | `boolean` | - | Execute the due roadmap jobs. Without it, run prints the due list only. |

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

### `devops pr wait`

**Monitor PR checks, Copilot review sessions, and unresolved threads until ready.**

```bash
devops pr wait [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | No | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--interval`, `-i` | `integer` | `60` | Polling interval in seconds between check queries. |
| `--timeout`, `-t` | `integer` | `300` | Maximum time in seconds to wait for checks and reviews. |
| `--settle-timeout`, `-s` | `integer` | `60` | Grace period in seconds to allow Copilot review sessions to initialize. |
| `--require-reviews` / `--no-require-reviews` | `boolean` | `True` | Wait for active Copilot review sessions to conclude and check for unresolved threads. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

### `devops pr monitor`

**Monitor PR checks, Copilot review sessions, and unresolved threads until ready.**

```bash
devops pr monitor [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | No | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--interval`, `-i` | `integer` | `60` | Polling interval in seconds between check queries. |
| `--timeout`, `-t` | `integer` | `300` | Maximum time in seconds to wait for checks and reviews. |
| `--settle-timeout`, `-s` | `integer` | `60` | Grace period in seconds to allow Copilot review sessions to initialize. |
| `--require-reviews` / `--no-require-reviews` | `boolean` | `True` | Wait for active Copilot review sessions to conclude and check for unresolved threads. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

### `devops pr edit`

**Edit pull request base branch, title, body, or milestone.**

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
| `--milestone`, `-m` | `string` | - | Set the milestone for this pull request. |

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

### `devops pr ready`

**Mark a draft pull request as ready for review.**

```bash
devops pr ready [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--monitor`, `-m` | `boolean` | - | Automatically transition to monitoring checks and reviews after marking ready. |
| `--force`, `-f` | `boolean` | - | Bypass failing check verification and force ready status |

### `devops pr diff`

**View diff of a pull request.**

```bash
devops pr diff [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--color` | `string` | `auto` | Whether to colorize diff (always, never, auto). |

### `devops pr close`

**Close a pull request.**

```bash
devops pr close [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--comment`, `-c` | `string` | - | Comment text to include when closing the pull request. |
| `--delete-branch`, `-d` | `boolean` | - | Delete remote topic branch upon closing. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

### `devops pr check-readiness`

**Validate PR merge readiness: conflicts, draft state, checks, review threads and grounding.**

Validate PR merge readiness: conflicts, draft state, checks, review threads and grounding.

Grounding applies to every PR but the release PR (release/vX.Y.Z into the default branch)
and release-process PRs (chore/open-vX.Y.Z into release/vX.Y.Z): its
body closes exactly one issue, and it adds, modifies or renames that issue's
docs/agent/tasks/task-\<issue\>-*.md. Into a release/* branch it leaves CHANGELOG.md and
docs/ROADMAP.md to the cut and adds changelog.d/\<issue\>.md instead. Into release/vX.Y.Z,
the issue it closes is in release vX.Y.Z. A base branch without docs/agent/tasks/ is exempt.

```bash
devops pr check-readiness [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | No | PR number to verify (defaults to current branch PR) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--allow-draft` | `boolean` | - | Report a draft pull request as ready; GitHub still refuses to merge one. |
| `--allow-pending-checks` | `boolean` | - | Treat checks that are still running as acceptable rather than blocking. |
| `--allow-blocked-state` | `boolean` | - | Allow mergeable_state 'blocked' (e.g. when executing within CI while checks/approvals are pending) |
| `--auto-resolve` | `boolean` | - | Automatically resolve review discussion threads that have received a reply from someone other than the thread opener. |
| `--allow-replied-threads` | `boolean` | - | Treat review discussion threads that have received a reply from someone other than the thread opener as addressed rather than blocking. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

### `devops pr update`

**Update pull request branch with latest commits from its base branch.**

```bash
devops pr update [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | No | Pull request number to update (optional if --all is specified). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all`, `-a` | `boolean` | - | Update all open pull requests targeting the base branch. |
| `--base`, `-B` | `string` | - | Filter open pull requests by base branch (e.g. main, release/v0.2.20). |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--expected-head-sha` | `string` | - | Expected SHA of the pull request's HEAD ref for optimistic locking. |
| `--dispatch-ci` | `boolean` | - | Dispatch the ci.yml workflow on the head branch after updating. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops pr threads`

```bash
devops pr threads COMMAND [ARGS]...
```

#### `devops pr threads list`

**List PR review discussion threads, file locations, and comments.**

```bash
devops pr threads list [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--unresolved-only`, `-u` | `boolean` | - | Filter to display only unresolved review discussion threads. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

#### `devops pr threads reply`

**Post an in-thread reply to a PR review discussion thread.**

```bash
devops pr threads reply <thread_id> <body>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<thread_id>` | `string` | Yes | Review thread GraphQL ID (e.g. PRRT_...). |
| `<body>` | `string` | Yes | Reply message text to append directly to the review thread. |

#### `devops pr threads resolve`

**Programmatically mark one or more PR review discussion threads as resolved.**

```bash
devops pr threads resolve [OPTIONS] <thread_ids>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<thread_ids>` | `string` | Yes | One or more review thread GraphQL IDs to resolve. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--without-reply`, `-w` | `boolean` | - | Force resolution of review threads even if they lack a reply from someone other than the thread opener. |

#### `devops pr threads unresolve`

**Reopen a previously resolved PR review discussion thread.**

```bash
devops pr threads unresolve <thread_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<thread_id>` | `string` | Yes | Review thread GraphQL ID (e.g. PRRT_...). |

#### `devops pr threads resolve-all`

**Resolve all or replied review discussion threads for a pull request.**

```bash
devops pr threads resolve-all [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--only-replied` / `--all` | `boolean` | `True` | Only resolve threads that have received a reply from someone other than the thread opener. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

---

## devops gh

GitHub Views, Projects, Issues, Pages, Milestones, and Labels automation.

### `devops gh api`

**Execute a GitHub API request with token-bucket pacing, rate-limit backoff, and optional caching.**

```bash
devops gh api [OPTIONS] <endpoint>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<endpoint>` | `string` | Yes | GitHub API endpoint (e.g. repos/:owner/:repo/issues) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--method`, `-X` | `string` | - | HTTP method (GET, POST, PUT, DELETE, PATCH) |
| `--paginate` | `boolean` | - | Paginate across all result pages |
| `--jq`, `-q` | `string` | - | Filter JSON output using a jq expression |
| `--template`, `-t` | `string` | - | Format JSON output using a Go template |
| `--cache` | `boolean` | - | Cache response in-memory for subsequent reads |
| `--cache-ttl` | `float` | `15.0` | Cache TTL in seconds (default 15.0) |

### `devops gh rate-limit`

**Display GitHub REST and GraphQL API rate limits, quotas, and reset countdowns.**

```bash
devops gh rate-limit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

### `devops gh status`

**Display GitHub published operational status, key components, and active incidents.**

```bash
devops gh status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json` | `boolean` | - | Emit structured JSON service status summary |
| `--emit-telemetry` | `boolean` | - | Emit operational service status metrics over OpenTelemetry to Prometheus |

### `devops gh metrics`

**Display comprehensive project metrics including release frequency, PRs, commits, CI pass rates, and milestones.**

```bash
devops gh metrics [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--limit`, `-l` | `integer` | `10` | Number of recent releases to inspect |
| `--ci-limit` | `integer` | `50` | Number of recent CI workflow runs to inspect |
| `--milestone`, `-m` | `string` | - | Filter metrics to a specific milestone |
| `--repo`, `-R` | `string` | - | Target repository |
| `--json` | `boolean` | - | Emit structured JSON metrics report |
| `--emit-telemetry` | `boolean` | - | Emit project and velocity metrics over OpenTelemetry to Prometheus |

### `devops gh labels`

```bash
devops gh labels COMMAND [ARGS]...
```

#### `devops gh labels list`

**List all labels defined in the remote repository.**

```bash
devops gh labels list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

#### `devops gh labels sync`

**Synchronize repository labels against the declarative YAML schema.**

```bash
devops gh labels sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--file`, `-f` | `path` | `.github/labels.yml` | Path to declarative labels.yml file |
| `--repo`, `-R` | `string` | - | Target repository |
| `--dry-run` | `boolean` | - | Preview label reconciliation without making changes |

#### `devops gh labels audit`

**Audit open pull requests for mandatory type/ and scope/ taxonomy labels.**

```bash
devops gh labels audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh milestones`

```bash
devops gh milestones COMMAND [ARGS]...
```

#### `devops gh milestones list`

**List repository milestones and track issue completion rates.**

```bash
devops gh milestones list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--state`, `-s` | `string` | `all` | Milestone state filter (open, closed or all) |
| `--repo`, `-R` | `string` | - | Target repository |

#### `devops gh milestones status`

**Inspect detailed progress and issue health for a specific milestone.**

```bash
devops gh milestones status [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Release version, with or without the v (e.g. v0.2.11) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

#### `devops gh milestones close`

**Close the release milestone of a version, with or without its v.**

```bash
devops gh milestones close [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Release version, with or without the v (e.g. v0.2.11) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

#### `devops gh milestones edit`

**Edit a release milestone's title, description, state, or due date; fields left out stay as they are.**

```bash
devops gh milestones edit [OPTIONS] <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Release version, with or without the v (e.g. v0.2.21) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--title`, `-t` | `string` | - | New milestone title |
| `--description`, `-d` | `string` | - | New milestone description |
| `--state`, `-s` | `string` | - | New state (open or closed) |
| `--due-date` | `string` | - | ISO due date (YYYY-MM-DD) |
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh project`

```bash
devops gh project COMMAND [ARGS]...
```

#### `devops gh project status`

**Inspect the declarative GitHub Projects v2 template structure and views.**

```bash
devops gh project status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | - | Path to the project template JSON; defaults to .github/project-template.json at the repository root. |

#### `devops gh project sync`

**Find or create the project board from its template, link it, create the fields it lacks, and reconcile Status and Priority on the cards already on it. Sync adds no issue or pull request to the board: devops roadmap intake places issues, and a pull request's progress shows on its issue's card. Exits 1 when reconcile stops early.**

```bash
devops gh project sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | - | Path to the project template JSON; defaults to .github/project-template.json at the repository root. |
| `--repo`, `-R` | `string` | - | Target repository |
| `--dry-run` / `--no-dry-run` | `boolean` | - | Make no request and describe what a sync does. |
| `--reconcile-fields` / `--no-reconcile-fields` | `boolean` | `True` | Also reconcile Status and Priority on the cards already on the board, from issue and pull request state and labels. |

#### `devops gh project reconcile`

**Reconcile Status and Priority on the cards already on the board, listing each change and its source; the board owns Status, and reconcile never writes Milestone, Value or Effort or adds a card. A planned value the board's field has no option for is refused before any write. A run that stops early (mutation budget, GraphQL quota or a failed write) says why and how many planned changes remain, and exits 1. Running it again continues from there: after the reset when the quota stopped it, and once the cause is fixed when a write failed.**

```bash
devops gh project reconcile [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--project-number`, `-n` | `integer` | - | GitHub Projects v2 board number |
| `--state`, `-s` | `string` | `all` | Filter issue/PR states (open, closed, all) |
| `--repo`, `-R` | `string` | - | Target repository |
| `--dry-run` | `boolean` | - | Make no request, reads included, and list the requests a run makes. |
| `--plan` | `boolean` | - | Read the board and the repository and list the changes a run makes, making none. |

#### `devops gh project link`

**Link a GitHub Project v2 board to the repository.**

```bash
devops gh project link [OPTIONS] <project_number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<project_number>` | `integer` | Yes | GitHub Projects v2 board number |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

#### `devops gh project list`

**List available GitHub Projects v2 boards for user or organization.**

```bash
devops gh project list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--owner`, `-o` | `string` | - | Target user or organization |

#### `devops gh project audit`

**Audit the project board's views against the template.**

```bash
devops gh project audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | - | Path to the project template JSON; defaults to .github/project-template.json at the repository root. |
| `--repo`, `-R` | `string` | - | Target repository |

#### `devops gh project template`

**Display the raw GitHub Projects v2 declarative JSON template.**

```bash
devops gh project template [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | - | Path to the project template JSON; defaults to .github/project-template.json at the repository root. |

#### `devops gh project workflows`

```bash
devops gh project workflows COMMAND [ARGS]...
```

##### `devops gh project workflows list`

**List built-in project workflows, enabled statuses, and configuration links.**

```bash
devops gh project workflows list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--project-number`, `-n` | `integer` | - | GitHub Projects v2 board number |
| `--repo`, `-R` | `string` | - | Target repository |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops gh views`

```bash
devops gh views COMMAND [ARGS]...
```

#### `devops gh views list`

**List all standardized GitHub Projects v2 views configured for this workspace.**

```bash
devops gh views list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | - | Path to the project template JSON; defaults to .github/project-template.json at the repository root. |

#### `devops gh views spec`

**Output JSON schema specification for all configured project views.**

```bash
devops gh views spec [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | - | Path to the project template JSON; defaults to .github/project-template.json at the repository root. |

#### `devops gh views sync`

**Synchronize standardized views with the remote GitHub Projects v2 board.**

```bash
devops gh views sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | - | Path to the project template JSON; defaults to .github/project-template.json at the repository root. |
| `--repo`, `-R` | `string` | - | Target repository |

#### `devops gh views audit`

**Audit remote project views against standardized template specifications.**

```bash
devops gh views audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--template`, `-t` | `path` | - | Path to the project template JSON; defaults to .github/project-template.json at the repository root. |
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh pages`

```bash
devops gh pages COMMAND [ARGS]...
```

#### `devops gh pages status`

**Inspect GitHub Pages deployment status, URL, branch, and HTTPS enforcement.**

```bash
devops gh pages status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

#### `devops gh pages builds`

**List recent GitHub Pages build history and durations.**

```bash
devops gh pages builds [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |
| `--limit`, `-l` | `integer` | `5` | Number of builds to retrieve |

#### `devops gh pages build`

**Trigger a new deployment build for GitHub Pages.**

```bash
devops gh pages build [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

#### `devops gh pages verify`

**Verify local repository readiness for GitHub Pages publishing.**

```bash
devops gh pages verify [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dir`, `-d` | `path` | `.` | Path to project root directory |

### `devops gh issues`

```bash
devops gh issues COMMAND [ARGS]...
```

#### `devops gh issues list`

**List repository issues with milestone, taxonomy labels, and status.**

```bash
devops gh issues list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |
| `--state`, `-s` | `string` | `open` | Issue state: open, closed, all |
| `--milestone`, `-m` | `string` | - | Filter by milestone |
| `--label`, `-l` | `string` | - | Filter by label |
| `--limit` | `integer` | `30` | Max issues to return |

#### `devops gh issues create`

**Create a new issue linking milestone and taxonomy labels.**

```bash
devops gh issues create [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--title`, `-t` | `string` | - | Issue title |
| `--body`, `-b` | `string` | `` | Issue description |
| `--milestone`, `-m` | `string` | - | Target milestone |
| `--label`, `-l` | `string` | - | Taxonomy label (repeatable) |
| `--repo`, `-R` | `string` | - | Target repository |

#### `devops gh issues triage`

**Audit open issues for mandatory taxonomy labels, and report those not on the roadmap board as awaiting intake.**

```bash
devops gh issues triage [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

#### `devops gh issues status`

**Display aggregated issue counts by priority, type, and milestone.**

```bash
devops gh issues status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

#### `devops gh issues edit`

**Edit an existing issue title, body, state, milestone, or taxonomy labels.**

```bash
devops gh issues edit [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Issue number to edit. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--title`, `-t` | `string` | - | New issue title. |
| `--body`, `-b` | `string` | - | New issue body text. |
| `--state`, `-s` | `string` | - | New state (open or closed). |
| `--milestone`, `-m` | `string` | - | New milestone version, title, or number (e.g. v0.2.21). |
| `--clear-milestone` | `boolean` | - | Remove milestone linkage from the issue. |
| `--add-label` | `string` | - | Taxonomy label to attach (repeatable). |
| `--remove-label` | `string` | - | Taxonomy label to detach (repeatable). |
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh runs`

```bash
devops gh runs COMMAND [ARGS]...
```

#### `devops gh runs list`

**List recent workflow runs for the repository or branch.**

```bash
devops gh runs list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--limit`, `-n` | `integer` | `10` | Maximum number of items to return or display. |
| `--branch`, `-b` | `string` | - | Filter by branch |
| `--repo`, `-R` | `string` | - | Target repository |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

#### `devops gh runs view`

**View details and failure logs of a specific workflow run.**

```bash
devops gh runs view [OPTIONS] <run_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<run_id>` | `integer` | Yes | Workflow run database ID. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--log-failed` | `boolean` | - | Display logs for failed jobs or steps in the workflow run. |
| `--log` | `boolean` | - | Display full execution logs for the workflow run. |
| `--job`, `-j` | `string` | - | Filter workflow run logs to a specific job ID. |
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh branch-protection`

**Manage classic branch protection policies; does not cover rulesets.**

```bash
devops gh branch-protection COMMAND [ARGS]...
```

#### `devops gh branch-protection audit`

**Audit repository classic branch protection against declarative policy specification.**

```bash
devops gh branch-protection audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |
| `--branch`, `-b` | `string` | - | Target specific branch for protection audit or synchronization. |
| `--policy-file`, `-f` | `path` | `.github/branch-protection.yml` | Path to declarative branch protection policy YAML file. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

#### `devops gh branch-protection sync`

**Synchronize repository classic branch protection against declarative policy specification.**

```bash
devops gh branch-protection sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |
| `--branch`, `-b` | `string` | - | Target specific branch for protection audit or synchronization. |
| `--policy-file`, `-f` | `path` | `.github/branch-protection.yml` | Path to declarative branch protection policy YAML file. |
| `--dry-run` | `boolean` | - | Preview branch protection synchronization without applying mutations |

### `devops gh secrets`

```bash
devops gh secrets COMMAND [ARGS]...
```

#### `devops gh secrets sync`

**Synchronize repository secrets from OS Keyring or HashiCorp Vault with libsodium sealing.**

```bash
devops gh secrets sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--secret-names`, `-n` | `string` | - | Comma-separated list of secret names to synchronize. |
| `--repo`, `-R` | `string` | - | Target repository |
| `--source`, `-s` | `string` | `keyring` | Source store for secrets to synchronize (keyring or vault). |
| `--vault-path` | `string` | `secret/devops` | Vault KV-v2 secret path when source is vault (default: secret/devops). |
| `--dry-run` | `boolean` | - | Preview secret synchronization without mutations |

#### `devops gh secrets list`

**List Actions secrets configured in the repository (names only, values are hidden).**

```bash
devops gh secrets list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository |

### `devops gh pr`

```bash
devops gh pr COMMAND [ARGS]...
```

#### `devops gh pr list`

**List pull requests with base targeting and review status.**

```bash
devops gh pr list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--state`, `-s` | `string` | `open` | Filter by state (open, closed, merged, all). |
| `--limit`, `-n` | `integer` | `30` | Maximum number of items to return or display. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

#### `devops gh pr view`

**View details of a pull request.**

```bash
devops gh pr view [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

#### `devops gh pr checks`

**Check remote CI quality gate status on a pull request.**

```bash
devops gh pr checks [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

#### `devops gh pr wait`

**Monitor PR checks, Copilot review sessions, and unresolved threads until ready.**

```bash
devops gh pr wait [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | No | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--interval`, `-i` | `integer` | `60` | Polling interval in seconds between check queries. |
| `--timeout`, `-t` | `integer` | `300` | Maximum time in seconds to wait for checks and reviews. |
| `--settle-timeout`, `-s` | `integer` | `60` | Grace period in seconds to allow Copilot review sessions to initialize. |
| `--require-reviews` / `--no-require-reviews` | `boolean` | `True` | Wait for active Copilot review sessions to conclude and check for unresolved threads. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

#### `devops gh pr monitor`

**Monitor PR checks, Copilot review sessions, and unresolved threads until ready.**

```bash
devops gh pr monitor [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | No | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--interval`, `-i` | `integer` | `60` | Polling interval in seconds between check queries. |
| `--timeout`, `-t` | `integer` | `300` | Maximum time in seconds to wait for checks and reviews. |
| `--settle-timeout`, `-s` | `integer` | `60` | Grace period in seconds to allow Copilot review sessions to initialize. |
| `--require-reviews` / `--no-require-reviews` | `boolean` | `True` | Wait for active Copilot review sessions to conclude and check for unresolved threads. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

#### `devops gh pr edit`

**Edit pull request base branch, title, body, or milestone.**

```bash
devops gh pr edit [OPTIONS] <number>
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
| `--milestone`, `-m` | `string` | - | Set the milestone for this pull request. |

#### `devops gh pr create`

**Create a pull request with automatic release branch target validation.**

```bash
devops gh pr create [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--title`, `-t` | `string` | - | Title for the item or entity. |
| `--body`, `-b` | `string` | `` | Body or description text. |
| `--base`, `-B` | `string` | - | Base git branch to diff against (default: main). |
| `--draft`, `-d` | `boolean` | - | Create pull request or entity as draft. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

#### `devops gh pr ready`

**Mark a draft pull request as ready for review.**

```bash
devops gh pr ready [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--monitor`, `-m` | `boolean` | - | Automatically transition to monitoring checks and reviews after marking ready. |
| `--force`, `-f` | `boolean` | - | Bypass failing check verification and force ready status |

#### `devops gh pr diff`

**View diff of a pull request.**

```bash
devops gh pr diff [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--color` | `string` | `auto` | Whether to colorize diff (always, never, auto). |

#### `devops gh pr close`

**Close a pull request.**

```bash
devops gh pr close [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--comment`, `-c` | `string` | - | Comment text to include when closing the pull request. |
| `--delete-branch`, `-d` | `boolean` | - | Delete remote topic branch upon closing. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

#### `devops gh pr check-readiness`

**Validate PR merge readiness: conflicts, draft state, checks, review threads and grounding.**

Validate PR merge readiness: conflicts, draft state, checks, review threads and grounding.

Grounding applies to every PR but the release PR (release/vX.Y.Z into the default branch)
and release-process PRs (chore/open-vX.Y.Z into release/vX.Y.Z): its
body closes exactly one issue, and it adds, modifies or renames that issue's
docs/agent/tasks/task-\<issue\>-*.md. Into a release/* branch it leaves CHANGELOG.md and
docs/ROADMAP.md to the cut and adds changelog.d/\<issue\>.md instead. Into release/vX.Y.Z,
the issue it closes is in release vX.Y.Z. A base branch without docs/agent/tasks/ is exempt.

```bash
devops gh pr check-readiness [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | No | PR number to verify (defaults to current branch PR) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--allow-draft` | `boolean` | - | Report a draft pull request as ready; GitHub still refuses to merge one. |
| `--allow-pending-checks` | `boolean` | - | Treat checks that are still running as acceptable rather than blocking. |
| `--allow-blocked-state` | `boolean` | - | Allow mergeable_state 'blocked' (e.g. when executing within CI while checks/approvals are pending) |
| `--auto-resolve` | `boolean` | - | Automatically resolve review discussion threads that have received a reply from someone other than the thread opener. |
| `--allow-replied-threads` | `boolean` | - | Treat review discussion threads that have received a reply from someone other than the thread opener as addressed rather than blocking. |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |

#### `devops gh pr update`

**Update pull request branch with latest commits from its base branch.**

```bash
devops gh pr update [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | No | Pull request number to update (optional if --all is specified). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all`, `-a` | `boolean` | - | Update all open pull requests targeting the base branch. |
| `--base`, `-B` | `string` | - | Filter open pull requests by base branch (e.g. main, release/v0.2.20). |
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--expected-head-sha` | `string` | - | Expected SHA of the pull request's HEAD ref for optimistic locking. |
| `--dispatch-ci` | `boolean` | - | Dispatch the ci.yml workflow on the head branch after updating. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

#### `devops gh pr threads`

```bash
devops gh pr threads COMMAND [ARGS]...
```

##### `devops gh pr threads list`

**List PR review discussion threads, file locations, and comments.**

```bash
devops gh pr threads list [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo`, `-R` | `string` | - | Target repository in OWNER/REPO format. |
| `--unresolved-only`, `-u` | `boolean` | - | Filter to display only unresolved review discussion threads. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |

##### `devops gh pr threads reply`

**Post an in-thread reply to a PR review discussion thread.**

```bash
devops gh pr threads reply <thread_id> <body>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<thread_id>` | `string` | Yes | Review thread GraphQL ID (e.g. PRRT_...). |
| `<body>` | `string` | Yes | Reply message text to append directly to the review thread. |

##### `devops gh pr threads resolve`

**Programmatically mark one or more PR review discussion threads as resolved.**

```bash
devops gh pr threads resolve [OPTIONS] <thread_ids>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<thread_ids>` | `string` | Yes | One or more review thread GraphQL IDs to resolve. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--without-reply`, `-w` | `boolean` | - | Force resolution of review threads even if they lack a reply from someone other than the thread opener. |

##### `devops gh pr threads unresolve`

**Reopen a previously resolved PR review discussion thread.**

```bash
devops gh pr threads unresolve <thread_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<thread_id>` | `string` | Yes | Review thread GraphQL ID (e.g. PRRT_...). |

##### `devops gh pr threads resolve-all`

**Resolve all or replied review discussion threads for a pull request.**

```bash
devops gh pr threads resolve-all [OPTIONS] <number>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<number>` | `integer` | Yes | Pull request number. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--only-replied` / `--all` | `boolean` | `True` | Only resolve threads that have received a reply from someone other than the thread opener. |
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

### `devops tf graph`

**Inspect the in-memory resource dependency graph and blast radius.**

```bash
devops tf graph [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--resource`, `-r` | `string` | - | Resource address to compute blast radius for, e.g. aws_vpc.main. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops tf drift`

**Compare declared configuration against recorded state.**

```bash
devops tf drift [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

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

### `devops tf cost`

```bash
devops tf cost COMMAND [ARGS]...
```

#### `devops tf cost breakdown`

**Estimate monthly and hourly cloud infrastructure costs using Infracost.**

```bash
devops tf cost breakdown [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--mock` | `boolean` | - | Use deterministic mock cost output |
| `--max-monthly-cost` | `float` | - | Maximum allowable monthly cost budget threshold |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

#### `devops tf cost diff`

**Calculate cost delta between local Terraform code and baseline state using Infracost.**

```bash
devops tf cost diff [OPTIONS] <directory>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<directory>` | `path` | No | Target directory containing OpenTofu configuration. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--compare-to`, `-c` | `string` | - | Path to baseline Infracost JSON file for comparison |
| `--mock` | `boolean` | - | Use deterministic mock cost output |
| `--max-monthly-cost` | `float` | - | Maximum allowable monthly cost budget threshold |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

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
| `--common-name`, `-cn` | `string` | `Homelab DevOps Root CA` | Common Name for the certificate (e.g. *.example.internal). |
| `--organization`, `-org` | `string` | `Homelab DevOps` | Organization name. |
| `--country`, `-c` | `string` | `US` | 2-letter country code. |
| `--validity-days`, `-d` | `integer` | `3650` | Validity period in days. |
| `--key-size`, `-k` | `integer` | `2048` | RSA key size in bits (2048 or 4096). |
| `--overwrite`, `-f` | `boolean` | - | Overwrite existing files. |

### `devops tls cert`

**Generate an X.509 TLS certificate signed by local CA or self-signed.**

```bash
devops tls cert [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--common-name`, `-cn` | `string` | `homelab.local` | Common Name for the certificate (e.g. *.example.internal). |
| `--san`, `-s` | `string` | - | Subject Alternative Names (DNS names or IP addresses). |
| `--ca-cert` | `path` | - | Path to signing CA certificate (ca.crt). |
| `--ca-key` | `path` | - | Path to signing CA private key (ca.key). |
| `--output-dir`, `-o` | `path` | `~/.config/devops-cli/tls` | Directory to save certificate and key files. |
| `--validity-days`, `-d` | `integer` | `365` | Validity period in days. |
| `--key-size`, `-k` | `integer` | `2048` | RSA key size in bits (2048 or 4096). |
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
| `--secret-name` | `string` | `homelab-tls` | Kubernetes TLS secret name to create. |
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

### `devops telemetry connect`

**Find the cluster's OpenTelemetry collector, check it answers, and send telemetry there.**

```bash
devops telemetry connect [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--context` | `string` | - | Kubernetes context of the cluster running the collector (default: current). |
| `--namespace`, `-n` | `string` | `otel` | Namespace of the collector service. |
| `--service` | `string` | `otel-collector-opentelemetry-collector` | Name of the collector service. |
| `--save` / `--no-save` | `boolean` | `True` | Save the endpoint as telemetry.endpoint (default) or only check it. |

### `devops telemetry logfire`

**Display Logfire structured observability bridge status and token metrics.**

```bash
devops telemetry logfire [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json` | `boolean` | - | Output findings or metrics as JSON. |

### `devops telemetry test`

**Emit a test OpenTelemetry trace span and metric to the configured collector.**

```bash
devops telemetry test [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--name`, `-n` | `string` | `devops-cli.manual_test` | Name for test span. |
| `--logfire` | `boolean` | - | Emit test span via Logfire bridge. |

### `devops telemetry profile`

**Run a devops-cli command, or name a trace, and show its span waterfall as Jaeger recorded it.**

```bash
devops telemetry profile [OPTIONS] <command>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<command>` | `string` | No | devops-cli command line to run and profile; its first word must be 'devops' (e.g. 'devops k8s contexts'), and any other program is refused. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--trace-id`, `-t` | `string` | - | Trace ID to read from Jaeger and show, instead of running a command. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops telemetry open-ui`

**Print and show the Jaeger Query UI endpoint for inspecting traces.**

```bash
devops telemetry open-ui
```

### `devops telemetry semconv`

**The GenAI semantic conventions that LLM span attributes are checked against.**

```bash
devops telemetry semconv COMMAND [ARGS]...
```

#### `devops telemetry semconv refresh`

**Resolve the GenAI semantic conventions at a commit with weaver and rewrite the snapshot.**

```bash
devops telemetry semconv refresh [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--commit` | `string` | - | Full 40-character commit SHA of open-telemetry/semantic-conventions-genai to resolve. |

---

## devops cloudflare

Cloudflare Zero Trust tunnels and DNS management.

### `devops cloudflare status`

**Verify Cloudflare API token authentication and inspect zone status.**

```bash
devops cloudflare status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json`, `-j` | `boolean` | - | Output status details in JSON format |

### `devops cloudflare service-status`

**Display Cloudflare published operational status, key components, and active incidents.**

```bash
devops cloudflare service-status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json`, `-j` | `boolean` | - | Output status details in JSON format |
| `--emit-telemetry` | `boolean` | - | Emit operational service status metrics over OpenTelemetry to Prometheus |

### `devops cloudflare dns`

```bash
devops cloudflare dns COMMAND [ARGS]...
```

#### `devops cloudflare dns list`

**List DNS records in the designated Cloudflare zone.**

```bash
devops cloudflare dns list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--type`, `-t` | `string` | - | Filter by DNS record type (e.g. CNAME, A, TXT) |
| `--name`, `-n` | `string` | - | Filter by record hostname |
| `--zone-id`, `-z` | `string` | - | Override Cloudflare Zone ID |
| `--json`, `-j` | `boolean` | - | Output DNS records in JSON format |

#### `devops cloudflare dns sync`

**Synchronize CNAME records for root and subdomains to the Cloudflare tunnel.**

```bash
devops cloudflare dns sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--domain`, `-d` | `string` | - | Root domain name (e.g. example.com) |
| `--tunnel-cname`, `-c` | `string` | - | Target tunnel CNAME or Tunnel UUID |
| `--subdomains`, `-s` | `string` | - | Comma-separated subdomains to route to tunnel |
| `--zone-id`, `-z` | `string` | - | Override Cloudflare Zone ID |
| `--dry-run` | `boolean` | - | Preview DNS record reconciliation without applying changes |
| `--json`, `-j` | `boolean` | - | Output reconciliation summary in JSON format |

#### `devops cloudflare dns delete`

**Delete one or more DNS records by name or record ID.**

```bash
devops cloudflare dns delete [OPTIONS] <targets>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<targets>` | `string` | Yes | One or more DNS record names (e.g. chat.example.com) or record IDs to delete |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--type`, `-t` | `string` | - | Filter by DNS record type (e.g. CNAME, A, TXT) |
| `--force`, `-f` | `boolean` | - | Force deletion of records not marked as 'Managed by devops-cli' |
| `--zone-id`, `-z` | `string` | - | Override Cloudflare Zone ID |
| `--dry-run` | `boolean` | - | Preview DNS record deletions without applying changes |
| `--json`, `-j` | `boolean` | - | Output deletion results in JSON format |

### `devops cloudflare tunnel`

```bash
devops cloudflare tunnel COMMAND [ARGS]...
```

#### `devops cloudflare tunnel routes`

**Inspect Cloudflare tunnel ingress routes configuration.**

```bash
devops cloudflare tunnel routes [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--tunnel-id`, `-t` | `string` | - | Cloudflare Tunnel ID or name |
| `--account-id`, `-a` | `string` | - | Override Cloudflare Account ID |
| `--json`, `-j` | `boolean` | - | Output tunnel ingress routes in JSON format |

#### `devops cloudflare tunnel sync`

**Synchronize tunnel ingress rules to route subdomains to the cluster ingress controller.**

```bash
devops cloudflare tunnel sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--tunnel-id`, `-t` | `string` | - | Cloudflare Tunnel ID |
| `--domain`, `-d` | `string` | - | Domain to route through tunnel (e.g. example.com) |
| `--service` | `string` | `http://traefik.kube-system.svc.cluster.local:80` | Cluster ingress destination service URL |
| `--subdomains`, `-s` | `string` | - | Comma-separated subdomains to route to service |
| `--account-id`, `-a` | `string` | - | Override Cloudflare Account ID |
| `--dry-run` | `boolean` | - | Preview tunnel configuration without updating |
| `--json`, `-j` | `boolean` | - | Output updated tunnel configuration in JSON format |

### `devops cloudflare access`

```bash
devops cloudflare access COMMAND [ARGS]...
```

#### `devops cloudflare access status`

**Inspect Cloudflare Zero Trust Access applications and protected domains.**

```bash
devops cloudflare access status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--account-id`, `-a` | `string` | - | Override Cloudflare Account ID |
| `--json`, `-j` | `boolean` | - | Output access applications in JSON format |

#### `devops cloudflare access sync`

**Synchronize Cloudflare Zero Trust Access application and email allow-list policy.**

```bash
devops cloudflare access sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--domain`, `-d` | `string` | - | Domain to protect with Cloudflare Access |
| `--allowed-emails`, `-e` | `string` | - | Comma-separated emails permitted to access |
| `--bypass-ips`, `-b` | `string` | - | Comma-separated public IP addresses or CIDRs to bypass Access authentication (e.g. homelab public IP) |
| `--account-id`, `-a` | `string` | - | Override Cloudflare Account ID |
| `--dry-run` | `boolean` | - | Preview Access application changes without applying |
| `--json`, `-j` | `boolean` | - | Output Access sync summary in JSON format |

#### `devops cloudflare access policies`

**List Cloudflare Zero Trust Access policies for an application.**

```bash
devops cloudflare access policies [OPTIONS] <app_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<app_id>` | `string` | Yes | Access application ID |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--account-id`, `-a` | `string` | - | Override Cloudflare Account ID |
| `--json`, `-j` | `boolean` | - | Output policies in JSON format |

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
| `--docs` / `--no-docs` | `boolean` | `True` | Enable or disable Swagger UI (/docs) and ReDoc (/redoc). |
| `--service`, `-s` | `boolean` | - | Run continuous background service with GitHub webhook verification and per-repo queue. |

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
| `--network`, `-n` | `string` | `isolated` | Network mode: isolated | sandbox_namespace | public_whitelist | local_whitelist | bridge |
| `--network-mode` | `string` | - | Multi-tier network mode: isolated | sandbox_namespace | public_whitelist | local_whitelist | bridge |
| `--public-whitelist` | `string` | - | Comma-separated public domains/IPs allowed for egress |
| `--local-whitelist` | `string` | - | Comma-separated local URLs/IPs allowed for egress |
| `--read-only` | `boolean` | - | Mount workspace as read-only |
| `--rootless` / `--root` | `boolean` | `True` | Run container with host user UID/GID |
| `--dry-run` | `boolean` | - | Simulate test execution. |

### `devops test profile-memory`

**Deterministic async memory and connection pool profiler using tracemalloc.**

```bash
devops test profile-memory [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `string` | No | Target workload: 'http-pool', 'fastmcp', or importable 'module:function'. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--iterations`, `-i` | `integer` | `10` | Number of iterations to execute during profiling. |
| `--top`, `-t` | `integer` | `10` | Number of top memory allocation lines to display. |
| `--max-peak-mb` | `float` | `50.0` | Maximum acceptable peak memory threshold in megabytes. |
| `--fail-on-leak` / `--ignore-leak` | `boolean` | `True` | Exit with non-zero status if socket leaks are detected. |
| `--output`, `-o` | `path` | - | File path to export structured memory profiling report. |
| `--json` | `boolean` | - | Format report output as JSON. |
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

Inspect HashiCorp Vault cluster health and initialization status.

The health endpoint needs no token, and none is sent. The Token row names where the token
other commands would use comes from, and why a stored token is not used for this address.

```bash
devops vault status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--addr`, `-a` | `string` | - | Vault cluster HTTP API address |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops vault get`

**Fetch a secret from Vault, or from the OS keyring when Vault cannot answer.**

Fetch a secret from Vault, or from the OS keyring when Vault cannot answer.

The keyring answers only with no usable token, when Vault has no value at the path, or when
Vault is unreachable; never after Vault rejects the token. The output names the source.

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

Synchronize secrets from Vault into OS Keyring for offline/local CLI operations.

Reads Vault alone. A path with no secret fails, and a field named like the entry that holds
the `devops vault login` token is never written.

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

### `devops vault login`

**Authenticate with Vault natively via AppRole or the in-cluster ServiceAccount.**

Authenticate with Vault natively via AppRole or the in-cluster ServiceAccount.

With --store, the default, the token is kept in the OS keyring with the address and namespace
that issued it, and other vault commands use it for that Vault only. The command fails before
logging in when no encrypted, unlocked OS keyring can keep it. The token is never printed.

```bash
devops vault login [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--method`, `-m` | `string` | `approle` | Authentication method: approle or kubernetes. In a pod, use kubernetes with --no-store: it checks the ServiceAccount login without keeping the token, and the pod takes VAULT_TOKEN from its Vault integration. |
| `--role` | `string` | - | Vault role name (kubernetes method) |
| `--role-id` | `string` | - | AppRole role_id |
| `--secret-id` | `string` | - | AppRole secret_id |
| `--store` / `--no-store` | `boolean` | `True` | Keep the issued token in the OS keyring, for this Vault address and namespace only. --no-store checks the credentials without keeping the token: the form for CI and in-cluster runs, which take VAULT_TOKEN from their Vault integration. |

### `devops vault logout`

**Revoke the token `devops vault login` stored, at the Vault that issued it, and delete it.**

Revoke the token `devops vault login` stored, at the Vault that issued it, and delete it.

The revoke goes to the address and namespace stored with the token, whatever VAULT_ADDR says
now. The local copy is deleted even when the revoke fails, for example because Vault is
unreachable or the token has expired, and the output says the revoke did not happen.

```bash
devops vault logout
```

### `devops vault leases`

**Inspect, renew, or revoke tracked Vault dynamic secret leases.**

Inspect, renew, or revoke tracked Vault dynamic secret leases.

Every mode needs a usable token and fails before any request without one.

```bash
devops vault leases [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--renew` | `boolean` | - | Renew every tracked lease nearing expiry |
| `--revoke` | `string` | - | Revoke a single lease by id |

### `devops vault audit`

**Show which provider satisfied each credential lookup in this session.**

Show which provider satisfied each credential lookup in this session.

The trail records the logical secret name and the answering provider only; secret
values are never stored or rendered.

```bash
devops vault audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--json` | `boolean` | - | Emit the audit trail as JSON |

---

## devops valkey

Valkey workstation caching and in-memory data store

Valkey workstation caching and in-memory data store commands

### `devops valkey ping`

**Test connection and measure round-trip latency to the Valkey server.**

```bash
devops valkey ping [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

### `devops valkey info`

**Inspect server configuration, memory allocation, and operational metrics.**

```bash
devops valkey info [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--section`, `-s` | `string` | - | Specific INFO section (server, memory, clients, stats) |
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

### `devops valkey stats`

**Display quick diagnostic summary of server health, memory, and keys.**

```bash
devops valkey stats [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

### `devops valkey keys`

**List keys matching a glob pattern.**

```bash
devops valkey keys [OPTIONS] <pattern>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<pattern>` | `string` | No | Glob pattern to search for keys |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

### `devops valkey get`

**Retrieve string value stored at key.**

```bash
devops valkey get [OPTIONS] <key>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<key>` | `string` | Yes | Key to retrieve |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

### `devops valkey set`

**Set string value of key with optional expiration TTL.**

```bash
devops valkey set [OPTIONS] <key> <value>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<key>` | `string` | Yes | Key name to set |
| `<value>` | `string` | Yes | Value to associate with key |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--ex` | `integer` | - | Expiration timeout in seconds |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

### `devops valkey flush`

**Flush and purge keys from current or all databases.**

```bash
devops valkey flush [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all`, `-a` | `boolean` | - | Flush all databases instead of just active one |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

### `devops valkey backup`

**Trigger background RDB persistence snapshot (BGSAVE).**

```bash
devops valkey backup [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

### `devops valkey cli`

**Execute raw Valkey commands directly against the server.**

```bash
devops valkey cli [OPTIONS] <command_args>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<command_args>` | `string` | No | Optional command and arguments to execute directly (e.g. PING or DBSIZE) |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--host`, `-h` | `string` | - | Valkey server host |
| `--port`, `-p` | `integer` | - | Valkey server port |

---

## devops sandbox

Isolated workload sandbox container lifecycle engine.

### `devops sandbox deploy`

**Deploy an isolated background container sandbox with security containment.**

```bash
devops sandbox deploy [OPTIONS] <command>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<command>` | `string` | No | Optional container command |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--image`, `-i` | `string` | `python:3.14-slim` | Container image for the sandbox workload. |
| `--name`, `-n` | `string` | - | Friendly identifier name for the sandbox instance. |
| `--port`, `-p` | `integer` | - | Container port(s) to dynamically expose on available host ports. |
| `--workspace`, `-w` | `path` | `.` | Host workspace path to mount into container /workspace. |
| `--memory`, `-m` | `string` | `2g` | Memory limit for the container (e.g. 512m, 2g). |
| `--cpus`, `-c` | `float` | `2.0` | CPU quota limit for the container (e.g. 1.0, 2.0). |
| `--read-only` | `boolean` | `True` | Mount root filesystem as read-only with a tmpfs /tmp. |
| `--network` | `string` | `isolated` | Docker network mode (bridge | host | none). |
| `--network-mode` | `string` | - | Multi-tier network mode: isolated | sandbox_namespace | public_whitelist | local_whitelist | bridge |
| `--public-whitelist` | `string` | - | Comma-separated public domains/IPs allowed for egress |
| `--local-whitelist` | `string` | - | Comma-separated local URLs/IPs allowed for egress |
| `--env`, `-e` | `string` | - | Environment variable in KEY=VALUE format. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops sandbox status`

**Inspect status of deployed sandbox containers.**

```bash
devops sandbox status [OPTIONS] <instance_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<instance_id>` | `string` | No | Unique instance ID or name of the sandbox. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all`, `-a` | `boolean` | - | Apply operation across all registered sandbox instances. |
| `--json` | `boolean` | - | Output details in structured JSON format. |

### `devops sandbox stop`

**Gracefully stop and tear down a sandbox container.**

```bash
devops sandbox stop [OPTIONS] <instance_id>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<instance_id>` | `string` | No | Unique instance ID or name of the sandbox. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all`, `-a` | `boolean` | - | Apply operation across all registered sandbox instances. |
| `--timeout`, `-t` | `integer` | `10` | Graceful stop timeout in seconds before SIGKILL. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops sandbox exec`

**Execute a command inside an active sandbox container.**

```bash
devops sandbox exec [OPTIONS] <instance_id> <command>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<instance_id>` | `string` | Yes | Unique instance ID or name of the sandbox. |
| `<command>` | `string` | Yes | Command and arguments to execute inside sandbox |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--workdir`, `-w` | `string` | - | Working directory inside the container for command execution. |

### `devops sandbox probe`

**Probe endpoint readiness and service health across network protocols.**

```bash
devops sandbox probe [OPTIONS] <identifier>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<identifier>` | `string` | Yes | Unique instance ID or name of the sandbox. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--protocol`, `-p` | `string` | - | Network protocol(s) to probe (tcp, http, openapi, grpc). |
| `--path` | `string` | - | HTTP request path(s) to probe for readiness. |
| `--expected-status` | `string` | - | Expected HTTP response status code(s). |
| `--regex`, `-r` | `string` | - | Regex pattern to assert against HTTP response body. |
| `--latency-sla` | `float` | - | Maximum acceptable response latency budget in milliseconds. |
| `--timeout`, `-t` | `float` | `5.0` | Graceful stop timeout in seconds before SIGKILL. |
| `--json` | `boolean` | - | Output details in structured JSON format. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops sandbox metrics`

**Capture real-time cgroup v2 metrics and scrape Prometheus application metrics.**

```bash
devops sandbox metrics [OPTIONS] <identifier>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<identifier>` | `string` | Yes | Unique instance ID or name of the sandbox. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--prom-endpoint`, `-p`, `--path` | `string` | `/metrics` | Prometheus metrics scrape path (default /metrics). |
| `--timeout`, `-t` | `float` | `5.0` | HTTP timeout in seconds for Prometheus metrics scraping (default: 5.0). |
| `--warn-memory-pct` | `float` | `80.0` | Warning threshold percentage for container memory consumption. |
| `--warn-cpu-pct` | `float` | `85.0` | Warning threshold percentage for container CPU utilization. |
| `--latency-sla-ms` | `float` | - | Maximum acceptable average HTTP request latency SLA in milliseconds (disabled by default). |
| `--json` | `boolean` | - | Output details in structured JSON format. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops sandbox traces`

**Visualize distributed trace waterfall and cross-service latency for sandbox workloads.**

```bash
devops sandbox traces [OPTIONS] <identifier>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<identifier>` | `string` | No | Unique instance ID or name of the sandbox. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--trace-id`, `-t` | `string` | - | Specific OpenTelemetry trace ID to retrieve and visualize. |
| `--last`, `-l` | `boolean` | - | Visualize spans for the most recently executed trace. |
| `--probe` | `boolean` | - | Execute an endpoint health probe before visualizing the resulting trace. |
| `--jaeger-url` | `string` | - | Override Jaeger Query HTTP endpoint (default: http://localhost:16686). |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops sandbox logs`

**Stream stdout/stderr container logs with automated panic and crash detection.**

```bash
devops sandbox logs [OPTIONS] <identifier>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<identifier>` | `string` | No | Unique instance ID or name of the sandbox. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--follow`, `-f` | `boolean` | - | Follow log output continuously in live stream mode. |
| `--tail`, `-n` | `integer` | `100` | Number of lines to show from the end of the logs (default: 100). |
| `--timestamps`, `-t` | `boolean` | `True` | Show timestamps in log output. |
| `--detect-panics` / `--no-detect-panics` | `boolean` | `True` | Automatically detect panics, stacktraces, and segfaults. |
| `--archive-incidents` / `--no-archive-incidents` | `boolean` | `True` | Archive incident records to JSON files |
| `--incident-dir` | `path` | - | Directory path to persist structured panic incident records. |
| `--json` | `boolean` | - | Output findings or metrics as JSON. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops sandbox network-policy`

**Generate declarative Kubernetes NetworkPolicy YAML for workload sandbox isolation.**

```bash
devops sandbox network-policy [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--network-mode`, `-m` | `string` | `isolated` | Network mode: isolated | sandbox_namespace | public_whitelist | local_whitelist | bridge |
| `--name`, `-n` | `string` | `app-sandbox` | Name prefix for the NetworkPolicy resource |
| `--namespace` | `string` | `sandbox` | Target Kubernetes namespace |
| `--public-whitelist` | `string` | - | Comma-separated public destinations allowed for egress, each opening one TCP port: scheme://host:port, host:port or [v6]:port. A bare host, IP or CIDR, or https, gets 443 and http 80; any other scheme needs a port. Names are resolved when the policy is generated, so regenerate it when a name's addresses change. |
| `--local-whitelist` | `string` | - | Comma-separated local or private destinations allowed for egress, with the same forms and ports as --public-whitelist: scheme://host:port, host:port or [v6]:port; a bare host, IP or CIDR, or https, gets 443 and http 80; any other scheme needs a port. Names are resolved when the policy is generated, so regenerate it when a name's addresses change. |
| `--allow-collector` | `boolean` | - | Add one egress rule to the OTel collector's pods in the otel namespace on TCP 4317 and 4318 (sandbox_namespace, public_whitelist and local_whitelist modes) |

---

## devops dashboard

Interactive terminal UI dashboard for workstation situational awareness.

### `devops dashboard`

**Interactive terminal UI dashboard for workstation situational awareness.**

```bash
devops dashboard [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--summary`, `-s` | `boolean` | - | Print static summary panels and exit instead of starting full-screen TUI. |
| `--refresh-interval`, `-r` | `integer` | `5` | Auto-refresh interval in seconds for live dashboard updates. |
| `--tab`, `-t` | `string` | `k8s` | Initial tab to activate (1=k8s, 2=docker, 3=telemetry, 4=ai, 5=valkey). |
| `--dry-run` | `boolean` | - | Simulate dashboard launch and print static summary. |

---

## devops tui

Interactive terminal UI dashboard (alias)

Interactive terminal UI dashboard for workstation situational awareness.

### `devops tui`

**Interactive terminal UI dashboard for workstation situational awareness.**

```bash
devops tui [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--summary`, `-s` | `boolean` | - | Print static summary panels and exit instead of starting full-screen TUI. |
| `--refresh-interval`, `-r` | `integer` | `5` | Auto-refresh interval in seconds for live dashboard updates. |
| `--tab`, `-t` | `string` | `k8s` | Initial tab to activate (1=k8s, 2=docker, 3=telemetry, 4=ai, 5=valkey). |
| `--dry-run` | `boolean` | - | Simulate dashboard launch and print static summary. |

---

## devops status

Inspect published operational status of upstream platforms (GitHub, Cloudflare)

Inspect published operational status of upstream cloud platforms (GitHub, Cloudflare)

### `devops status`

**Inspect published operational status of upstream cloud platforms (GitHub, Cloudflare)**

```bash
devops status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--service`, `-s` | `string` | `all` | Target service to inspect (all, github, cloudflare) |
| `--json`, `-j` | `boolean` | - | Output status details in JSON format |
| `--emit-telemetry` | `boolean` | - | Emit operational service status metrics over OpenTelemetry to Prometheus |

---

## devops format

Automatically apply code formatting in-place (ruff format).

Format codebase with ruff format (or verify in check-only mode with --check).

### `devops format`

**Format codebase with ruff format (or verify in check-only mode with --check).**

```bash
devops format [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--check` | `boolean` | - | Check formatting without writing changes to files. |
| `--fix` / `--no-fix` | `boolean` | `True` | Apply formatting changes in-place. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## devops lint

Run static analysis checks and automatically apply fixes (ruff check --fix).

Run ruff linter across the project, automatically applying fixes by default.

### `devops lint`

**Run ruff linter across the project, automatically applying fixes by default.**

```bash
devops lint [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--fix` / `--no-fix` | `boolean` | `True` | Auto-fix violations where possible. |
| `--check` | `boolean` | - | Check linting without applying automated fixes. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
