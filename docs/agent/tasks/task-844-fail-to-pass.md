# Task 844: Fail-to-Pass Check Proving a Fix's Tests Fail on Its Base

**Issue**: [#844](https://github.com/dan-petty/devops-cli/issues/844)
**Feasibility**: Verified against `src/devops_cli/commands/ci.py`, `src/devops_cli/github/defect_classifier.py`, `pyproject.toml`, and git history (`5768cd9` vs `36b2bee`) that replaying changed `tests/**/test_*.py` files against a materialised merge-base tree with `tests/` overlaid reproduces 16 failed and 24 passed in `tests/test_ai_fixer.py` and classifies defect PRs via `is_defect_pr`.

## Deliverables

- [x] Implement `src/devops_cli/ci/fail_to_pass.py` and `devops ci fail-to-pass` in `src/devops_cli/commands/ci.py` to resolve the merge base, list added or modified `tests/**/test_*.py` files, materialise the base tree in a temporary directory with the head's `tests/` overlaid, run pytest (`-o addopts=`, `-p no:cacheprovider`, `--junitxml`), and report per-test outcomes (`failed`, `errored`, `passed`).
- [x] Enforce defect PR gating via `is_defect_pr` (`src/devops_cli/github/defect_classifier.py`) so defect PRs exit non-zero unless at least one changed test fails in the call phase on base or the PR body contains `Fail-to-pass: not applicable: <reason>` (echoed to `$GITHUB_STEP_SUMMARY`), while collection errors and non-defect PRs are handled per contract.
- [x] Add `.github/workflows/fail-to-pass.yml` triggered on `pull_request` (`[opened, synchronize, reopened, edited, labeled]`) into `release/**` (into `main` until #1721) with `fetch-depth: 0`, passing `PR_TITLE`, `PR_LABELS`, and `PR_BODY` via `env` with no `${{` inside `run:`, and replaying `5768cd9` against `36b2bee` in a self-check job when its own files change.
- [x] Update `AGENTS.md` and `src/devops_cli/ai/instruction_generator.py` to instruct fix PRs to cite the `fail-to-pass` check run instead of typing failure counts by hand.
- [x] Add unit tests in `tests/test_fail_to_pass.py` and workflow contract test `test_workflow_contract_fail_to_pass` in `tests/test_workflow_contracts.py`.
