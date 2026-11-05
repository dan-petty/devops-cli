# Tasks

## 1. A stage return and a named cause end a wait (behavior)

- [x] 1.1 Write the failing tests: a stage return gives one new look, the model reads its evidence, a second return on the same body waits on a person, a person set back still waits, a closed issue or a changed file that the wait text names gives a new look, a round gives no more new looks than its limit, and the check of a text is bounded.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine.py`
- [x] 1.2 Add the record key, the constant, the rules in `_still_waiting`, the request key `stage_return` and its prompt text.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine.py`

## 2. A refine wait is visible (behavior)

- [x] 2.1 Write the failing tests for the `Refine job` line of `explain` and the refine lines of the inbox.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_inbox.py`
- [x] 2.2 Add `refine_left_out`, the verdict, the inbox kind and the planned reads of the dry runs.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_inbox.py tests/roadmap/test_roadmap_dry_runs.py`

## 3. Documents (documents)

- [x] 3.1 Update the refine, inbox and workflow pages, and regenerate the command reference with `devops docs generate --sync-readme`.
  Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: merge this pull request after the repair pass of #3478. The new look would otherwise run the model that writes stubs on the returned items.
- Pending a person: after #3478 merges, run `devops roadmap refine --item <number> --confirm` on 20 of the waits recorded before the model, and compare the share that reach Ready or a real question.
