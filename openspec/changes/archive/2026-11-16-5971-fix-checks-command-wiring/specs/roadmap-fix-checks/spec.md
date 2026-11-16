## ADDED Requirements

### Requirement: The command repairs a failed check in a runner Job
With `--confirm`, `devops roadmap step fix-checks` SHALL refuse to run outside a runner Job. In a runner Job it SHALL give the step a worktree on the head branch of the pull request, the tier 1 fixers, and the model fix on the task `ai.tasks.fix_checks`. The step SHALL push the commit of a fixer to the head branch with a lease on the judged head, and SHALL return `repaired` with the new head.

#### Scenario: A failed check whose log names a file of the plan ends repaired
- **WHEN** the command runs with `--confirm` on a bot pull request whose `Static Analysis` check failed with a log that names a file of the plan, and the model fix commits a change
- **THEN** the step returns `repaired`, and the head branch on `origin` has one new commit

#### Scenario: The command refuses to repair outside a runner Job
- **WHEN** the command runs with `--confirm` in a process that is not a runner Job
- **THEN** the command exits 1 and reads no pull request

### Requirement: The step writes nothing without --confirm
Without `--confirm`, the step SHALL return `planned` with the action that it would take. It SHALL post no comment, write no mark, make no checkout, run no fixer and push nothing.

#### Scenario: A run without --confirm writes nothing
- **WHEN** the step runs without `--confirm` on a bot pull request with a failed check
- **THEN** the step returns `planned`, and GitHub, the store and the branch are unchanged

### Requirement: The model fix of one run has a cap of new tokens
The model fix of one `fix-checks` run SHALL stop before a model request when its new tokens (input that the provider did not read from its cache, and output) reach `roadmap.fix_checks.token_budget`. The default SHALL be 16,000,000. The stop SHALL name the setting, and the cap SHALL get no extension.

#### Scenario: A fix step at its cap stops and names the setting
- **WHEN** the new tokens of the step reach the cap
- **THEN** the step stops before the next request, and the reason names `roadmap.fix_checks.token_budget`

### Requirement: The step marks a repaired draft ready only by the readiness rule
When the step finds an implement draft that it repaired, with every check passing on the head, it SHALL ask `draft_readiness`. It SHALL mark the draft ready with the expected head only when the answer is ready, and SHALL return `ready`. Otherwise it SHALL leave the draft as it is.

#### Scenario: A repaired draft whose checks pass is marked ready
- **WHEN** the step runs with `--confirm` on a repaired implement draft whose checks pass and that `draft_readiness` calls ready
- **THEN** the step marks the draft ready with the expected head and returns `ready`
