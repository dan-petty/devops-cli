# Tasks

## 1. Renovate configuration

- [x] 1.1 Write the failing tests of the preset and the repository config: managers on, file patterns, custom managers, coupled groups, schedule, limits, security settings, approvals, labels and title length
  - Verification: `$ uv run devops ci test tests/core/test_renovate_config.py tests/tools_lock/test_tools_lock.py`
- [x] 1.2 Add `.github/renovate/base.json` and make `.github/renovate.json` extend it
  - Verification: `$ uv run devops ci test tests/core/test_renovate_config.py tests/tools_lock/test_tools_lock.py`
- [x] 1.3 Write the failing test that each uv header of the tools lock requirements files gives each option with `=`, then write the headers and the bump step of `tools.lock` in that form, so the pip-compile manager reads them
  - Verification: `$ uv run devops ci test tests/core/test_renovate_config.py`
- [x] 1.4 Validate both files with the official validator of `renovate@44.235.1`
  - Verification: `$ npx --yes --package renovate@44.235.1 renovate-config-validator --strict --no-global .github/renovate.json .github/renovate/base.json`

## 2. Workflows

- [x] 2.1 Write the failing contract test: Fail-to-Pass Check skips `devops-cli-renovate[bot]` and names no other author
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 2.2 Add the author condition to `.github/workflows/fail-to-pass.yml`
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 2.3 Pin setup-uv `0.13.6` in `release.yml`, fix the `docker/build-push-action` and `docker/setup-buildx-action` comments, and pin `actions/attest-build-provenance` to the commit of `v4.2.2`
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`

## 3. Documents

- [x] 3.1 Describe the schedule, the groups, the approvals and the coupled pins in CONTRIBUTING.md (Dependency Versions) and docs/SDLC.md
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #4902 adds the managers of the 20 binaries of the tools lock and of the gh download, with the repin command.
- #4905 allows the `postUpgradeTasks` commands in `allowedCommands`, puts the `devops install-tools` target directory on `PATH`, and sets `RENOVATE_X_SUPPRESS_PRE_COMMIT_WARNING`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
