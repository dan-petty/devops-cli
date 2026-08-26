# TFLint Tool Reference Manual

## 1. Overview & Operational Mandate
TFLint is a framework-aware linter for Terraform and OpenTofu. Unlike basic syntax linters, TFLint inspects provider-specific attributes, validates VM instance types, flags deprecated syntax, and enforces naming conventions before deployment.

In `devops-cli`, TFLint is integrated via `devops tf lint` and `run_tflint_scan()` under `src/devops_cli/security/tflint.py`.

## 2. Key Capabilities
- **Provider Rule Validation**: Verifies AWS, GCP, and Azure resource attributes against cloud provider schemas.
- **Deprecated Syntax Detection**: Warns against outdated interpolations or deprecated resource declarations.
- **Module Rule Enforcement**: Audits input variable declarations and module version constraints.

## 3. CLI Invocations
```bash
# Lint Terraform configurations in current directory
devops tf lint .

# Lint with custom .tflint.hcl config file
devops tf lint environments/prod/ --config .tflint.hcl

# Export findings as JSON
devops tf lint . --json
```

## 4. Native Persona Tool Registration
- **Registered Tool**: `tf_lint`
- **Personas**: `architect`, `devsecops`, `auditor`
