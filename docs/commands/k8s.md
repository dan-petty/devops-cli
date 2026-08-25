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
| `--dir`, `-d` | `path` | `k8s` | Directory containing Kubernetes manifests |
| `--auto-start`, `--no-auto-start` | `boolean` | `True` | Auto-start minikube if stopped |
| `--stack`, `-s` | `string` | `all` | Stack to deploy after bootstrap: infra | llm | all |

---

## `devops k8s deploy-stack`

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

---

## `devops k8s configure-urls`

**Auto-detect Kubernetes stack URLs and update CLI config.**

```bash
devops k8s configure-urls [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--stack`, `-s` | `string` | `infra` | Stack to configure URLs for (infra, llm, all) |
| `--context`, `-c` | `string` | - | Kubernetes cluster context |

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
| `--context`, `-c` | `string` | - | Kubernetes cluster context |

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

## `devops k8s create-tls-secret`

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

---

## `devops k8s enable-tls`

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

## `devops k8s validate`

**Validate Kubernetes YAML manifests against OpenAPI schemas using Kubeconform.**

```bash
devops k8s validate [OPTIONS] <manifest_path>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<manifest_path>` | `path` | No | Path to Kubernetes YAML manifest file or directory |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--kubernetes-version`, `-v` | `string` | `master` | Target Kubernetes OpenAPI version |
| `--strict`, `--no-strict` | `boolean` | `True` | Disallow additional undeclared properties |
| `--dry-run` | `boolean` | - | Simulate schema validation |
| `--json` | `boolean` | - | Output findings as JSON |

---
