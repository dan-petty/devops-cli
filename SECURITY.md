# Security Policy & Enterprise Threat Model — devops-cli

`devops-cli` is designed with a defense-in-depth security architecture suitable for enterprise DevOps and SRE workstations. This document details our security model, threat mitigations, and responsible vulnerability disclosure process.

---

## 1. Core Security Guarantees & Defenses

### Zero-Plaintext Secret Policy (OS Keyring)
- Sensitive credentials (GitHub Personal Access Tokens, LLM API Keys, Grafana Service Account Tokens, ArgoCD JWTs) are **never stored as plaintext** in configuration files (`config.yaml` or environment variables).
- All sensitive tokens are securely isolated in the OS Keyring via Python `keyring` (using SecretService on Linux, Keychain on macOS, or Credential Vault on Windows).
- Secrets are masked during CLI logging and persona reasoning runs (`<masked-token>`).

### Server-Side Request Forgery (SSRF) Mitigations
- Outbound network requests to external APIs (LLM endpoints, GitHub, Grafana, ArgoCD) pass through strict IP and hostname validation (`validate_service_url`).
- Connections to RFC 1918 private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback (`127.0.0.0/8`), and link-local (`169.254.0.0/16`) addresses are blocked by default.
- Private network egress can only be enabled via explicit runtime authorization (`DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK=true`).

### Subprocess Safety & Command Injection Prevention
- All OS commands are executed via parameterized arguments (`run_subprocess`) without shell interpolation (`shell=False`).
- Execution timeouts are strictly enforced across all subprocess calls (defaulting to 30s) to prevent resource starvation or hanging processes.

### Static Vulnerability Scanning & SecOps Gate
- Built-in static security scanners (`devops scan`, `devops k8s lint`, `devops k8s audit`, `devops k8s check-deprecated`) provide automated vulnerability discovery across files, Kubernetes manifests, and clusters before applying changes.

---

## 2. Reporting a Vulnerability

We welcome responsible security disclosures. If you discover a security vulnerability in `devops-cli`:

1. **Do NOT open a public GitHub issue.**
2. Send a detailed report via encrypted email or GitHub Private Vulnerability Reporting to the maintainers:
   - **Email**: `security@example.com` (or maintainer contact)
   - **Subject**: `[SECURITY VULNERABILITY] devops-cli — <Brief Description>`
3. Include:
   - Reproduction steps or proof-of-concept script.
   - Affected CLI versions and commands.
   - Potential impact analysis and recommended remediations.

### Response Timelines
- **Initial Acknowledgment**: Within 48 hours.
- **Triage & Impact Assessment**: Within 5 business days.
- **Patch Release & Security Advisory**: Coordinated within 14 business days.
