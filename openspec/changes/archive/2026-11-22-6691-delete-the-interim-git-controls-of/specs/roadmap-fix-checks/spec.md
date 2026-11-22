## MODIFIED Requirements

### Requirement: The Job makes its process unreadable before the repair
With `--confirm` in a runner Job, each phase of `devops roadmap step fix-checks` SHALL clear the dumpable flag of its own process first, before the runner check and before it reads a file of the run. A kernel that refuses the call SHALL stop the command before the step.

#### Scenario: A confirmed round hardens its process first
- **WHEN** the command runs with `--confirm` in a runner Job, with each value of `--phase`
- **THEN** it calls `deny_environment_reads`, then the runner check, or the check of the agent phase for `--phase agent`, and only then the phase
