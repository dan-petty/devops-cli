# `devops kustomize`

Kustomize build and apply operations.

## Commands

## `devops kustomize build`

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

---

## `devops kustomize diff`

**Show a diff of pending changes (delegates to kubectl diff -k).**

```bash
devops kustomize diff <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Target kustomize directory path. |

---

## `devops kustomize apply`

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
