# `devops scan`

Security, vulnerability, secret, and IaC scanner.

## Commands

## `devops scan trivy`

**Run Aqua Trivy vulnerability, secret, and misconfiguration scan.**

```bash
devops scan trivy [OPTIONS] <target>
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

## `devops scan secrets`

**Run Gitleaks secret pre-filter scan across workspace or targets.**

```bash
devops scan secrets [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or file to scan for secrets |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Simulate secret scan execution. |
| `--json` | `boolean` | - | Output raw findings as JSON |

---

## `devops scan gitleaks`

**Alias for devops scan secrets.**

```bash
devops scan gitleaks [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or file to scan for secrets |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | `boolean` | - | Simulate secret scan execution. |
| `--json` | `boolean` | - | Output raw findings as JSON |

---

## `devops scan semgrep`

**Run Semgrep multilingual static AST pattern matching scan.**

```bash
devops scan semgrep [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or file to scan with Semgrep AST rules |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--config`, `-c` | `string` | `p/default` | Semgrep ruleset config (e.g. p/default, p/security-audit) |
| `--dry-run` | `boolean` | - | Simulate Semgrep scan execution. |
| `--json` | `boolean` | - | Output raw findings as JSON |

---

## `devops scan sast`

**Run static application security testing (SAST) via Semgrep.**

```bash
devops scan sast [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or file to scan with Semgrep AST rules |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--config`, `-c` | `string` | `p/default` | Semgrep ruleset config (e.g. p/default, p/security-audit) |
| `--dry-run` | `boolean` | - | Simulate Semgrep scan execution. |
| `--json` | `boolean` | - | Output raw findings as JSON |

---

## `devops scan checkov`

**Run Checkov Infrastructure-as-Code (IaC) compliance scanner.**

```bash
devops scan checkov [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or file to scan with Checkov IaC rules |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--framework`, `-f` | `string` | - | Specific IaC framework (e.g. terraform) |
| `--dry-run` | `boolean` | - | Simulate Checkov IaC scan execution. |
| `--json` | `boolean` | - | Output raw findings as JSON |

---

## `devops scan iac`

**Run Checkov IaC static policy and security compliance scan.**

```bash
devops scan iac [OPTIONS] <target>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<target>` | `path` | No | Target directory or file to scan with Checkov IaC rules |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--framework`, `-f` | `string` | - | Specific IaC framework (e.g. terraform) |
| `--dry-run` | `boolean` | - | Simulate Checkov IaC scan execution. |
| `--json` | `boolean` | - | Output raw findings as JSON |

---
