## ADDED Requirements

### Requirement: Dry-run diff redacts credential values
When `devops config unset <key> --dry-run` removes a key whose name is a credential, the diff SHALL show `***REDACTED***` in place of the value.

#### Scenario: Credential value is redacted in the dry-run diff
- **WHEN** A config file holds `ai.api_key: sk-ant-fake123` and the user runs `devops config unset ai.api_key --dry-run`
- **THEN** The diff line for the removed key shows `***REDACTED***`, and no line of the diff holds `sk-ant-fake123`.

#### Scenario: Non-credential value stays in the dry-run diff
- **WHEN** A config file holds `ai.model: llama3` and the user runs `devops config unset ai.model --dry-run`
- **THEN** The diff line for the removed key shows `llama3`.
