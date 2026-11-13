## Purpose
The branch-name pre-commit hook refuses a commit on a branch outside the accepted forms, and it accepts the copilot branch that the Copilot cloud agent works on.

## ADDED Requirements

### Requirement: The branch-name hook accepts a copilot branch
The `branch-name` hook SHALL accept each branch name of the form `copilot/<slug>` that the Copilot cloud agent creates, so a commit on it gets no refusal from the hook.

#### Scenario: copilot branch names pass the hook
- **WHEN** A test runs the pattern argument of the branch-name hook with Python re.search on copilot/fix-login-bug, copilot/sub-pr-12 and copilot/fix-4773
- **THEN** No name matches the pattern, so the hook refuses no commit on a copilot branch

### Requirement: The branch-name rule keeps its refusal for other names
The `branch-name` hook SHALL refuse each branch name that is neither `<type>/<issue>-<slug>` nor `copilot/<slug>`.

#### Scenario: a name outside both forms fails
- **WHEN** The same test runs the pattern on copilot/, copilot/Fix-login, copilot/fix_login and feature/12-widget
- **THEN** Each name matches the pattern, so the hook refuses each commit on it

### Requirement: The hook states both accepted branch forms
The name of the `branch-name` hook and the comment above it SHALL state both accepted branch forms.

#### Scenario: the hook text names copilot
- **WHEN** A test reads the name and the comment lines of the branch-name hook in the pre-commit config
- **THEN** The text holds <type>/<issue>-<slug> and copilot/
