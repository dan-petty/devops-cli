# Infrastructure as Code (Terraform & OpenTofu) Cheatsheet

Compare native `terraform` and `tofu` (OpenTofu) commands with `devops-cli` plan/apply orchestration, output formatting, and secret masking.

---

## 1. Plan & Apply Execution

| Action / Goal | Original Command (`terraform` / `tofu`) | `devops-cli` Command | Key Enhancements in `devops-cli` |
| :--- | :--- | :--- | :--- |
| **Run Infrastructure Plan** | `terraform plan` / `tofu plan` | `devops tf plan` / `devops tofu plan` | Colorizes added/modified/destroyed resource counts and strips noisy metadata churn. |
| **Apply Infrastructure Changes** | `terraform apply -auto-approve` / `tofu apply` | `devops tf apply` / `devops tofu apply` | Enforces explicit dry-run safety gates before committing changes to cloud providers. |
| **Inspect State Outputs** | `terraform output -json` / `tofu output` | `devops tf output` / `devops tofu output` | Formats output variables as structured Rich tables and masks sensitive fields. |
| **Initialize Working Directory** | `terraform init -upgrade` / `tofu init` | `devops tf init` / `devops tofu init` | Auto-detects local backend providers and checks lockfile synchronization. |

---

## 2. Best Practices & Safety Gates

1. **Deterministic Binary Resolution**: `devops tf` and `devops tofu` ensure correct engine selection without alias conflicts.
2. **Subprocess Timeout Guardrails**: All provider downloads and plan computations execute with strict timeouts to prevent hanging shell pipelines.
3. **Secret Redaction**: Sensitive output variables and remote state credentials are automatically masked from CLI logs.
