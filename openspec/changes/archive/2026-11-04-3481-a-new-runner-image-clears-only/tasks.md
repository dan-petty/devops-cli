# Tasks

## 1. Record the digest clears of an item

Reads: `src/devops_cli/roadmap/store.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`. Changes: `src/devops_cli/roadmap/digest_clears.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/test_roadmap_digest_clears.py`.

- [x] 1.1 Add `tests/roadmap/test_roadmap_digest_clears.py`: a list of entries survives encode and read, a record that is not valid raises, an item with no record has no clears and no comment time, and the settings `digest_clears_per_class` and `digest_clears_per_item` default to 1 and 3
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_digest_clears.py` fails on the base
- [x] 1.2 Add the keys `implement.digest_clears` and `implement.digest_clear_commented_at` to `ImplementRecordKey`, the module `digest_clears.py` (the entry model, read, encode, the comment time) and the two settings with their defaults
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_digest_clears.py` passes

## 2. Clear by digest only a stop that a retry can fix

Reads: `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stop_clear.py`. Changes: `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stop_clear.py`.

- [x] 2.1 Add cases to `tests/roadmap/test_roadmap_stop_clear.py`: a new digest alone does not clear a stop of class `plan_defect`, `refused_tool`, `premise_false` or `test`, and does not clear a stop with no class, `implement: retry` still clears these, a stop of class `provider`, `timeout` or `ci_infra` clears and records its entry, the class limit and the item limit hold a stop (also for `ci_infra`) until `implement: retry`, a clear writes at most one comment in 24 hours and still records the entry, a record that does not parse stops the digest clear, and the rule reads no template for a class that it does not clear
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stop_clear.py` fails on the base
- [x] 2.2 Change `stop_clear.py`: gate rule `digest` on the action `retry` of `ACTION_BY_CLASS`, count the entries of `implement.digest_clears` against the two limits, record the entry with the clear, cap the comment with `implement.digest_clear_commented_at`, and remove the text `Never a loop`. `clear_stops` reads the limits from the settings when the caller passes none. Change the digest comment in `messages.py` to state the class and the limits
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stop_clear.py` passes
- [x] 2.3 No rule reads image content, and the docstring no longer says `Never a loop`
  - Verification: `! git grep -n "Never a loop" src/devops_cli/roadmap/stop_clear.py`

## 3. Take a new item before a retried item of the same priority

Reads: `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_selection.py`. Changes: `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_selection.py`.

- [x] 3.1 Add cases to `tests/roadmap/test_roadmap_stage_selection.py`: inside one priority an item with no digest clear goes before an item with one, an item with a digest clear and a higher priority goes before an item with none and a lower priority, and equal items go by number
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py` fails on the base
- [x] 3.2 Change `priority_order` to return the rank, then whether `implement.digest_clears` is set, then the number
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_selection.py` passes

## 4. State the rule in the documents

Reads: `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/ROUTINE_TASKS.md`. Changes: `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/ROUTINE_TASKS.md`, `docs/roadmap/implement.md`, `CONTEXT.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`.

- [x] 4.1 State in step 16 of `k8s/README.md`, in `docs/ROADMAP_WORKFLOW.md` (the state table, the record table and the stop and retry path) and in `docs/ROUTINE_TASKS.md`, `docs/roadmap/implement.md` and `CONTEXT.md` that only a stop of a class with the action `retry` clears by digest, the two limits, the comment cap and the order inside a priority. Run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
