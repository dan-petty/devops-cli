---
applies_to:
  - "tool:tflint@0.65.*"
sources:
  - "https://github.com/terraform-linters/tflint"
reviewed: "2026-10-29"
tags:
  - "tflint"
  - "iac"
  - "terraform"
---

# TFLint Tool Reference Manual

## 1. Overview & Operational Mandate
TFLint is a framework-aware linter for Terraform and OpenTofu. Unlike basic syntax linters, TFLint inspects provider-specific attributes, validates VM instance types, flags deprecated syntax, and enforces naming conventions before deployment.

In `devops-cli`, TFLint is integrated via `devops tf lint` and `run_tflint_scan()` under `src/devops_cli/security/tflint.py`. `tools.lock` pins tflint 0.65.0 as a zip build for each platform, and `devops install-tools --tool tflint` installs it.

`tflint --format json` writes one JSON object, `{"issues": [...], "errors": [...]}`. Each issue has `rule` (`name`, `severity`, `link`), `message` and `range`. The severity of an issue is `error`, `warning` or `info`, and the adapter makes them HIGH, MEDIUM and LOW findings at `<file>:<line>`. tflint exits 0 with no issue, 2 with issues and 1 after an error, so exit 1 with no issue is a failed scan. tflint takes no path argument and lints the `.tf` files of its starting directory only unless `--recursive` is set. The adapter starts it in the directory of the target with `--recursive`, so it lints each directory below the target. When tflint is not on PATH, the scan is `unavailable` and `devops tf lint` exits 1: no hand-written check replaces the tool. The check for `0.0.0.0/0` in IaC files is the job of Trivy's misconfiguration scan, `devops scan trivy --type config`.

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
