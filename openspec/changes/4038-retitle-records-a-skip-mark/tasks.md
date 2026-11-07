# Tasks

## 1. Record and honor the skip mark

Reads: `src/devops_cli/roadmap/retitle.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/body_hash.py`, `tests/roadmap/test_roadmap_retitle.py`, `tests/support/fakes/roadmap_store.py`. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/retitle.py`, `tests/roadmap/test_roadmap_retitle_skip.py` (new).

- [ ] 1.1 Add `tests/roadmap/test_roadmap_retitle_skip.py` for the mark, the return of an item whose title, body or `stage.pr` changes, and the counts of writes, reads and model requests in the next round. Run it and see it fail
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main` shows the new tests fail on the base
- [ ] 1.2 In `store.py`, add `RetitleRecordKey` with `SKIPPED = "retitle.skipped"`, add it to the `JobRecord` union, to `_JOB_RECORD_KEYS` and to `__all__`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_retitle_skip.py`
- [ ] 1.3 In `retitle.py`, add `skip_hash(item)`, the `hash_text` of the title, the body and the `stage.pr` mark. Make `long_title_items` leave out an item whose `retitle.skipped` equals it. Make `apply_retitle` write `{RetitleRecordKey.SKIPPED: skip_hash(item)}` with one `store.set_marks` call for each `TitleSkip`. Update the module document of `retitle.py` for the mark
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_retitle_skip.py tests/roadmap/test_roadmap_retitle.py`

## 2. List the write of the mark in the dry run

Reads: `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`.

- [ ] 2.1 In `retitle_requests`, add the `PATCH` of the body with the record (`StoreRequests.set_marks`) under a new condition text in `plan_conditions`, and update its docstring. The test `test_request_count_the_dry_run_plan_lists_the_write_of_the_mark` of group 1 is the failing test
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_retitle_skip.py tests/roadmap/test_roadmap_dry_runs.py`

## 3. Documents

Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [ ] 3.1 Add a Retitle row for `retitle.skipped` to the table of record keys in `docs/ROADMAP_WORKFLOW.md`: the hash of the title, the body and the `stage.pr` mark, and the rule that the job selects the item again when the hash changes
  - Verification: `$ uv run devops ci docs`
- [ ] 3.2 Run `uv run devops docs generate --sync-readme` and commit the generated documents if the message change alters them
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
