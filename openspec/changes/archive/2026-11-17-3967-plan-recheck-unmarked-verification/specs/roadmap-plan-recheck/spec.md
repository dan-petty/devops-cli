## ADDED Requirements

### Requirement: Mark existing verification commands
The plan rewrite SHALL prepend `$ ` to the code span of each existing `Verification:` line that lacks the marker.

#### Scenario: Unmarked verification line is rewritten
- **WHEN** A task group has `- Verification: `uv run devops ci test tests/test_x.py` passes`.
- **THEN** `devops roadmap plan-recheck --confirm` writes `- Verification: `$ uv run devops ci test tests/test_x.py` passes` and adds no second `Verification:` line.

### Requirement: Mark all unmarked verification lines
The rewrite MUST mark every existing `Verification:` line without `$ ` in all task groups of the change.

#### Scenario: Several unmarked lines are rewritten
- **WHEN** `tasks.md` has two task groups, and each group has a `Verification:` line without `$ `.
- **THEN** `devops roadmap plan-recheck --confirm` prepends `$ ` to both code spans and leaves no unmarked `Verification:` line.

### Requirement: Keep marked verification commands
The rewrite SHALL leave an existing `Verification:` line that already starts its code span with `$ ` unchanged.

#### Scenario: Marked verification line is not changed
- **WHEN** A task group has `- Verification: `$ uv run devops ci test tests/test_x.py` passes`.
- **THEN** The rewrite leaves the code span and the surrounding text on that line unchanged.

### Requirement: Do not duplicate a verification line
The rewrite MUST NOT add a generated `Verification:` line to a task group that has an existing `Verification:` line after the marking pass.

#### Scenario: Existing line prevents a generated duplicate
- **WHEN** A task group has one `Verification:` line without `$ ` and a `Changes:` line that names a test file.
- **THEN** The rewritten task group has exactly one `Verification:` line.

### Requirement: Change only verification code spans
The rewrite SHALL change only the command code span on an existing `Verification:` line when it adds the `$ ` marker.

#### Scenario: Other code spans stay unchanged
- **WHEN** A task group has a non-verification code span without `$ ` and a `Verification:` line without `$ `.
- **THEN** The rewrite marks only the command code span and leaves the non-verification code span as it was.
