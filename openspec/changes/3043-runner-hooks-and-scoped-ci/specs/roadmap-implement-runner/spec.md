# Spec Delta

## ADDED Requirements

### Requirement: The local hooks run only programs that the runner image holds
Each `language: system` hook of `.pre-commit-config.yaml` SHALL start with `uv run`, and the tool that it runs SHALL be a dev dependency of the lock (`ast-grep-cli`, `devops`) or a program that the `runner` stage of the `Dockerfile` installs (`openspec`). The `pre-commit` package SHALL be a dev dependency of the lock. The hook environments SHALL be fetched at run time into the home volume, because the perimeter admits public HTTPS.

#### Scenario: A hook that needs another program
- **WHEN** a local hook has the entry `actionlint`
- **THEN** the test fails and names the hook and the program

#### Scenario: The config as it is
- **WHEN** the test reads `.pre-commit-config.yaml`, `pyproject.toml` and `Dockerfile`
- **THEN** every local hook passes
