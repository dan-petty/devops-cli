## ADDED Requirements

### Requirement: The implement prompt forbids polling
The implement prompt SHALL state that a shell call returns when its command ends, and MUST forbid polling with `sleep`, `time.sleep` or a repeated `tail`.

#### Scenario: The prompt holds the no-poll rule
- **WHEN** A test reads `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- **THEN** The prompt says that a shell call returns when its command ends, and names sleep, time.sleep and a repeated tail as ways not to poll.
