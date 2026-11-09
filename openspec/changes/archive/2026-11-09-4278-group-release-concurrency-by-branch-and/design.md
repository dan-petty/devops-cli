# Design: #4278

## Architecture
- **Release Concurrency**:
  - In `.github/workflows/release.yml`, the concurrency group is set to `release-${{ github.ref }}` while preserving `cancel-in-progress: false`.
  - In `tests/invariants/test_workflow_contracts.py`, the invariant `test_release_please_makes_every_release_on_a_push_to_main` asserts `{"group": "release-${{ github.ref }}", "cancel-in-progress": False}`.

- **Renovate Dependency Management**:
  - In `.github/renovate.json`:
    - `terraform` manager matches `tf/` configurations and applies `type/chore` and `scope/infra`.
    - `devcontainer` manager matches devcontainer definitions and applies `type/chore` and `scope/ci`.
    - `pre-commit` manager matches `.pre-commit-config.yaml` and applies `type/chore` and `scope/ci`.
    - `github-actions` manager specifies `pinDigests: true` to enforce commit SHA pinning with version comments.
    - `helm-values` and `helmv3` managers are disabled (`enabled: false`) to ensure Helm chart values remain deliberate bumps per `docs/SDLC.md`.
    - `rebaseWhen: "behind-base-branch"` keeps proposed dependency branches up to date.
  - In `tests/core/test_renovate_config.py`, contract tests assert these package rules exist with the expected manager names and taxonomy labels.
