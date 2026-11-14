# Proposal

## Why

The Fail-to-Pass Check refuses a change that repairs a red `main` (#5590). While `main` is red, an unchanged test fails on the merge base of every change, and the check refuses each change for it, so no change can repair `main` and an agent cannot mark it ready. The check refuses for a test that the change does not touch, even when the change makes that test pass on the head. A repair of the base is no unclean replay, so the check must not refuse it, and must still refuse an unchanged test that does not pass on the head.

## What Changes

- The check replays the changed test files that hold an unchanged failure on the head tree: the working tree for `HEAD`, and one detached worktree of a named head, shared with the head gate rows.
- An unchanged test that fails on base and passes on head no longer refuses the replay and is named as repaired on head; one that does not pass on head still refuses it.
- The gate counts only a changed test that fails on base, so a repaired test alone satisfies nothing, as the base requirement on the title, label and body already states.
- A head replay that writes no complete JUnit report refuses the replay and names the head run and its exit status.
- `devops ci fail-to-pass --dry-run` lists the head pytest run and the head worktree with their conditions.
- The report's unchanged-failure sentence names the head, and two new sentences name a repaired test and a head run that could not run.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-fail-to-pass`: The report names a repaired test, A head replay that cannot run refuses the replay, The dry run lists the head replay, An unchanged test that still fails on the head refuses the replay, The head run of a named head uses a worktree of that head

## Impact

- Code: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/ci/test_fail_to_pass.py`

## Feasibility

- The probe lines confirm the two cited paths: `The path `src/devops_cli/ci/fail_to_pass.py` is a file of the staging commit.` and `The path `tests/invariants/test_mcp_server_image.py` is a file of the staging commit.`
- `read_file` of `src/devops_cli/ci/fail_to_pass.py` lines 706-740 showed `run_fail_to_pass` replaying pytest on the merge-base tree only, with `src/devops_cli/ci/fail_to_pass.py:726:_run_gate_rows_on_head(root, head, list(rows), Path(tmp) / "head") if rows else {}`, and `src/devops_cli/ci/fail_to_pass.py:703:return run, _unchanged_failures(`.
- `read_file` of `src/devops_cli/ci/fail_to_pass.py` lines 803-831 showed the refusal: `src/devops_cli/ci/fail_to_pass.py:813:if report.unchanged_failed:` with the sentence at `src/devops_cli/lang/en/messages.py:2286:fail_to_pass_unchanged_failed`. That is the defect of the issue: an unchanged failure refuses whether or not the head repairs it.
- `read_file` of `tests/ci/test_fail_to_pass.py` lines 130-330 and 779-1060 showed the fake that answers both pytest runs with one JUnit report, so the new head run needs its own answer, and the dry-run tests that assert the exact request lines and indices.
- `read_spec` of `ci-fail-to-pass` showed the requirement `A failed test that the fix does not change refuses the replay`, whose name and text fit only the base, and the requirement `The replay reads no title, label or body`, whose text already says the command fails unless a changed test fails on base.
- `search_code` of `fail_to_pass_unchanged_failed` found 2 files: `src/devops_cli/ci/fail_to_pass.py` and `src/devops_cli/lang/en/messages.py`, both in group 1.
- The probe shows that the issue's `tools.lock` is no root path: `The path `tools.lock` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/tools_lock/tools.lock`, `tests/fixtures/research/repo/src/devops_cli/tools_lock/tools.lock`. No commit in the history deleted or renamed it.` The plan changes no pin and needs no such path.
- `Not probed, the bound of 10 commands is reached: `test_the_kubectl_and_helm_pins_hold_the_go_builds_that_fix_the_stdlib_findings`, `test_every_mcp_server_trivyignore_entry_has_a_reason_and_an_exp_date_that_is_not_past`, `_unsatisfied_reasons`, `pytest``: this run read `_unsatisfied_reasons` and the two test functions itself, and the two test functions are no part of the plan. The expiry dates of the ignore entries are `not checked` by this run, and the plan depends on no date.
- The GitHub state of #5584, #5585, #5573 and #5574 is `not checked` by this run, and the plan depends on none of them: the refusal is in the code and in the base spec. #5585 scopes the trigger and stays out of this change.
- The first check that the implementation runs against the real system is `uv run devops ci test tests/ci/test_fail_to_pass.py`, then `uv run devops ci fail-to-pass --base origin/main --dry-run` to read the planned head run, then `uv run devops openspec check` for the change folder.
- `run_fail_to_pass` (`src/devops_cli/ci/fail_to_pass.py:def run_fail_to_pass`) needs a checkout of the repository: it starts `git worktree`, `git archive` and pytest. `changed_tests` needs a checkout for `git merge-base` and `git diff`.
- The new `_head_tree` needs a checkout of the repository, because it adds and removes a detached worktree. `_run_pytest_replay` needs a checkout, because pytest runs in the tree that it is given; it needs no network, because the test harness doubles the process edges.
- `_run_gate_row` needs a checkout of the repository. `plan_fail_to_pass`, `_files_holding`, `_repaired_and_refused` and `format_fail_to_pass_report` need no checkout, no client and no network.
- The plan introduces no new program: `git` and `pytest` are runner tools of the image and `uv` starts the verify command, so no program is `NOT_IN_RUNNER`. The pod settings that apply are `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`; the head replay writes its JUnit report under the temporary directory that the base replay already writes, so it needs no new writable path.
- The needed failure classes are `test` (action `repair`) for a failing test, `lint` and `types` (action `repair`) for ruff and mypy, and `timeout` (action `retry`) for the second pytest run of a large replay.

## Existing Tool Considered

git worktree and pytest are open and maintained, and give the head tree and the JUnit outcomes; neither classifies an unchanged failure as a repair, so the change adds that classification to the in-repo check. Written cost: about 100k tokens to build, keep and fix the classification and its tests, over about 4 hours. It deletes `_run_gate_rows_on_head` and renames `_run_pytest_on_base`.

## Dependencies

None.
