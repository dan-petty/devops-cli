# Proposal

## Why

Refine and the alternatives check write the result of one item with two requests, and a stop between them leaves a state that the next round reads wrongly (#4049).

- Refine calls `write_issue_body`, then `set_field` or `set_marks`. A stop after the body leaves the new body with the old marks. The next round reads the new body as a person's edit (`WaitingItem(EDIT)`) and refines the item again, with model spend.
- The alternatives check calls `write_issue_body`, then `set_marks`, then `comment`. A stop after the body leaves a new block and no `checked_at`. The item looks unchecked and is checked again.

A fix that writes the body and the marks in one request and the Status in a second request only moves the window: a stop between them leaves `refine.next_step=ready` on an item whose Status is New. The body, the marks and the Status of one result must go in one request.

## What Changes

- Add an optional argument `body` to `set_field` and `set_marks` of `RoadmapStore` and of `GitHubRoadmapStore`. When it is given, the one `PATCH` of the issue carries the labels (for `set_field`) and `with_record(body, encode_job_record(held, changes))`. The private `_edit_issue` takes the same text. `write_issue_body` stays for `repair.py`, which has no marks.
- `_apply_refined` of refine writes the body in the same call as the Status and the marks, in all three paths: Ready, Ready back to New, and a Status that stays. It no longer calls `write_issue_body`.
- `AlternativesWriter.settle` writes the new body and the marks with one `set_marks(..., body=...)`. The comment stays a separate request after the write.
- The dry-run plan (`request_plan.py`) drops the separate write of the body in the plans of refine and of alternatives. The request count of the normal path falls by two for each refined item and each check: one read and one `PATCH`.
- The race guards stay: `_outside_unchanged_since_read` before the write in refine, `_unchanged_since_read` in the alternatives writer, and `require_unchanged` in `set_field`.
- The fake store `tests/support/fakes/roadmap_store.py` takes the same argument, so the tests that use it carry the body with the marks.
- The change carries a spec delta: the requests of a job against GitHub, and its dry-run plan, are observable. It adds one requirement to `roadmap-refine` and one to `roadmap-alternatives`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: Refine writes the body, the marks and the Status of one item with one request.
- `roadmap-alternatives`: A check writes its block and its marks with one request.

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/request_plan.py`
- Documents: `docs/roadmap/refine.md`, `docs/roadmap/alternatives.md`
- Tests: `tests/roadmap/refine/test_roadmap_refine_one_write.py` (new), `tests/roadmap/test_roadmap_alternatives_one_write.py` (new), `tests/roadmap/stores/test_roadmap_store_body_with_marks.py` (new), `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/refine/test_roadmap_refine_deferred.py`, `tests/roadmap/refine/test_roadmap_refine_gateway_failures.py`, `tests/roadmap/refine/test_roadmap_refine_round.py`, `tests/roadmap/stage/test_roadmap_stage_item_writes.py`, `tests/support/fakes/roadmap_store.py`
- Settings: none. The change adds, removes, renames and tightens no setting, and it does not touch `k8s/devops/configmap.example.yaml` or the live ConfigMap, so it needs no test that loads the example ConfigMap into `Settings`.

## Feasibility

Checked on 2026-11-08 at origin/main `4f3c45cd`, by reading the code and by running the new tests on the base and on a scratch implementation.

- `GitHubRoadmapStore.set_field` already sends the labels and the body with the record block in one `PATCH` through `_edit_issue`, so GitHub accepts a combined edit of labels and body today. `_edit_issue` builds the body from `issue.split()` and the record from `encode_job_record(held, changes)`. A new `body` replaces only the first part. The change adds no API behavior.
- The defect is real on the base. The new test `test_a_stop_after_first_write_leaves_the_body_the_marks_and_the_status_together` stops the second write of a refine round: the item holds the new body, Status New and no marks, and the next plan lists `NextStep.EDIT` for it. The new test `test_a_stop_after_write_leaves_the_block_and_checked_at_together` leaves the block with no `checked_at`, and the next selection takes the item again. The run `uv run devops ci fail-to-pass --base origin/main` lists 13 tests that fail on the base, among them the tests of the five acceptance criteria; the fail is the missing `body` argument, the extra `write_issue_body` request, or the item that the next round reads as a person's edit.
- A scratch implementation of the five edits above made the 63 tests of the four new or changed test files pass, and the 793 tests of `tests/roadmap/refine`, `tests/roadmap/stores`, `tests/roadmap/test_roadmap_alternatives.py` and `tests/roadmap/stage/test_roadmap_stage_item_writes.py` pass. The scratch code was not kept in this commit.
- The set that the change covers is every caller that writes a body and then marks: `src/devops_cli/roadmap/refine/refine.py` (`_apply_refined`) and `src/devops_cli/roadmap/alternatives.py` (`AlternativesWriter.settle`). `git grep -n write_issue_body src/` finds these two and `repair.py:198`, which writes no marks and keeps `write_issue_body`. The dry-run plan lists the same writes at three places in `request_plan.py`: the round and the single item of refine, and the check of alternatives; the repair plan keeps its body write.
- The issue names `apply_alternatives`, which no longer exists: #4034 moved the writes to `AlternativesWriter.settle`.

## Existing Tool Considered

`with_record` and `encode_job_record` of the store already build the body with the record block, and `set_field` already sends labels and body in one `PATCH`. No library is needed, and the change adds no dependency. The change adds one optional argument to two store methods and deletes the second request of each path, so it costs about 60k tokens and 3 hours to write, about 2k tokens a quarter to keep, and about 12k tokens and 1 hour to fix if a call site is missed. The change deletes two calls of `write_issue_body` and three planned writes in `request_plan.py`.
