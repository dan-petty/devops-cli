# Proposal

## Why

Issue #2110 carries out the decision that the owner made on 2026-10-22 in #1752. The pre-push hook `devops-ci-pre-push` runs the full `uv run devops ci` before each push. On 2026-10-24, the 75 passing gates of the last 24 hours had a median sum of check durations of 23 minutes, and the load average of the host reached 88. Each push follows a rebase or an amend, so the cache of the gate cannot help. Under that load, tests that wait for a time window fail (#2069, #2092), and the whole gate runs again.

The decision: the pre-push hook runs only the fast static checks (`ruff` lint, `ruff` format, `actionlint` and `zizmor`). The full `uv run devops ci` stays a manual command. Remote CI is the authoritative gate (ADR 0004). The hook can change after the required checks of `main` gate each topic pull request, and that condition holds now.

## What Changes

- The pre-push hook `devops-ci-pre-push` in `.pre-commit-config.yaml` runs `uv run devops ci --check --only lint,format,actionlint,zizmor`. `--only` takes a comma-separated list of check names, so one hook runs the four checks. `--check` makes the hook examine the pushed tree and change no file, as the `Static Analysis` job of CI does. The comment on the hook says what it runs and where the other checks run. The comment on the `openspec-gate` hook no longer says that each push runs the `openspec` row.
- A test in `tests/test_workflow_contracts.py` holds the pre-push hooks to exactly the `lint`, `format`, `actionlint` and `zizmor` rows of the `devops ci` table, in check-only mode.
- AGENTS.md rule 5 says what runs where: the fast static checks before a push, the required checks of CI before a merge, and the full `uv run devops ci` by hand.
- `CONTRIBUTING.md`, `docs/SDLC.md` (the lifecycle diagram, Phase 4 and Phase 6), `docs/TESTING.md`, `docs/ROUTINE_TASKS.md`, `docs/SELF_IMPROVEMENT.md`, `openspec/config.yaml` (the apply guidance) and the knowledge base (`ci_quality_gate.md`, `continuous_integration_and_progressive_verification.md`, `ruff_mypy_pytest.md`) say the same. No document says that the pre-push hook runs the full gate.
- The check in `tests/test_agents_md_claims.py` that finds a deleted process in an agent instruction also finds the phrases that say the pre-push hook runs the full gate.
- The chat invariant in `DEFAULT_CHAT_INVARIANTS` that told the model to push only after `uv run devops ci` passes tells it to push only through the pre-push hook. The comment on `CONST_CI_TEST_BUDGET_SECONDS`, a comment in `.github/workflows/ci.yml`, the docstring of `compute_workspace_fingerprint` and five test docstrings no longer say that the hook runs the full gate.

This change alters no behavior that a consumer of devops observes. It changes a hook of this repository, documents, comments, docstrings and one line of the text that the model of `devops ai chat` reads. No `devops` command, option, help text or output changes, and no spec states the words of the chat invariants. So `.openspec.yaml` sets `skip_specs: true`.

This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `docs/adr/0004-ci-is-the-authoritative-gate.md`: its amendment line said "with the strict policy"; it now says that the strict policy is off and that the release pull request shows a defect on `main`, as ADR 0014 records.
- `.pre-commit-config.yaml`: the pre-push hook and two comments.
- `tests/test_workflow_contracts.py`: the new test of the pre-push hook.
- `tests/test_agents_md_claims.py`: five phrases added to the deleted processes.
- `AGENTS.md`, `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/TESTING.md`, `docs/ROUTINE_TASKS.md`, `docs/SELF_IMPROVEMENT.md`, `openspec/config.yaml` and three knowledge base documents: what runs where.
- `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/ci/cache.py`, `.github/workflows/ci.yml`, `tests/test_ci.py`, `tests/test_ci_cache_fingerprint.py`, `tests/test_test_module_independence.py` and `tests/test_test_selection.py`: text only.

## Feasibility

I confirmed the premise against the real system on 2026-10-24:

- `uv run devops ci --help` at 02fee43a: `--only` runs "the specified check names (comma-separated or repeated)". `resolve_selected_specs` in `src/devops_cli/commands/ci.py` splits each value at the commas, and `get_check_specs` names the four checks `lint`, `format`, `actionlint` and `zizmor`. `resolve_step_rows("uv run devops ci --check --only lint,format,actionlint,zizmor")` returns exactly these four rows.
- `uv run devops gh api repos/dan-petty/devops-cli/rulesets/21466414`: the `main` ruleset has a `required_status_checks` rule with `Static Analysis`, `Tests & Coverage` and `Semantic PR title`. So the condition of #1752 holds.
- `.github/workflows/ci.yml`: the `Static Analysis` job runs `uv run devops ci --check --no-cache --skip test,outdated`, and the `Tests & Coverage` job runs `uv run devops ci --check --no-cache --only test`. So each check that the hook no longer runs, except the `outdated` report that the advisory, scheduled `dependency-freshness` job runs, still runs in a required check before a merge, and the four checks of the hook run there too.
- `devops scan workflows`, the command of the `zizmor` row, runs zizmor offline, so the hook makes no network request for it.
- `uv run pre-commit run --hook-stage pre-push --all-files` on 16 CPUs, with the environment synced first. On the base tree (02fee43a), the old hook passed in 285.3 s, with one other full gate on the host and a 1-minute load average of 22; its slowest rows were `test` (4 min 17 s), `typecheck` (3 min 49 s) and `security` (3 min 39 s). With this change, the hook passed in 9.0 s, 9.1 s and 8.7 s on a quiet host (1-minute load average 4 to 5): `lint` 1.0 s, `format` 1.9 s, `actionlint` 3.1 s and `zizmor` 5.7 s, in parallel. Under a 1-minute load average of 45, it passed in 22.8 s. It changed no file.

## Existing Tool Considered

pre-commit, which the repository already uses, runs the hook, and `devops ci --only` selects the checks from the check table that CI runs. The alternative was four pre-commit hooks of the `pre-push` stage: `ruff-check` and `ruff-format` from `ruff-pre-commit`, an `actionlint` hook and a `zizmor` hook. It was rejected: the `ruff-pre-commit` revision is pinned apart from the locked `ruff`, and the `zizmor` row runs through `devops scan workflows` with the repository's settings. One `devops ci --only` hook runs the same commands as the `Static Analysis` job, so the hook and CI cannot disagree. The change adds no code and deletes no code.
