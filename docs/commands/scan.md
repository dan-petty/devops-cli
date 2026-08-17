# `devops scan`

Security, vulnerability, secret, and IaC scanner.

## Commands

## `devops scan`

**Security, vulnerability, secret, and IaC scanner via Aqua Trivy.**

```bash
devops scan [OPTIONS] <target>
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
