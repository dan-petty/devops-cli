# Task: The Release Pull Request Skips the Fail-to-Pass Replay and Shows No Cancelled Check (#1972)

**Issue**: [#1972](https://github.com/dan-petty/devops-cli/issues/1972)
**Scope**: scope/ci
**Feasibility**: On 2026-10-23 the runs of the branch `release-please--branches--main--components--devops-cli` showed two `Fail-to-Pass Test Replay` runs for head `28075db1`, one successful and one cancelled (runs 40007817347 and 40007817412). release-please pushes, then edits and labels the pull request, and `fail-to-pass.yml` starts on `synchronize`, `edited` and `labeled` with one concurrency group per ref.

## Description

- [x] **Skip** (`.github/workflows/fail-to-pass.yml`): `Fail-to-Pass Check` and `Fail-to-Pass Self-Check` skip a `release-please--` branch. The release pull request changes only the changelog, the manifest and the version lines, so no test replays there.
- [x] **No cancelled runs**: each run of a `release-please--` branch gets its own concurrency group, so a skipped run never cancels another. Every other pull request keeps one group per ref, where a newer event cancels an older run.
- [x] **Test** (`tests/test_workflow_contracts.py`): `test_fail_to_pass_skips_the_release_pull_request_without_cancelled_runs` holds both job conditions and the concurrency group. It failed before the change.
