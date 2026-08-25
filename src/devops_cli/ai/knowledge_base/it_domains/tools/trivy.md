# Knowledge Base: Trivy (Vulnerability & Security Scanner)

## 1. Overview & Purpose

Trivy (by Aqua Security) is a comprehensive, open-source security scanner. It detects known Common Vulnerabilities and Exposures (CVEs), Infrastructure as Code (IaC) misconfigurations, sensitive hardcoded secrets, and license compliance risks across container images, filesystems, and Git repositories. In the `devops-cli` ecosystem, Trivy powers container security audits, dependency vulnerability lookups, and workstation pre-release scans.

---

## 2. Usage Information & Architecture

- **Multi-Target Scanning**: Scans container images (`trivy image`), local directory filesystems (`trivy fs`), Git repositories (`trivy repo`), and Kubernetes manifests (`trivy k8s`).
- **Offline Vulnerability DB**: Downloads and updates local vulnerability database caches under `~/.cache/trivy/db`.
- **Integration Layer**: Programmatically wrapped in `src/devops_cli/security/trivy.py` and exposed via `devops scan` subcommands.

---

## 3. Common & Advanced Commands

### DevOps CLI Scan Commands
```bash
# Scan a container image for vulnerabilities
devops scan image ghcr.io/dan-petty/devops-cli/devcontainer:latest

# Scan a local repository filesystem for CVEs and misconfigurations
devops scan fs .

# Scan Kubernetes manifests for security misconfigurations
devops scan k8s k8s/
```

### Standard & Advanced `trivy` Commands
```bash
# Scan container image with table output filtered by severity
trivy image --severity HIGH,CRITICAL ghcr.io/dan-petty/devops-cli/devcontainer:latest

# Scan filesystem and output structured JSON report
trivy fs --format json --output trivy-report.json .

# Scan for hardcoded plaintext secrets
trivy fs --scanners secret .

# Scan Infrastructure as Code (Terraform / Kubernetes) for misconfigurations
trivy config tf/

# Ignore unfixed vulnerabilities
trivy image --ignore-unfixed ghcr.io/dan-petty/devops-cli/devcontainer:latest
```

---

## 4. Best Practice Guidance

1. **Gate on Severity Thresholds**: In automated CI pipelines, configure exit codes on `CRITICAL` or `HIGH` vulnerabilities (`--exit-code 1 --severity CRITICAL`).
2. **Scan Base Images Frequently**: Daily scheduled scans ensure newly disclosed CVEs in upstream base OS packages (e.g. Debian, Alpine) are caught promptly.
3. **Use `.trivyignore`**: Document justified false positives or accepted risks in `.trivyignore` with expiration dates and CVE identifiers.
4. **Cache Vulnerability Database**: Cache `~/.cache/trivy` in CI workflows to avoid rate limits from vulnerability database mirrors.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Zero Tolerance for Critical CVEs**: Base container images must not be pushed to production registries with unmitigated `CRITICAL` vulnerabilities.
- **Air-Gapped Scans**: In restricted networks, download the Trivy DB archive (`trivy-db.tar.gz`) in advance and scan using `--skip-db-update`.

---

## 6. General Standards & Reference Guidelines

- **CVE Schema**: Follow standard NVD and GitHub Advisory Database identifiers (`CVE-YYYY-NNNN`, `GHSA-xxxx-xxxx-xxxx`).
- **Exit Code Conventions**: Exit code `0` on clean scans; exit code `1` when policy-violating vulnerabilities are detected.

---

## 7. Official References & Published Artifacts

- **Project Homepage**: [trivy.dev](https://trivy.dev/)
- **Public Git Repository**: [github.com/aquasecurity/trivy](https://github.com/aquasecurity/trivy)
- **Published Container Image**: [hub.docker.com/r/aquasec/trivy](https://hub.docker.com/r/aquasec/trivy)
- **DevOps CLI Scanner Engine**: [src/devops_cli/security/trivy.py](../../../../security/trivy.py)
