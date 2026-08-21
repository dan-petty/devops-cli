# Security, Vulnerability Scanning & SSH Cheatsheet

Compare disparate security scanning tools (`trivy`, `bandit`, `kube-linter`, `pluto`, `popeye`, `ssh-keygen`, `ssh-audit`) with unified `devops-cli` security scanners, threat intelligence lookups, and ED25519 key management.

---

## 1. Static Security & Vulnerability Scanning

| Action / Goal | Original Command | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **All-in-One Security Scan** | Multiple distinct tools (`trivy`, `bandit`, `kube-linter`, `pluto`) | `devops scan all` | Executes multi-engine static scanning in parallel and unifies findings into a single severity table. |
| **Python Security Scan** | `bandit -r src/ -ll -ii` | `devops scan bandit` | Runs Bandit across Python source files, filtering out test suites and temporary files. |
| **Filesystem / Container Scan** | `trivy fs . --severity HIGH,CRITICAL` | `devops scan trivy` | Scans dependencies and container images with automatic caching and zero egress leaks. |
| **Kubernetes Linting** | `kube-linter lint k8s/` | `devops scan kube-linter` | Audits manifests against production security standards (read-only rootfs, non-root users, drop capabilities). |
| **Deprecated K8s API Scan** | `pluto detect-files -d k8s/` | `devops scan pluto` | Detects deprecated Kubernetes API versions before cluster upgrades. |

---

## 2. Threat Intelligence & Network Reputation Lookups

| Action / Goal | Original Command / Manual Workflow | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **OSV / NVD CVE Lookup** | Manual search on `osv.dev` and `nvd.nist.gov` | `devops ai review path <file>` | Automatically extracts Python, Node, Rust, and Go dependencies and audits against live OSV.dev and NVD APIs. |
| **Network Host Reputation** | Manual search on Shodan / Cloudflare Radar | `devops ai review path <file>` | Automatically extracts external public IPs/domains and queries Shodan InternetDB and Cloudflare Radar. |

---

## 3. SSH Key Generation & Security Auditing

| Action / Goal | Original Command (`ssh-keygen` / `ssh-audit`) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **Generate Secure ED25519 Key**| `ssh-keygen -t ed25519 -a 100 -C "user@host"` | `devops ssh keygen --name <name>` | Enforces ED25519 algorithm, custom comment formatting, and safe storage in user's managed `.ssh/` folder. |
| **Audit SSH Host Security** | `ssh-audit <host>` | `devops ssh audit <host>` | Audits cipher suites, key exchange algorithms, and protocol vulnerabilities on remote endpoints. |
| **List Managed SSH Keys** | `ls -la ~/.ssh/*.pub` | `devops ssh list` | Formats public keys, algorithms, bit strengths, and fingerprints in an easy-to-read table. |
