# Knowledge Base: OpenTofu & Terraform (Infrastructure as Code Engine)

## 1. Overview & Purpose

OpenTofu is an open-source, community-driven Infrastructure as Code (IaC) tool forked from Terraform under the Linux Foundation. In the `devops-cli` ecosystem, OpenTofu and Terraform provide declarative cloud infrastructure provisioning across AWS, GCP, Azure, and Kubernetes. The CLI provides unified subcommands (`devops tofu` and `devops tf`) with automated binary resolution, plan inspection, drift detection, and state auditing.

---

## 2. Usage Information & Architecture

- **Dual-Binary Dispatch**: Automatically detects and uses `tofu` if installed, falling back to `terraform` seamlessly.
- **Directory Convention**:
  ```text
  tf/
  ├── aws/           # AWS infrastructure manifests
  ├── azure/         # Azure infrastructure manifests
  ├── gcp/           # GCP infrastructure manifests
  └── environments/  # Environment variable definitions (.tfvars)
  ```
- **State Safety**: Programmatic execution utilizes bounded timeouts, plan file locking, and zero-trust parameter passing.
- **CLI Commands**:
  - `devops tf init`: Initialize working directory and provider plugins.
  - `devops tf plan`: Generate and inspect execution plan.
  - `devops tf apply`: Apply infrastructure changes with auto-approve or plan files.
  - `devops tf output`: Read structured output variables as JSON.
  - `devops tf status`: Inspect state file freshness and initialized providers.

---

## 3. Common & Advanced Commands

### DevOps CLI OpenTofu Subcommands
```bash
# Initialize OpenTofu directory
devops tofu init --path tf/aws

# Generate execution plan with variable file
devops tofu plan --path tf/aws -v tf/environments/dev.tfvars -o dev.tfplan

# Apply generated plan
devops tofu apply --path tf/aws --plan dev.tfplan

# Show structured output values as JSON
devops tofu output --path tf/aws --json

# Inspect initialization and state status
devops tofu status --path tf/aws
```

### Standard OpenTofu / Terraform CLI Commands
```bash
# Initialize backend and download provider plugins
tofu init -upgrade

# Validate syntax and configuration consistency
tofu validate

# Format all HCL configuration files recursively
tofu fmt -recursive

# Refresh state and check for external configuration drift
tofu plan -refresh-only

# Show state resources list
tofu state list

# Show detailed attributes of a specific resource in state
tofu state show aws_s3_bucket.data_lake

# Import existing cloud resource into state
tofu import aws_s3_bucket.data_lake my-bucket-name
```

---

## 4. Best Practice Guidance

1. **Always Plan Before Apply**: Generate a plan file (`-o <name>.tfplan`) and review all additions, modifications, and destructions before applying.
2. **Lock Provider Versions**: Always declare required provider versions explicitly in `versions.tf` (`required_providers`).
3. **Use Remote State with Locking**: For team environments, configure remote state storage (S3 + DynamoDB, GCS, or Azure Blob) with state locking enabled.
4. **Environment Isolation**: Keep environment states separated by workspace or directory structures (`tf/environments/`) rather than sharing single state files.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Never Commit State Files**: Never commit `.tfstate` or `.tfstate.backup` files to Git. State files contain unencrypted resource attributes and secrets.
- **Secret Redaction**: Mark sensitive output variables with `sensitive = true` to prevent secrets from being printed in CI console logs.
- **Least Privilege Cloud IAM**: Run OpenTofu using scoped IAM roles with temporary STS tokens rather than root cloud account credentials.
- **Static Analysis**: Lint HCL configurations with security scanners (Trivy, tfsec, checkov) before executing apply pipelines.

---

## 6. General Standards & Reference Guidelines

- **HCL Formatting**: All files must be formatted with `tofu fmt` (checked during `devops ci`).
- **File Structure**:
  - `main.tf`: Primary resource declarations.
  - `variables.tf`: Input variable declarations with types and descriptions.
  - `outputs.tf`: Exported output attributes.
  - `versions.tf`: `required_version` and `required_providers` blocks.

---

## 7. Official References & Published Artifacts

- **Project Homepage**: [opentofu.org](https://opentofu.org/)
- **Public Git Repository**: [github.com/opentofu/opentofu](https://github.com/opentofu/opentofu)
- **OpenTofu Registry**: [search.opentofu.org](https://search.opentofu.org/)
- **Terraform Documentation**: [developer.hashicorp.com/terraform](https://developer.hashicorp.com/terraform)
- **DevOps CLI OpenTofu Engine**: [src/devops_cli/commands/tf.py](../../../src/devops_cli/commands/tf.py)
