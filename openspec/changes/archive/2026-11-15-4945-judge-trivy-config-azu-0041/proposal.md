# Proposal

## Why

Issue #4945: Trivy config reports a CRITICAL misconfiguration AZU-0041 for `tf/azure/main.tf`. The rule requires API server authorized IP ranges for the AKS cluster. Alert 213 in GitHub Code Scanning remains open. Under SECURITY.md, an agent or owner must judge the finding. The owner decision of 2026-11-12 requires setting `api_server_access_profile.authorized_ip_ranges` from a new variable without a default value, keeping the endpoint public and keeping addresses out of git. Closes #4945.

## What Changes

- Add the `api_server_access_profile` block to `azurerm_kubernetes_cluster.aks` in `tf/azure/main.tf`, setting `authorized_ip_ranges = var.api_server_authorized_ip_ranges`.
- Declare `api_server_authorized_ip_ranges` in `tf/azure/variables.tf` with `type = list(string)` and a description, without a default value.
- Preserve the existing `network_profile` block in `tf/azure/main.tf` without modification.
- Add security verification tests in `tests/security/test_tf_azure_aks_security.py`.
- The change alters no devops CLI command, option, message, manifest or service behavior, so it has no spec delta and sets `skip_specs: true`.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `tf/azure/main.tf` and `tf/azure/variables.tf`: AKS cluster provisioning configuration.
- Consumers of the Azure Terraform module must supply the `api_server_authorized_ip_ranges` variable when deploying the cluster.
- `trivy config tf/azure` clears CRITICAL finding AZU-0041.

## Feasibility

Read on 2026-11-15 against `origin/main` at `a37a52479`:

- `trivy config tf/azure` on base: reports 7 failures, including AZU-0041 (CRITICAL) at `tf/azure/main.tf:44-79`.
- `trivy config tf/azure` with `api_server_access_profile` and the variable: reports 6 failures with 0 CRITICAL findings. AZU-0041 is absent.
- `tflint --chdir=tf/azure` passes with status 0 and 0 findings.
- `uv run pytest tests/security/test_tf_azure_aks_security.py` passes all 4 tests offline.

## Existing Tool Considered

The open, maintained AzureRM Terraform provider (`hashicorp/azurerm`) supplies `api_server_access_profile.authorized_ip_ranges`. Trivy and TFLint are the open scanners that analyze the configuration. The change builds no custom scanner code.
