# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests of the filer, the command, the workflow, the policy rule and the ignore file
  - Verification: `$ uv run devops ci test tests/security/test_alert_filer.py tests/commands/test_scan_alerts.py tests/invariants/test_workflow_contracts.py tests/invariants/test_agents_md.py tests/security/test_trivy_config_ignore.py`
- [x] 1.2 Add the filer, the command `devops scan alerts` and the workflow
  - Verification: `$ uv run devops ci test tests/security/test_alert_filer.py tests/commands/test_scan_alerts.py tests/invariants/test_workflow_contracts.py tests/invariants/test_agents_md.py`
- [x] 1.3 Make the `trivy config` scan name `.trivyignore.yaml` when it exists
  - Verification: `$ uv run devops ci test tests/security/test_trivy_config_ignore.py`

## 2. Documents

- [x] 2.1 Add the section "Judging a Trivy-config Alert" to `SECURITY.md`, and regenerate the command pages
  - Verification: `$ uv run devops ci docs`
