# Checkov Tool Reference Manual

## 1. Overview & Operational Mandate
Checkov is a static code analysis tool for Infrastructure as Code (IaC). It audits Terraform, CloudFormation, Kubernetes manifests, Dockerfiles, Serverless framework files, and ARM templates for security compliance and CIS benchmarks.

In `devops-cli`, Checkov is integrated via `devops scan iac` and `run_checkov_scan()` under `src/devops_cli/security/checkov.py`.

## 2. Key Capabilities
- **Multi-Framework Policy Auditing**: Scans Terraform (`.tf`), Kubernetes (`.yaml`), Helm charts, and Dockerfiles.
- **CIS & Security Benchmarks**: Evaluates infrastructure definitions against CIS benchmarks, HIPAA, PCI-DSS, and SOC2 policies.
- **Structured JSON Output**: Produces normalized findings containing policy IDs (`CKV_AWS_*`, `CKV_K8S_*`), resource paths, evaluated keys, and remediation guidelines.

## 3. CLI Invocations
```bash
# Scan all IaC manifests in target workspace
devops scan iac .

# Scan specific directory for Terraform policies
devops scan iac terraform/ --framework terraform

# Output normalized JSON findings
devops scan iac . --json
```

## 4. Native Persona Tool Registration
- **Registered Tool**: `scan_iac`
- **Personas**: `devsecops`, `auditor`
