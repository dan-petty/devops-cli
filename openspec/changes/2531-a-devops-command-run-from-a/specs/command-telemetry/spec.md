## ADDED Requirements

### Requirement: Deleted CWD returns no git directory
_resolve_git_dir SHALL return None when Path.cwd() raises OSError because the working directory no longer exists.

#### Scenario: CWD deleted before call
- **WHEN** Path.cwd() raises FileNotFoundError because the process working directory was removed
- **THEN** _resolve_git_dir returns None and no exception propagates to the caller

### Requirement: Command completes without traceback from deleted CWD
A devops command run from a deleted working directory SHALL complete without an unhandled FileNotFoundError traceback from the telemetry setup.

#### Scenario: gh api from deleted directory
- **WHEN** a devops gh api command runs after its working directory has been deleted
- **THEN** the command exits with a clean result or a single error line, not a traceback

### Requirement: Normal resolution unaffected
_resolve_git_dir SHALL return the correct git directory when the working directory exists and contains a .git entry.

#### Scenario: CWD inside a git repository
- **WHEN** the process working directory exists and is inside a git repository
- **THEN** _resolve_git_dir returns the path to the .git directory
