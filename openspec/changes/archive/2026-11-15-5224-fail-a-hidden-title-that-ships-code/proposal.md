# Proposal

## Why

Pull request #5198 merged with `docs(cli)` and changed runtime code under `src/devops_cli/`. `release-please-config.json` marks `docs` as hidden, so release-please opened no release pull request and the Service image stayed at 0.123.0. An implement run then failed at its docs step, because the image ran the older command (#5224).

## What Changes

- Add `src/devops_cli/github/release_title.py`: `hidden_types` and `releasable_types` read `release-please-config.json`, and `hidden_type_problem` refuses a hidden title type when the pull request changes a path under `src/devops_cli/` that is not a document.
- Add the step to `.github/workflows/pr-title.yml`, after the title action: it reads the changed files with `gh pr view` and runs the module.
- State the rule in `CONTRIBUTING.md`.
- Add `tests/github/test_release_title.py`, and update the workflow contract test.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-title-labels`: a hidden title type ships no runtime code.

## Impact

- Code: `src/devops_cli/github/release_title.py`, `.github/workflows/pr-title.yml`
- Tests: `tests/github/test_release_title.py`, `tests/invariants/test_workflow_contracts.py`
- Document: `CONTRIBUTING.md`

## Feasibility

- Read on `origin/main`, 2026-11-15. `release-please-config.json` holds `changelog-sections` with `hidden: true` for `docs`, `test`, `build`, `ci`, `style` and `chore`.
- `.github/workflows/pr-title.yml:37` holds the title action, and the job has no checkout yet.
- The path list comes from the pull request files of the event; no new permission is needed beyond `contents: read`.
- `uv run pytest tests/github/test_release_title.py tests/invariants/test_workflow_contracts.py` passes after the change.

## Existing Tool Considered

The title action checks the title form and cannot read the changed paths. The module reads the same `release-please-config.json` that release-please reads: about 2,500 tokens to build and 100 a quarter to keep.

## Dependencies

None.
