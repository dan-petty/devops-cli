## REMOVED Requirements

### Requirement: install-tools-request-plans
**Reason**: `devops install-tools` is gone (#4363).
**Migration**: The devtools image installs the tools.

### Requirement: install-tools-no-external-request
**Reason**: `devops install-tools status` is gone (#4363).
**Migration**: A tool states its own version with `--version`.
