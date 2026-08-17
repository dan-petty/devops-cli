# `devops k8s`

Kubernetes resource management.

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
| `<name>` | `string` | Yes | Target context name to switch to |

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
| `<path>` | `string` | Yes | Manifest file or directory path |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | - |
| `--namespace`, `-n` | `string` | - | - |

---

## `devops k8s logs`

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

---

## `devops k8s bootstrap`

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

---

## `devops k8s deploy-stack`

**Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to minikube.**

```bash
devops k8s deploy-stack [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--k8s-dir` | `path` | `k8s` | Path to k8s/ config directory |
| `--stack`, `-s` | `string` | `infra` | Stack to deploy (infra, llm, all) |

---

## `devops k8s configure-urls`

**Auto-detect Minikube stack URLs and update CLI config.**

```bash
devops k8s configure-urls [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `infra` | Stack to configure URLs for (infra, llm, all) |

---

## `devops k8s port-forward`

**Port-forward k8s monitoring / LLM stack services to localhost ports and update CLI config.**

```bash
devops k8s port-forward [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `infra` | Stack services to port-forward (infra, llm, all) |
| `--argocd-port` | `integer` | `8080` | Local port for ArgoCD |
| `--grafana-port` | `integer` | `8030` | Local port for Grafana |
| `--prometheus-port` | `integer` | `8090` | Local port for Prometheus |
| `--ollama-port` | `integer` | `11434` | Local port for Ollama |
| `--open-webui-port` | `integer` | `3000` | Local port for Open-WebUI |
| `--qdrant-port` | `integer` | `6333` | Local port for Qdrant HTTP |
| `--valkey-port` | `integer` | `6379` | Local port for Valkey |

---

## `devops k8s teardown-stack`

**Uninstall the k8s infrastructure / LLM stack and delete namespaces.**

```bash
devops k8s teardown-stack [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--k8s-dir` | `path` | `k8s` | Path to k8s/ config directory |
| `--stack`, `-s` | `string` | `infra` | Stack to teardown (infra, llm, all) |

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
| `<target>` | `path` | No | Target K8s manifest file or directory to lint |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Simulate manifest linting. |

---

## `devops k8s audit`

**Sanitize active K8s/Minikube cluster resource health using Derailed Popeye.**

```bash
devops k8s audit [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Simulate cluster health audit. |

---

## `devops k8s check-deprecated`

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

---
