# Knowledge Base: KubeLinter, Popeye & Pluto (Kubernetes Quality & Safety Suite)

## 1. Overview & Purpose

Kubernetes cluster safety and manifest quality require multi-layered static and runtime validation. The `devops-cli` ecosystem integrates three specialized tools:
1. **KubeLinter**: Static analysis tool for Kubernetes YAML files and Helm charts, checking for security best practices and misconfigurations.
2. **Popeye**: Real-time Kubernetes cluster sanitizer scanning live cluster resources for potential misconfigurations, port mismatches, dead resources, and resource limit oversights.
3. **Pluto**: Static utility that detects deprecated and removed Kubernetes API versions in manifests, Helm releases, and live clusters.

---

## 2. Usage Information & Architecture

- **Manifest Security Auditing (`KubeLinter`)**: Integrated in `src/devops_cli/security/kubelinter.py` to evaluate manifests against security rules (e.g. running as non-root, read-only root filesystems, resource limits).
- **Cluster Sanitation (`Popeye`)**: Integrated in `src/devops_cli/security/popeye.py` to inspect live namespaces and score cluster health from A to F.
- **API Deprecation Detection (`Pluto`)**: Integrated in `src/devops_cli/security/pluto.py` to identify deprecated `apiVersion` entries before cluster upgrades.

---

## 3. Common & Advanced Commands

### DevOps CLI Kubernetes Security Commands
```bash
# Lint Kubernetes manifests with KubeLinter
devops scan kubelinter k8s/

# Sanitize live Kubernetes cluster resources with Popeye
devops scan popeye --namespace monitoring

# Detect deprecated Kubernetes API versions with Pluto
devops scan pluto k8s/
```

### Standard Tool CLI Commands
```bash
# KubeLinter: Lint a directory of YAML manifests
kube-linter lint k8s/base/

# KubeLinter: Lint Helm chart templates
helm template my-chart | kube-linter lint -

# Popeye: Run cluster sanitation on specific namespace with spin report
popeye -n default -s ok,info,warn,error

# Popeye: Output structured JSON report
popeye -o json > popeye-report.json

# Pluto: Scan local directory for deprecated APIs against target Kubernetes version
pluto detect-files -d k8s/ --target-versions k8s=v1.31.0

# Pluto: Scan live Helm releases in the cluster
pluto detect-helm -A
```

---

## 4. Best Practice Guidance

1. **Enforce Resource Requests & Limits**: KubeLinter and Popeye flag pods without CPU/memory requests and limits; always specify `resources.requests` and `resources.limits`.
2. **Set Security Contexts**: Define `securityContext.runAsNonRoot: true` and `securityContext.readOnlyRootFilesystem: true` across all Deployment pod templates.
3. **Check Pluto Before Upgrades**: Run Pluto prior to upgrading Kubernetes cluster versions (e.g. v1.30 to v1.31) to catch removed API versions before they break deployments.
4. **Clean Dead Resources**: Regularly inspect Popeye output for unused ConfigMaps, orphaned Services, and unattached PersistentVolumeClaims.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Privilege Escalation**: Block `allowPrivilegeEscalation: true` and drop dangerous Linux capabilities (`capabilities.drop: ["ALL"]`).
- **Service Account Token Auto-Mounting**: Set `automountServiceAccountToken: false` on pods that do not interact with the Kubernetes API server directly.

---

## 6. General Standards & Reference Guidelines

- **Target Versions**: Keep Pluto target Kubernetes versions aligned with current production cluster runtimes.
- **Rule Configurations**: Customize KubeLinter rules in `.kube-linter.yaml` when specific architectural exceptions are required.
