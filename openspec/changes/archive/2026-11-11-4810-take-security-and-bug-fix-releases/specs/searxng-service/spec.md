## MODIFIED Requirements

### Requirement: A bump of the image tells the person what to check
The Renovate configuration SHALL hold a rule for the image whose pull request text names the refresh of the engine names file and names no age of the tag.

#### Scenario: The note is missing
- **WHEN** a test reads `.github/renovate.json`
- **THEN** one rule matches the image, its note names the engine names file, and its note does not hold `days old`
