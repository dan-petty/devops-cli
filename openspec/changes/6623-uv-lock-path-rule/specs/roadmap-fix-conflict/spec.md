## MODIFIED Requirements

### Requirement: A conflict on a release path stops with class conflict
When any conflicted path is a release path, the step SHALL NOT attempt automated resolution and SHALL stop with failure class `conflict`. A release path is `CHANGELOG.md`, a file of release-please (`.release-please-manifest.json`, `release-please-config.json`, `.release-please*`), or `pyproject.toml` when its `version =` line conflicts. The `version =` line of a package in `uv.lock` is none. The plan and the round SHALL ask one check (`release_conflict`), so the plan names the same stop.

#### Scenario: A conflict on a release path stops with class conflict
- **WHEN** a conflict occurs on `CHANGELOG.md` or a release manifest
- **THEN** the step halts with failure class `conflict`

#### Scenario: The plan and the round agree on a version line
- **WHEN** the side of the pull request in a conflict of `pyproject.toml` holds its `version =` line
- **THEN** the plan says `stop on the release path`, and a confirmed round stops and runs no fixer

#### Scenario: The version line of a package in uv.lock
- **WHEN** the side of the pull request in a conflict of `uv.lock` holds the `version =` line of a package, and the pull request also adds a file
- **THEN** the plan says that tier 1 takes the default branch, and a confirmed round takes the `uv.lock` of the default branch, runs `uv lock` once, and pushes the branch with the added file as its one change
