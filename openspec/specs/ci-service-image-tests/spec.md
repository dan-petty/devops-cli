# ci-service-image-tests Specification

## Purpose
The in-image suite proves that the tests pass in the Python and the OS of the Service image. It runs where an image input changes, and daily for all other changes, so that a push to a pull request does not wait for it.

## Requirements

### Requirement: The in-image suite runs nightly and on image pull requests
The Service Image Tests workflow SHALL run on the daily schedule, on a manual run, and on a pull request that changes `Dockerfile`, `.dockerignore`, `pyproject.toml`, `uv.lock`, `src/devops_cli/tools_lock/` or the workflow file. A pull request that changes only other `src/` files SHALL start no job of it.

#### Scenario: A pull request changes only src
- **WHEN** a pull request changes only files under `src/` that are not under `src/devops_cli/tools_lock/`
- **THEN** GitHub starts no Service Image Tests job for it

#### Scenario: A pull request changes an image input
- **WHEN** a pull request changes `uv.lock`
- **THEN** the six Service Image Tests shards run the suite inside the built Service image

#### Scenario: The daily run
- **WHEN** the daily schedule fires
- **THEN** the six shards run the suite inside the Service image built from `main`

#### Scenario: The schedule trigger is removed
- **WHEN** the workflow has no `schedule` trigger
- **THEN** the architectural invariant test fails
