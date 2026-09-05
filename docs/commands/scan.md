# `devops scan`

Security scanner suite: Trivy, Gitleaks, Semgrep, Checkov, Kubeconform.

## Commands

## `devops scan trivy`

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

---

## `devops scan secrets`

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

---

## `devops scan sast`

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

---

## `devops scan iac`

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

---

## `devops scan complexity`

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

---

## `devops scan sbom`

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

---

## `devops scan aibom`

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

---

## `devops scan fix`

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

---
