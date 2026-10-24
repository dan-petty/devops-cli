# Tasks

## 1. The pre-push hook runs only the fast static checks

- [x] 1.1 Write a failing test in `tests/test_workflow_contracts.py` that holds the pre-push hooks to the `lint`, `format`, `actionlint` and `zizmor` rows of the `devops ci` table, in check-only mode (`uv run devops ci test tests/test_workflow_contracts.py`).
- [x] 1.2 Make the `devops-ci-pre-push` hook in `.pre-commit-config.yaml` run `uv run devops ci --check --only lint,format,actionlint,zizmor`, with a comment that says what it runs and where the other checks run, and correct the comment on the `openspec-gate` hook (`uv run devops ci test tests/test_workflow_contracts.py tests/test_openspec_scaffold.py`).
- [x] 1.3 Time the pre-push hook on the base tree and with the change, and record both times in the proposal (`uv run pre-commit run --hook-stage pre-push --all-files`).

## 2. The documents say what runs where

- [x] 2.1 Add the phrases that say the pre-push hook runs the full gate to the deleted processes of `tests/test_agents_md_claims.py`, and see the check fail on AGENTS.md, CONTRIBUTING.md, docs/SDLC.md, docs/TESTING.md and two knowledge base documents (`uv run devops ci test tests/test_agents_md_claims.py`).
- [x] 2.2 Rewrite AGENTS.md rule 5, and correct `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/TESTING.md`, `docs/ROUTINE_TASKS.md`, `docs/SELF_IMPROVEMENT.md`, the apply guidance of `openspec/config.yaml` and the knowledge base documents `ci_quality_gate.md`, `continuous_integration_and_progressive_verification.md` and `ruff_mypy_pytest.md` (`uv run devops ci test tests/test_agents_md_claims.py tests/test_kb.py tests/test_kb_manuals_metadata.py tests/test_docs.py`).
- [x] 2.3 Correct the chat invariant in `src/devops_cli/config/defaults.py`, the comments in `src/devops_cli/config/constants.py` and `.github/workflows/ci.yml`, the docstring in `src/devops_cli/ci/cache.py` and the docstrings in `tests/test_ci.py`, `tests/test_ci_cache_fingerprint.py`, `tests/test_test_module_independence.py`, `tests/test_test_selection.py` and `tests/test_workflow_contracts.py` (`uv run devops ci test tests/test_agent_invariants.py tests/test_ai_cmd.py tests/test_ci.py tests/test_ci_cache_fingerprint.py tests/test_test_module_independence.py tests/test_test_selection.py`).
- [x] 2.4 Regenerate the documentation and check it (`uv run devops docs generate --sync-readme`, `uv run devops docs check`).

## 3. Verification

- [x] 3.1 Run the OpenSpec gate (`uv run devops openspec check`).

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
