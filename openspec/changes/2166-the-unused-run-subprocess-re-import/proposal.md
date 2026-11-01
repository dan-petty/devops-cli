# Proposal

## Why

Issue #2166: two accommodations for tests reached the code, and no check stopped a third from entering `src/`. Most of the issue is done on `main`. Two parts remain:

- The private alias `_prepare_cmd = prepare_tool_cmd` in `src/devops_cli/core/process.py` still stands. The shared process fake imports it, and a test imports it. `docs/TESTING.md` says no test imports a private name from `devops_cli`.
- The ceiling of the ratchet for `# noqa: F401` in `src/` is 15, and the real count is 0. The ratchet lets 15 new unused re-imports in with no failure.

## What Changes

- Remove the alias `_prepare_cmd` from `src/devops_cli/core/process.py`. The process fake and `tests/core/test_process.py` use the public `prepare_tool_cmd`.
- Set the ceiling `src noqa: F401` of the existing suppression ratchet to 0.
- The change fits one pull request.
- The change has no spec delta and sets `skip_specs: true`. It alters no command, option, message, manifest or service behavior. The alias had no caller in `src/`, and the ratchet is a test.

## Acceptance

The criteria of #2166, and the group that delivers each:

- `src/devops_cli/security/ruff.py` imports no name it does not use, and its tests patch no `devops_cli` name: already true on `main`, so no group (see Feasibility).
- `rg -n "_prepare_cmd" src tests` prints nothing: group 1.
- A `devops ci` row fails on a new unused `# noqa: F401` import in `src/`, and shows it failing on an added re-import: group 2. The check is the existing suppression ratchet, which runs in the `test` row of `devops ci`. Group 2 holds its ceiling at 0 and shows the failure on an added import. This replaces the new row that the issue names, because the ratchet already counts this kind (see Feasibility). Pending a person: confirm that the ratchet at 0 meets the criterion, or ask for the extra `ruff --ignore-noqa` row.
- The check runs on the stock runner with no install, and its job stays under 5 minutes: group 2. The ratchet runs in the `test` row that CI already runs, so it adds no job and no install.
- `uv run devops ci` passes: the checks of the pull request, run by CI. Group 1 and group 2 each end with the narrow test run that covers their files.

## Feasibility

Each fact below comes from a run on `origin/main` at 1c20865a, on 2026-11-01.

- The re-import in `src/devops_cli/security/ruff.py` is gone. `grep -n "run_subprocess\|noqa" src/devops_cli/security/ruff.py` prints nothing. Commit a1950694 (#1332, merged 2026-10-30) removed it; `git log -S run_subprocess -- src/devops_cli/security/ruff.py` lists that commit last.
- No site is left. `git grep -n "noqa: F401" -- src` prints nothing (exit 1), and `uv run ruff check --select F401 --ignore-noqa src` prints `All checks passed!` (ruff 0.16.8). The issue counted 15 at b170358e.
- No test of the ruff scanner patches a `devops_cli` name. `git grep -n patch -- tests/security/test_review_ruff_mypy_evidence.py` prints nothing. The one `patch.object(ci_module, "run_subprocess", ...)` in `tests/commands/test_ci.py:1938` is a test of `ci.py`.
- The alias stands. `git grep -n "_prepare_cmd" -- src tests` prints 8 lines: `src/devops_cli/core/process.py:482`, `tests/core/test_process.py:583,585,592,598` and `tests/support/fakes/process.py:23,272,361`. No other file in `src/` uses it. `prepare_tool_cmd` (`src/devops_cli/core/process.py:474`) is the public function. `ci.py` already calls it.
- The ratchet exists. `DEFAULT_SUPPRESSION_CEILINGS` in `tests/invariants/test_architectural_invariants.py:176` holds `"src noqa: F401": 15`. `_collect_suppressions` counts every `# noqa` comment in `src/` by code, and a bare `# noqa` counts under the kind `src noqa`, which has no ceiling and so a ceiling of 0. The collector gives 0 for `src noqa: F401`, so the ceiling is 15 above the count.
- The gap is real. A probe file `src/devops_cli/f401_probe.py` with the line `import os  # noqa: F401` makes `uv run ruff check --select F401 --ignore-noqa src` report `Found 1 error`, while `uv run devops ci test tests/invariants/test_architectural_invariants.py -k suppressions_stay_under_their_ceilings` prints `1 passed`. The probe file was removed after the run.
- Nothing newer does this work. `uv run devops gh api repos/dan-petty/devops-cli/issues/1332 --jq .state` prints `closed`, and the same call for #1309 prints `closed`. #1336 is open: it turns ratchets into bans, and does not touch this ceiling. `git grep -ln "_prepare_cmd" -- openspec/changes` outside this folder prints nothing.

## Existing Tool Considered

The suppression ratchet of #849 (`tests/invariants/test_architectural_invariants.py`) already counts `# noqa: F401` in `src/` and fails when the count passes its ceiling. It needs a ceiling of 0 and no new code. Ruff with `--select F401 --ignore-noqa` is the other open tool. It reports the same sites as the ratchet, so a second guard for the same sites has no extra value now. #1336 turns the ratchets into bans, so a second guard would also be one more thing to remove.

The change deletes one name, `_prepare_cmd`, and one private import in each of the process fake and `tests/core/test_process.py`.

## Impact

- Code: `src/devops_cli/core/process.py` (the alias line).
- Tests: `tests/support/fakes/process.py`, `tests/core/test_process.py`, `tests/invariants/test_architectural_invariants.py`.
- Existing code to keep passing: `prepare_tool_cmd` and its callers in `src/devops_cli/commands/ci.py` and `src/devops_cli/core/process.py`; the 128 test files that use the process fake; `test_suppressions_stay_under_their_ceilings`.
