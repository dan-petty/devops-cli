# Tasks: #4278

- [x] 1. Update release workflow concurrency and workflow contract test
  - [x] 1.1 Update `.github/workflows/release.yml` concurrency group to `release-${{ github.ref }}`
  - [x] 1.2 Update `tests/invariants/test_workflow_contracts.py` assertion
  - Verification: `uv run pytest tests/invariants/test_workflow_contracts.py -k test_release_please_makes_every_release_on_a_push_to_main`
- [x] 2. Update Renovate configuration and contract tests
  - [x] 2.1 Update `.github/renovate.json` with package rules and rebase configuration
  - [x] 2.2 Add tests to `tests/core/test_renovate_config.py`
  - [x] 2.3 Update `docs/SDLC.md`
  - Verification: `uv run pytest tests/core/test_renovate_config.py`
- [x] 3. Validate quality gates and OpenSpec check
  - Verification: `uv run devops openspec check && uv run devops ci --check`
