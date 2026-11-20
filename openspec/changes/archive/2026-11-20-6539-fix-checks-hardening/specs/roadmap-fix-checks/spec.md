## ADDED Requirements

### Requirement: The Job makes its process unreadable before the repair
With `--confirm` in a runner Job, `devops roadmap step fix-checks` SHALL clear the dumpable flag of its own process and adopt the orphans of a step before the step runs, as the implement Job does. A kernel that refuses either call SHALL stop the command before the step.

#### Scenario: A confirmed round hardens its process first
- **WHEN** the command runs with `--confirm` in a runner Job
- **THEN** it calls the runner check, then `deny_environment_reads`, then `adopt_orphans`, and only then the step
