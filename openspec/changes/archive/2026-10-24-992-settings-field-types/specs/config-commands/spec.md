# Spec Delta

## ADDED Requirements

### Requirement: Settings values validate against field types at load and on set
When settings values load from environment variables or configuration files, or update through `devops config set`, each value SHALL pass the declared type and constraints of its field. An invalid value SHALL cause the load or command to fail with a configuration error naming the setting or environment variable without exposing sensitive input text.

#### Scenario: Non-positive timeout in environment variable is refused
- **WHEN** an environment variable sets a timeout or duration field to `0`, `-1`, `inf`, or non-numeric text
- **THEN** loading settings fails with a configuration error naming the environment variable

#### Scenario: Malformed URL in configuration file or command is refused
- **WHEN** a configuration file or `devops config set` specifies a URL lacking an approved scheme or matching host origin
- **THEN** the operation fails with an error naming the key without exposing credentials
