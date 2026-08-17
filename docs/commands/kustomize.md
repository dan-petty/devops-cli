# `devops kustomize`

Kustomize operations.

## Commands

## `devops kustomize build`

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

---

## `devops kustomize diff`

**Show a diff of pending changes (delegates to kubectl diff -k).**

```bash
devops kustomize diff <path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<path>` | `path` | No | Path to kustomization directory |

---

## `devops kustomize apply`

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
