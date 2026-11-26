## ADDED Requirements

### Requirement: The release check refuses a file outside the release set
The command `python -m devops_cli.release.release_files` SHALL read the files that the pull request changes from the compare of `main` and its head commit, SHALL exit 1 with one reason for each path that `RELEASE_FILES` does not hold or that the pull request does not modify, and SHALL exit 0 when every path is a release file that the pull request modifies.

#### Scenario: The command refuses a source file
- **WHEN** The compare of `main` and the head commit holds only `src/devops_cli/main.py`.
- **THEN** `check_release_files` exits 1 and writes the reason that names `src/devops_cli/main.py`.

#### Scenario: A clean release pull request
- **WHEN** The compare holds only `.release-please-manifest.json`, `CHANGELOG.md`, `pyproject.toml` and `uv.lock`, each with the status `modified`.
- **THEN** `check_release_files` exits 0 and writes the line that names the pull request as allowed.

#### Scenario: A failed read of GitHub
- **WHEN** The compare read answers an error of the GitHub API.
- **THEN** `check_release_files` exits 1 and writes the reason of the failed read.

### Requirement: The job Tests on Main runs the release check from the base commit
The job `Tests on Main` of `.github/workflows/ci.yml` SHALL check out the base commit of the pull request, SHALL run `python -m devops_cli.release.release_files` before the step that reads the push run of `main`, and SHALL fail when that command exits 1. The changed workflow SHALL pass `uv run devops ci --check --only actionlint,zizmor`.

#### Scenario: The changed workflow passes the validator
- **WHEN** The developer runs `uv run devops ci --check --only actionlint,zizmor` on the changed `.github/workflows/ci.yml`.
- **THEN** The command exits 0 and reports no finding.
