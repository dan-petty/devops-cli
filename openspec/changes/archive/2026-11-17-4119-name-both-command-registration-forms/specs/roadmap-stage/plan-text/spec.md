## ADDED Requirements

### Requirement: The stage prompt names both command registration forms
The stage prompt SHALL state that a CLI command registers its name by the string literal of `@app.command("name")` or by the function name under `@app.command()` or `@<group>.command()`, and SHALL state that a check for a command name is a negative search for the bare name.

#### Scenario: The prompt names the literal and the function forms
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the prompt holds `@app.command("name")`, `@app.command()`, `@<group>.command()` and `def <name>(`

#### Scenario: The prompt names the bare-name negative search
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the prompt holds `! git grep -n <name> src/ tests/`, `@app.command("<name>")` and `def <name>(`
