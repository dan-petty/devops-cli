## ADDED Requirements

### Requirement: The step marks an implement draft ready only by the readiness rule
When the step finds an implement draft that it repaired (`fix_checks.result` equal to `repaired`), or whose implement Job ended at the draft (`implement.result` equal to `drafted`), with every check passing on the head, it SHALL ask `draft_readiness`. It SHALL mark the draft ready with the expected head only when the answer is ready, and SHALL return `ready`. Otherwise it SHALL leave the draft as it is.

#### Scenario: A repaired draft whose checks pass is marked ready
- **WHEN** the step runs with `--confirm` on a repaired implement draft whose checks pass and that `draft_readiness` calls ready
- **THEN** the step marks the draft ready with the expected head and returns `ready`

#### Scenario: A drafted implement draft whose checks pass is marked ready
- **WHEN** the step runs with `--confirm` and `ready_only` on an implement draft whose item records `implement.result` equal to `drafted`, whose checks pass and that `draft_readiness` calls ready
- **THEN** the step marks the draft ready with the expected head and returns `ready`

## REMOVED Requirements

### Requirement: The step marks a repaired draft ready only by the readiness rule
**Reason**: The step also marks the draft of an implement Job that ended at the draft (#6559).
**Migration**: The requirement "The step marks an implement draft ready only by the readiness rule" holds the rule.

### Requirement: The implement repair loop keeps its own counts
**Reason**: The implement Job ends at the draft pull request and watches no check (#6559).
**Migration**: None: the implement Job runs no repair after its push, and the fix-checks Jobs keep the `fix_checks.*` counts.
