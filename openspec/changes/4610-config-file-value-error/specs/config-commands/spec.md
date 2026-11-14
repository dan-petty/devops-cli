## ADDED Requirements

### Requirement: A refused config-file value is one error line
`load_settings` SHALL raise a `ConfigurationError` that names the file, the config key and the reason when a validator refuses a value that a config file holds. The error SHALL hold no pydantic URL and the command SHALL print no traceback.

#### Scenario: A refused effort value in a config file
- **WHEN** a config file sets `roadmap.implement.effort` to `["huge"]` and `load_settings` reads it
- **THEN** the call raises `ConfigurationError` with the key `roadmap.implement.effort`, the file and the reason, and the text holds no pydantic URL

#### Scenario: A duplicate service repository in a config file
- **WHEN** a config file sets `service.repos` to `["Owner/Repo", "owner/repo"]`
- **THEN** the error names `service.repos` and the repeated repository

#### Scenario: The command prints no traceback
- **WHEN** `devops roadmap inbox` runs with such a config file
- **THEN** it exits 1, prints one error line with the key, and prints no `Traceback (most recent call last):`
