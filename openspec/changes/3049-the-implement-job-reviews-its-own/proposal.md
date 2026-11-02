# Proposal

## Why

The implement job marks a pull request ready with no review of the diff against the issue, the plan and the project rules, and the review tools the project already has are unused by the job (#3049).

## What Changes

- Add `src/devops_cli/roadmap/implement_review.py` with the review run, the plan-conformance check and the disposition of each finding.
- Gate `_ready` in `src/devops_cli/roadmap/implement_run.py` on both the checks and the review.
- Add the `roadmap.implement.review_runs` setting and enforce it as the review call budget per item.
- Post every finding and its disposition in the implement comment.
- Add the review step names and messages.
- Add a replay test with a seeded high-severity finding, and tests for the budget and the ready gate.
- Add the `roadmap-implement-review` capability spec delta and update the implement job docs.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-implement-review`: Review runs before the ready mark, A surviving high-severity finding blocks the ready mark, The comment lists every finding with its disposition, The review call budget is stated and enforced, The ready mark waits for the checks and the review

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/implement_review.py`, `src/devops_cli/roadmap/implement_run.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `CONTEXT.md`
- Tests: `tests/roadmap/test_implement_review.py`

## Feasibility

- `read_file` on `src/devops_cli/roadmap/implement_run.py` lines 642-699 showed `_checks` raising `_StopError` unless the watch is READY, then `_ready` calling `mark_ready` at once: the review has no place between them today.
- `file_symbols` on `src/devops_cli/roadmap/implement_pull.py` showed `mark_ready(repo, pull)`, `watch_pull(repo, pull, head)` and `failed_log(repo, check)` as the pull-request seams the job already uses.
- `search_code` for `ready_to_mark` showed `src/devops_cli/roadmap/stage_ready.py` as the single decision function of the stage-ready row, so the review result plugs into an existing seam.
- `read_file` on `src/devops_cli/roadmap/implement_run.py` lines 505-520 showed `repair_rounds` bounding the scoped and check repairs: the review budget follows the same shape.
- First checks against the real system: `uv run devops review --help` shows the command's options and its exit codes; `uv run devops roadmap implement --plan` shows the planned steps of an item; `uv run devops ci test tests/roadmap/test_implement_review.py` runs the new replay test.

## Existing Tool Considered

`devops review` (ADR 0005) already produces the findings from pinned tools, advisories, confirmed version facts and the rule pack, and `src/devops_cli/roadmap/stage_ready.py` already holds the one decision function for the ready mark. The change wires both into the implement job and builds no scanner and no review engine of its own; the plan-conformance check reads the change folder and is a few dozen lines. Building a review engine would cost the pinned tools, a sandbox, a canary per language and the rule pack, weeks of work and a permanent maintenance load, and ADR 0005 rejected exactly that.
