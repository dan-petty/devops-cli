## MODIFIED Requirements

### Requirement: The scaffold prints the steps that remain manual
The command scaffold SHALL print each step that it cannot do, and that list SHALL name `devops docs generate`.

#### Scenario: The checklist names the regeneration command
- **WHEN** A user runs `devops new command sample hello`.
- **THEN** The output holds `devops docs generate` and names no list that the change derives.
