# Tasks

## 1. Carry a body in the item writes of the store

Kind: behavior

Reads: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `tests/support/fakes/roadmap_store.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`, `tests/support/fakes/roadmap_store.py`, `tests/roadmap/stores/test_roadmap_store_body_with_marks.py` (new).

- [x] 1.1 Write `tests/roadmap/stores/test_roadmap_store_body_with_marks.py`, and give the fake store the same `body` argument on `set_field` and `set_marks`, with a `write_issue_body` entry in `job_writes`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 1.2 Add the optional keyword `body` to `set_field` and `set_marks` of `RoadmapStore` and `GitHubRoadmapStore`, and let `_edit_issue` replace the text before the record block with it, so one `PATCH` carries the labels, the new body and the record block
  - Verification: `$ uv run devops ci test tests/roadmap/stores`

## 2. Write the result of a refined item with one request

Kind: behavior

Reads: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_refine_deferred.py`, `tests/roadmap/refine/test_roadmap_refine_gateway_failures.py`, `tests/roadmap/refine/test_roadmap_refine_round.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_refine_one_write.py` (new), `tests/roadmap/refine/test_roadmap_refine_deferred.py`, `tests/roadmap/refine/test_roadmap_refine_gateway_failures.py`, `tests/roadmap/refine/test_roadmap_refine_round.py`, `tests/roadmap/stage/test_roadmap_stage_item_writes.py`.

- [x] 2.1 Write `tests/roadmap/refine/test_roadmap_refine_one_write.py` (a stop after the first write, a Ready item, a Status that stays, a Ready item back to New), and move the refine tests that name the write of the body to the combined write
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 2.2 Write the body, the marks and the Status in `_apply_refined` with `set_field(..., body=r.new_body)` or `set_marks(..., body=r.new_body)`, and delete its call of `write_issue_body`
  - Verification: `$ uv run devops ci test tests/roadmap/refine`

## 3. Write a check of the alternatives job with one request

Kind: behavior

Reads: `src/devops_cli/roadmap/alternatives.py`, `tests/support/roadmap_alternatives.py`. Changes: `src/devops_cli/roadmap/alternatives.py`, `tests/roadmap/test_roadmap_alternatives_one_write.py` (new).

- [x] 3.1 Write `tests/roadmap/test_roadmap_alternatives_one_write.py` (a stop after the write, and the requests of one check)
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 3.2 Write the new body and the marks in `AlternativesWriter.settle` with one `set_marks(..., body=outcome.new_body)`, and delete its call of `write_issue_body`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_alternatives_one_write.py`

## 4. Plan one write in the dry run

Kind: behavior

Reads: `src/devops_cli/roadmap/request_plan.py`, `tests/roadmap/test_roadmap_dry_runs.py`. Changes: `src/devops_cli/roadmap/request_plan.py`, `tests/roadmap/test_roadmap_dry_runs.py`.

- [x] 4.1 Add the two `body_with_marks` tests to `tests/roadmap/test_roadmap_dry_runs.py`: the plan of a refine round and of `--item`, and the plan of a check
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 4.2 Delete the planned `write_issue_body` from the refine plans (round and `--item`) and from the alternatives plan, and keep it in the repair plan
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py`

## 5. Say that a result is one write

Kind: documents

Reads: `docs/roadmap/refine.md`, `docs/roadmap/alternatives.md`. Changes: `docs/roadmap/refine.md`, `docs/roadmap/alternatives.md`.

- [ ] 5.1 In `docs/roadmap/alternatives.md`, change the list of "What a check writes": the body block and the job record go in one request, and the comment follows as a separate request. In `docs/roadmap/refine.md`, say that refine writes the body, the marks and the Status of an item with one request, and the comment after it
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 2: `uv run pytest tests/roadmap/refine/test_roadmap_refine_one_write.py -k stop_after_first_write` - the only write of an item is one request. A stop after it leaves the new body, the new marks and the new Status together. The item is not a `WaitingItem(EDIT)`, and it is not a spurious stage return.
- Group 2: `uv run pytest tests/roadmap/refine/test_roadmap_refine_one_write.py -k no_status_change` - an item that keeps its Status is written with one request that holds the body and the marks.
- Group 3: `uv run pytest tests/roadmap/test_roadmap_alternatives_one_write.py -k stop_after_write` - a stop after the write leaves the new block and `checked_at` together.
- Group 4: `uv run pytest tests/roadmap/test_roadmap_dry_runs.py -k body_with_marks` - the dry-run plan lists one `PATCH` for the body with the marks.
- Group 1: `uv run pytest tests/roadmap/stores/test_roadmap_store_body_with_marks.py -k set_marks_body` - `set_marks` with `body` sends one `PATCH` with the new body and the record block.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
