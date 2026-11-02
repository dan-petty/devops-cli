# Spec Delta

## MODIFIED Requirements

### Requirement: The extension, the stall and the ceiling are settings
The settings `roadmap.implement.deadline_stall_seconds` (default 4200), `roadmap.implement.deadline_extension_seconds` (default 5400) and `roadmap.implement.deadline_ceiling_seconds` (default 14400) SHALL set the stall time, the extension step and the ceiling, and each SHALL have an environment variable. The configuration SHALL refuse a stall above the extension, an extension above the ceiling, and a ceiling above 14400.

#### Scenario: The defaults
- **WHEN** the configuration is loaded with no value for the three settings
- **THEN** they are 4200, 5400 and 14400

#### Scenario: A stall above the extension
- **WHEN** the stall is set above the extension
- **THEN** the configuration is refused

#### Scenario: A ceiling above the cap
- **WHEN** the ceiling is set to 14401
- **THEN** the configuration is refused
