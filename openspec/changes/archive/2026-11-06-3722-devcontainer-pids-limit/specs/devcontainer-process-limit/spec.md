## Purpose
The process limit of the devcontainer: a burst of VS Code file searches must not fill the container and stop the tools of agent sessions.

## ADDED Requirements

### Requirement: Devcontainer process limit
The devcontainer configuration SHALL set the container process limit to at least 4096 with the `--pids-limit` option in `runArgs`, and SHALL keep `--gpus all` there.

#### Scenario: Run arguments hold the process limit
- **WHEN** A test reads `runArgs` from `.devcontainer/devcontainer.json`.
- **THEN** The list holds `--pids-limit=8192` and `--gpus` followed by `all`.

### Requirement: Process limit guard
A test SHALL fail when the `--pids-limit` value of `.devcontainer/devcontainer.json` is absent or below 4096.

#### Scenario: A low process limit is below the minimum
- **WHEN** The reader gets `--pids-limit` followed by `2048`.
- **THEN** It returns 2048, which is under the minimum of 4096.
