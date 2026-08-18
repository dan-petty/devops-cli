# FastMCP Tool Catalog

The `devops-cli` FastMCP server exposes DevOps automation and AI review capabilities to Model Context Protocol (MCP) clients and AI agents.

## Available Tools

| Tool Name | Description |
|---|---|
| [`argo_list`](#argo-list) | List ArgoCD applications. |
| [`argo_status`](#argo-status) | Check ArgoCD application health and sync status. |
| [`branches_create`](#branches-create) | Create a topic branch following repository branching hierarchy and release targeting. |
| [`branches_status`](#branches-status) | Show detailed branch status, tracking state, ahead/behind drift, and worktree status. |
| [`ci_remote_logs`](#ci-remote-logs) | Fetch failure logs or full step logs for a remote GitHub Actions workflow run. |
| [`ci_remote_status`](#ci-remote-status) | Check status of remote GitHub Actions CI workflow runs or PR checks. |
| [`ci_run`](#ci-run) | Run devops-cli complete quality gate (pytest, ruff check, ruff format, mypy). |
| [`config_output`](#config-output) | Output environment variables available for configuration (text or json). |
| [`config_show`](#config-show) | Display configuration settings with masked secret tokens. |
| [`docker_stats`](#docker-stats) | List local Docker images and display container information. |
| [`grafana_dashboards`](#grafana-dashboards) | List Grafana dashboards, optionally filtered by search query. |
| [`k8s_bootstrap`](#k8s-bootstrap) | Bootstrap minikube Kubernetes cluster and deploy infrastructure stack. |
| [`k8s_deploy_stack`](#k8s-deploy-stack) | Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to minikube. |
| [`k8s_pods`](#k8s-pods) | List Kubernetes pod status for the specified namespace. |
| [`k8s_status`](#k8s-status) | Display pod status across infrastructure namespaces. |
| [`k8s_teardown_stack`](#k8s-teardown-stack) | Uninstall minikube infrastructure or LLM stack and delete namespaces. |
| [`pr_checks`](#pr-checks) | Check CI quality gate checks and status on a pull request. |
| [`pr_list`](#pr-list) | List GitHub pull requests with base targeting and review status. |
| [`pr_view`](#pr-view) | View metadata and conversation details for a GitHub pull request. |
| [`prometheus_query`](#prometheus-query) | Execute PromQL instant query against Prometheus endpoint. |
| [`release_notes`](#release-notes) | Extract release notes from CHANGELOG.md for a specified release version. |
| [`release_prepare`](#release-prepare) | Bump version across pyproject.toml and source, update changelog, and sync docs. |
| [`release_status`](#release-status) | Check devops-cli release status, version consistency, tags, and docs state. |
| [`repos_exec`](#repos-exec) | Execute a shell command across all discovered git repositories in repos/. |
| [`repos_list`](#repos-list) | List local workspace repositories and active git branches. |
| [`repos_status`](#repos-status) | Display uncommitted changes and branch drift across workspace repositories. |
| [`repos_sync`](#repos-sync) | Fetch and pull tracking branches across workspace repositories. |
| [`review_branch`](#review-branch) | Run an AI code review on git branch diff against base branch. |
| [`review_findings`](#review-findings) | Inspect structured review findings for a session by verification status. |
| [`review_path`](#review-path) | Run an AI code review on local files matching pattern using specified persona. |
| [`review_pr`](#review-pr) | Fetch GitHub PR diff and review using specified persona; optionally post comment. |
| [`review_stats`](#review-stats) | View accuracy metrics and false-positive rates per reviewer persona. |
| [`ssh_audit`](#ssh-audit) | Audit SSH key expiration dates and key file permissions. |
| [`ssh_status`](#ssh-status) | Inspect age and rotation status of managed SSH keys in ~/.ssh. |
| [`tf_apply`](#tf-apply) | Apply OpenTofu / Terraform Infrastructure-as-Code changes. |
| [`tf_output`](#tf-output) | Retrieve OpenTofu / Terraform outputs from state. |
| [`tf_plan`](#tf-plan) | Generate and inspect an OpenTofu / Terraform execution plan. |
| [`tofu_apply`](#tofu-apply) | Apply OpenTofu Infrastructure-as-Code changes (alias for tf_apply). |
| [`tofu_output`](#tofu-output) | Retrieve OpenTofu outputs from state (alias for tf_output). |
| [`tofu_plan`](#tofu-plan) | Generate and inspect an OpenTofu execution plan (alias for tf_plan). |
| [`verify_finding`](#verify-finding) | Validate or invalidate a finding and record human feedback. |
| [`workspace_list`](#workspace-list) | Show the active VS Code workspace file and configured repository directories. |

---

### `argo_list`

List ArgoCD applications.

*No parameters required.*

### `argo_status`

Check ArgoCD application health and sync status.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `app` | `string` | No | `argocd` | - |

### `branches_create`

Create a topic branch following repository branching hierarchy and release targeting.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | `string` | Yes | - | - |
| `base` | `string` | No | `` | - |
| `branch_type` | `string` | No | `feat` | - |

### `branches_status`

Show detailed branch status, tracking state, ahead/behind drift, and worktree status.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |

### `ci_remote_logs`

Fetch failure logs or full step logs for a remote GitHub Actions workflow run.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `run_id` | `string` | No | `` | - |
| `failed_only` | `boolean` | No | `True` | - |

### `ci_remote_status`

Check status of remote GitHub Actions CI workflow runs or PR checks.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `branch` | `string` | No | `` | - |
| `pr_number` | `integer` | No | `0` | - |

### `ci_run`

Run devops-cli complete quality gate (pytest, ruff check, ruff format, mypy).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `check` | `string` | No | `all` | - |

### `config_output`

Output environment variables available for configuration (text or json).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `output_format` | `string` | No | `json` | - |

### `config_show`

Display configuration settings with masked secret tokens.

*No parameters required.*

### `docker_stats`

List local Docker images and display container information.

*No parameters required.*

### `grafana_dashboards`

List Grafana dashboards, optionally filtered by search query.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | `string` | No | `` | - |

### `k8s_bootstrap`

Bootstrap minikube Kubernetes cluster and deploy infrastructure stack.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `auto_start` | `boolean` | No | `True` | - |

### `k8s_deploy_stack`

Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to minikube.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `stack` | `string` | No | `infra` | - |

### `k8s_pods`

List Kubernetes pod status for the specified namespace.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `namespace` | `string` | No | `default` | - |

### `k8s_status`

Display pod status across infrastructure namespaces.

*No parameters required.*

### `k8s_teardown_stack`

Uninstall minikube infrastructure or LLM stack and delete namespaces.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `stack` | `string` | No | `infra` | - |

### `pr_checks`

Check CI quality gate checks and status on a pull request.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | - |
| `repo` | `string` | No | `` | - |

### `pr_list`

List GitHub pull requests with base targeting and review status.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `repo` | `string` | No | `` | - |
| `state` | `string` | No | `open` | - |

### `pr_view`

View metadata and conversation details for a GitHub pull request.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | - |
| `repo` | `string` | No | `` | - |

### `prometheus_query`

Execute PromQL instant query against Prometheus endpoint.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `promql` | `string` | No | `up` | - |

### `release_notes`

Extract release notes from CHANGELOG.md for a specified release version.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `version` | `string` | No | `` | - |
| `raw` | `boolean` | No | `True` | - |

### `release_prepare`

Bump version across pyproject.toml and source, update changelog, and sync docs.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `version` | `string` | Yes | - | - |
| `create_pr` | `boolean` | No | `False` | - |

### `release_status`

Check devops-cli release status, version consistency, tags, and docs state.

*No parameters required.*

### `repos_exec`

Execute a shell command across all discovered git repositories in repos/.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `command` | `string` | Yes | - | - |
| `base_dir` | `string` | No | `` | - |

### `repos_list`

List local workspace repositories and active git branches.

*No parameters required.*

### `repos_status`

Display uncommitted changes and branch drift across workspace repositories.

*No parameters required.*

### `repos_sync`

Fetch and pull tracking branches across workspace repositories.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `all_repos` | `boolean` | No | `False` | - |

### `review_branch`

Run an AI code review on git branch diff against base branch.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `branch` | `string` | No | `` | - |
| `base` | `string` | No | `main` | - |
| `persona` | `string` | No | `devsecops` | - |

### `review_findings`

Inspect structured review findings for a session by verification status.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `session_id` | `string` | No | `` | - |
| `status` | `string` | No | `` | - |

### `review_path`

Run an AI code review on local files matching pattern using specified persona.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `target` | `string` | No | `.` | - |
| `pattern` | `string` | No | `*` | - |
| `persona` | `string` | No | `devsecops` | - |

### `review_pr`

Fetch GitHub PR diff and review using specified persona; optionally post comment.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `number` | `integer` | Yes | - | - |
| `post` | `boolean` | No | `False` | - |
| `persona` | `string` | No | `devsecops` | - |

### `review_stats`

View accuracy metrics and false-positive rates per reviewer persona.

*No parameters required.*

### `ssh_audit`

Audit SSH key expiration dates and key file permissions.

*No parameters required.*

### `ssh_status`

Inspect age and rotation status of managed SSH keys in ~/.ssh.

*No parameters required.*

### `tf_apply`

Apply OpenTofu / Terraform Infrastructure-as-Code changes.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `var_file` | `string` | No | `` | - |
| `auto_approve` | `boolean` | No | `True` | - |

### `tf_output`

Retrieve OpenTofu / Terraform outputs from state.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `json_format` | `boolean` | No | `True` | - |

### `tf_plan`

Generate and inspect an OpenTofu / Terraform execution plan.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `var_file` | `string` | No | `` | - |

### `tofu_apply`

Apply OpenTofu Infrastructure-as-Code changes (alias for tf_apply).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `var_file` | `string` | No | `` | - |
| `auto_approve` | `boolean` | No | `True` | - |

### `tofu_output`

Retrieve OpenTofu outputs from state (alias for tf_output).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `json_format` | `boolean` | No | `True` | - |

### `tofu_plan`

Generate and inspect an OpenTofu execution plan (alias for tf_plan).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `directory` | `string` | No | `.` | - |
| `var_file` | `string` | No | `` | - |

### `verify_finding`

Validate or invalidate a finding and record human feedback.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `session_id` | `string` | Yes | - | - |
| `index` | `integer` | Yes | - | - |
| `status` | `string` | Yes | - | - |
| `reason` | `string` | No | `` | - |

### `workspace_list`

Show the active VS Code workspace file and configured repository directories.

*No parameters required.*
