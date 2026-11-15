# Tasks

## 1. Security configuration

- [x] 1.1 Add test verifying AKS authorized IP ranges and variable declaration
  - Verification: `$ uv run pytest tests/security/test_tf_azure_aks_security.py`
- [x] 1.2 Declare api_server_authorized_ip_ranges in tf/azure/variables.tf and configure api_server_access_profile in tf/azure/main.tf
  - Verification: `$ uv run pytest tests/security/test_tf_azure_aks_security.py`
- [x] 1.3 Verify that trivy config reports no AZU-0041 on tf/azure
  - Verification: `$ trivy config tf/azure`

## Workflow follow-up

- Item #4949 tracks resolving AZU-0043 (network policy).
