# `devops argo`

Argo CD, Workflows, and Rollouts management.

## Commands

## `devops argo cd`

```bash
devops argo cd COMMAND [ARGS]...
```

### `devops argo cd apps`

```bash
devops argo cd apps COMMAND [ARGS]...
```

#### `devops argo cd apps list`

**List all ArgoCD applications.**

```bash
devops argo cd apps list
```

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
devops argo cd apps status <name>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<name>` | `string` | Yes | Application name. |

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

---
