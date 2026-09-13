# `devops argo`

Argo CD, Workflows, and Rollouts management.

## Commands

## `devops argo sync`

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

---

## `devops argo cd`

```bash
devops argo cd COMMAND [ARGS]...
```

### `devops argo cd fleet`

```bash
devops argo cd fleet COMMAND [ARGS]...
```

#### `devops argo cd fleet sync`

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

### `devops argo cd gitops`

```bash
devops argo cd gitops COMMAND [ARGS]...
```

#### `devops argo cd gitops watch`

**Monitor Kubernetes and Helm manifests for drift and trigger instant ArgoCD sync.**

```bash
devops argo cd gitops watch [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--path`, `-p` | `string` | `k8s` | Comma-separated paths or directories of manifests to monitor |
| `--app-name`, `-a` | `string` | `root-app` | Application name. |
| `--debounce-ms` | `integer` | `500` | Debounce delay in milliseconds to aggregate rapid modifications |
| `--interval`, `-i` | `float` | `1.0` | Watch polling interval in seconds |
| `--max-events` | `integer` | - | Maximum change events to process before exiting |
| `--once` | `boolean` | - | Check manifest drift once, trigger sync if drifted, and exit immediately |
| `--mode`, `-m` | `string` | `api` | Synchronization trigger mode ('api' or 'webhook') |
| `--prune` | `boolean` | - | Allow deletion of resources omitted from the source repository. |
| `--force` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

#### `devops argo cd gitops drift`

**Inspect and report local manifest state and detect any unstaged or modified files.**

```bash
devops argo cd gitops drift [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--path`, `-p` | `string` | `k8s` | Comma-separated paths or directories of manifests to inspect |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

#### `devops argo cd gitops sync`

**Trigger an immediate GitOps synchronization for an ArgoCD application.**

```bash
devops argo cd gitops sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--app-name`, `-a` | `string` | `root-app` | Application name. |
| `--mode`, `-m` | `string` | `api` | Synchronization trigger mode ('api' or 'webhook') |
| `--prune` | `boolean` | - | Allow deletion of resources omitted from the source repository. |
| `--force` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

### `devops argo cd apps`

```bash
devops argo cd apps COMMAND [ARGS]...
```

#### `devops argo cd apps list`

**List all ArgoCD applications.**

```bash
devops argo cd apps list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--watch`, `-w` | `boolean` | - | Watch application status changes live. |
| `--interval`, `-i` | `float` | `3.0` | Auto-refresh polling interval in seconds. |

#### `devops argo cd apps sync`

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

#### `devops argo cd apps status`

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

#### `devops argo cd apps bootstrap-gitops`

**Bootstrap local GitOps project orchestration via ArgoCD and the Git daemon.**

```bash
devops argo cd apps bootstrap-gitops [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--root-app`, `-f` | `path` | `k8s/argocd/apps/root-app.yaml` | Path to root ArgoCD App-of-Apps manifest. |
| `--context`, `-c` | `string` | - | Kubernetes cluster context name. |

---

## `devops argo workflows`

```bash
devops argo workflows COMMAND [ARGS]...
```

### `devops argo workflows list`

**List Argo Workflows.**

```bash
devops argo workflows list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |

### `devops argo workflows submit`

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

### `devops argo workflows logs`

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

---

## `devops argo rollouts`

```bash
devops argo rollouts COMMAND [ARGS]...
```

### `devops argo rollouts list`

**List Argo Rollouts.**

```bash
devops argo rollouts list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--namespace`, `-n` | `string` | - | Kubernetes namespace. |

### `devops argo rollouts status`

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

### `devops argo rollouts promote`

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

### `devops argo rollouts abort`

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

### `devops argo rollouts restart`

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

### `devops argo rollouts analyze`

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
| `--auto-abort`, `--no-auto-abort` | `boolean` | `True` | Automatically trigger rollout abort when metric analysis violates threshold |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

---

## `devops argo fleet`

```bash
devops argo fleet COMMAND [ARGS]...
```

### `devops argo fleet sync`

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

---

## `devops argo gitops`

```bash
devops argo gitops COMMAND [ARGS]...
```

### `devops argo gitops watch`

**Monitor Kubernetes and Helm manifests for drift and trigger instant ArgoCD sync.**

```bash
devops argo gitops watch [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--path`, `-p` | `string` | `k8s` | Comma-separated paths or directories of manifests to monitor |
| `--app-name`, `-a` | `string` | `root-app` | Application name. |
| `--debounce-ms` | `integer` | `500` | Debounce delay in milliseconds to aggregate rapid modifications |
| `--interval`, `-i` | `float` | `1.0` | Watch polling interval in seconds |
| `--max-events` | `integer` | - | Maximum change events to process before exiting |
| `--once` | `boolean` | - | Check manifest drift once, trigger sync if drifted, and exit immediately |
| `--mode`, `-m` | `string` | `api` | Synchronization trigger mode ('api' or 'webhook') |
| `--prune` | `boolean` | - | Allow deletion of resources omitted from the source repository. |
| `--force` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

### `devops argo gitops drift`

**Inspect and report local manifest state and detect any unstaged or modified files.**

```bash
devops argo gitops drift [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--path`, `-p` | `string` | `k8s` | Comma-separated paths or directories of manifests to inspect |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

### `devops argo gitops sync`

**Trigger an immediate GitOps synchronization for an ArgoCD application.**

```bash
devops argo gitops sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--app-name`, `-a` | `string` | `root-app` | Application name. |
| `--mode`, `-m` | `string` | `api` | Synchronization trigger mode ('api' or 'webhook') |
| `--prune` | `boolean` | - | Allow deletion of resources omitted from the source repository. |
| `--force` | `boolean` | - | Force execution ignoring non-blocking warnings. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |
| `--json`, `-j` | `boolean` | - | Output findings or metrics as JSON. |

---
