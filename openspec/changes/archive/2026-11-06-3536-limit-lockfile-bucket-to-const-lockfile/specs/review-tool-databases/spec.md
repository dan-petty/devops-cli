## ADDED Requirements

### Requirement: The review lockfile bucket holds known lockfile names only
The review pipeline SHALL place a file in the osv-scanner lockfile bucket only when the file's name is in `CONST_LOCKFILE_NAMES`. A file that only ends in `.lock` or `.lockb`, such as `rules.lock` or `tools.lock`, SHALL NOT reach the bucket, from the reviewed files or from the lockfiles beside them.

#### Scenario: rules.lock and tools.lock are excluded
- **WHEN** the classifier receives `src/devops_cli/review/rules/rules.lock`, `src/devops_cli/tools_lock/tools.lock` and `uv.lock`
- **THEN** the lockfile bucket holds `uv.lock` and holds neither `rules.lock` nor `tools.lock`

#### Scenario: A lockfile beside a reviewed file is a known name
- **WHEN** a reviewed file sits in a directory that holds `uv.lock` and `rules.lock`
- **THEN** the lockfile bucket holds `uv.lock` alone
