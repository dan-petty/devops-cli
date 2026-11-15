## ADDED Requirements

### Requirement: A lower-case name after a keyword is not a credential
The space-separated keyword rule SHALL mask the value after `token`, `bearer`, `secret`, `password` or `api_key` only when the value holds a digit, a dot, an internal capital, or 24 characters or more. A lower-case name with hyphens SHALL stay as written. The assignment forms SHALL keep the wider rule of `_mask_literal`.

#### Scenario: A Kubernetes object name
- **WHEN** the text holds `Secret devops-cli`
- **THEN** the masker returns the text unchanged

#### Scenario: A subcommand
- **WHEN** the text holds `token revoke-self`
- **THEN** the masker returns the text unchanged

#### Scenario: A token after a keyword
- **WHEN** the text holds `token abc123def456ghi789`
- **THEN** the masker returns `token <masked-token>`

#### Scenario: An assignment
- **WHEN** the text holds `auth_token: my-service-account`
- **THEN** the masker masks the value as the assignment form does
