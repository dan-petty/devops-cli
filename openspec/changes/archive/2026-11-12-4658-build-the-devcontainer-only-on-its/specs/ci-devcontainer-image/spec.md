## Purpose
The DevContainer Image check proves that the devcontainer image builds and starts as its remote user. It runs where an image input changes, and daily for all other changes, so that a push to a pull request that changes only the CLI source does not wait for it.

## ADDED Requirements

### Requirement: The DevContainer image builds on its own inputs
The DevContainer Image workflow SHALL run on the daily schedule, on a manual run, and on a pull request that changes an input of the image other than `src/`: `.devcontainer/`, `.dockerignore`, `pyproject.toml`, `uv.lock`, `README.md`, `src/devops_cli/tools_lock/`, its two actions or the workflow file. A pull request that changes only other `src/` files SHALL start no job of it.

#### Scenario: A pull request changes only src
- **WHEN** a pull request changes only files under `src/` that are not under `src/devops_cli/tools_lock/`
- **THEN** GitHub starts no DevContainer Image job for it

#### Scenario: A pull request changes an image input
- **WHEN** a pull request changes `.devcontainer/Dockerfile`
- **THEN** the DevContainer Image job builds the image and starts it as its remote user

#### Scenario: The daily run
- **WHEN** the daily schedule fires
- **THEN** the DevContainer Image job builds the image from `main` and starts it

#### Scenario: The filter misses an input
- **WHEN** the `paths` filter does not hold a file that `.devcontainer/Dockerfile` copies, other than `src/`
- **THEN** the architectural invariant test fails
