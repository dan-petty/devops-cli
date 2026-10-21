# Task: Commit-status read fails closed when the runner raises and check_verdict stops swallowing StopIteration (#1350)

**Issue**: [#1350](https://github.com/dan-petty/devops-cli/issues/1350)
**Scope**: scope/github
**Feasibility**: Verified against `src/devops_cli/github/check_verdict.py`, `tests/test_pr_check_verdict.py`, and `tests/test_pr_cmd.py` on Python 3.14. Removing `try ... except StopIteration, IndexError` in `_fetch_commit_statuses_from_rest` aligns commit-status reading with check-runs reading so runner exceptions propagate instead of failing open.

## Description

Removes the `try ... except StopIteration, IndexError` shim from `_fetch_commit_statuses_from_rest` in `src/devops_cli/github/check_verdict.py`, scripts the `/status` response in the three fallback tests that previously relied on the swallowed `StopIteration`, and adds a regression test verifying that `fetch_pr_check_verdicts` propagates runner exceptions instead of returning a passing verdict.

## Deliverables

- [x] Remove `try ... except StopIteration, IndexError` around `runner(status_cmd, check=False, quiet=True)` in `_fetch_commit_statuses_from_rest` (`src/devops_cli/github/check_verdict.py`).
- [x] Script `/status` responses and assert on returned commit statuses in `test_fetch_pr_check_verdicts_rest_fallback_on_cli_failure`, `test_rest_pagination_bucket_count_matches_total_count` (`tests/test_pr_check_verdict.py`), and `TestPrCommands::test_pr_checks_fallback_on_gh_failure` (`tests/test_pr_cmd.py`).
- [x] Add `test_commit_status_read_raising_propagates_and_never_passes` in `tests/test_pr_check_verdict.py`.
- [x] Add `changelog.d/1350.md` under `### Fixed`.
