# Proposal

## Why

`devops roadmap retitle` records no mark for an item that it leaves (#4038). `long_title_items` selects every open item with a long title summary, the lowest number first, and `plan_retitle` takes the first 25. An item that the job cannot shorten is taken again in every round, which runs every 61 minutes. Each round reads the comments and the title changes of the item, and for an item that is not Planned it makes up to 2 model calls. These items hold the places of items with higher numbers. #3630 found 34 Ready items that the title rule left out, so this row blocks the stage job.

The job leaves an item for one of three reasons: a person changed the title, the plan pull request has no usable title, or the model gave no summary that passes the title form in two tries.

## What Changes

- Add the record key family `RetitleRecordKey` with the key `retitle.skipped` to `src/devops_cli/roadmap/stores/store.py`. Add it to the `JobRecord` union, to the parsed families `_JOB_RECORD_KEYS` and to `__all__`.
- Add `skip_hash(item)` to `src/devops_cli/roadmap/retitle.py`. It is the SHA-256 hash (`hash_text` of `body_hash.py`) of the title, the body and the `stage.pr` mark of the item.
- Make `long_title_items` leave out an item whose `retitle.skipped` equals `skip_hash(item)`. The item returns to the selection when its title, its body or its plan pull request changes.
- Make `apply_retitle` write the mark once for each `TitleSkip`, with one `set_marks` call. This covers all three reasons, a person's edit included. A model call that cannot reach the gateway raises before the apply step, so it records no mark.
- Add the write of the mark to `retitle_requests` in `src/devops_cli/roadmap/request_plan.py`, with its condition text in `src/devops_cli/lang/`, so that the dry run lists it.
- Add the key family to the table of record keys in `docs/ROADMAP_WORKFLOW.md`.
- The mark is a hash only. It has no link to the failure class table.
- The change alters the output of `devops roadmap retitle --dry-run` and the selection of the job, which a consumer observes, so it carries a spec delta (`roadmap-retitle`) and `skip_specs` is false.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-retitle`: Skip mark, Skipped item returns when its inputs change, Cost of a skipped item

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/retitle.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_retitle_skip.py` (new)

## Feasibility

- Read at origin/main, in the worktree: `retitle.py` has `long_title_items`, which takes every open item with a long summary, and `plan_retitle`, which takes the first `DEFAULT_ROADMAP_RETITLE_LIMIT` (25) of them. `_decide` reads `comments_on` and `last_renamed_at` for each of them, and `_model_title` makes up to `_ATTEMPTS` (2) model calls. A `TitleSkip` is only reported, and commented when `comment=True`. Nothing records it, so the premise of the issue holds.
- `stores/store.py` lists `ItemField | RefineRecordKey | AlternativesRecordKey | StageRecordKey | ImplementRecordKey` in `JobRecord`, and the same families in `_JOB_RECORD_KEYS`. No `RetitleRecordKey` exists.
- `RoadmapStore.set_marks(item, marks)` writes marks in one call and changes no field. `open_items()` returns each item with its `job_record` and its `body` with the record block taken out, so the check needs no extra read and the write of the mark does not change the body.
- `body_hash.hash_text` gives the SHA-256 hash, so no new library is needed.
- No merged or open pull request and no newer issue or ADR supersedes the item: #3535, #3630 and #3811 added the row and the schedule only, and no open pull request touches `retitle.py`.
- Check of the new tests against the real code: `uv run devops ci test tests/roadmap/test_roadmap_retitle_skip.py` fails on the unchanged selection (15 of 17 tests fail on the call; the 2 that pass are controls that hold with no mark). `uv run devops ci fail-to-pass --base origin/main` is the proof for the pull request.
- Risks settled in `design.md`: the hash covers the whole body, a model failure is recorded as a skip, and the key family lands before the failure-class issues of #3027.

## Existing Tool Considered

The record marks of the item job record and `hash_text` of `body_hash.py` cover the need: the job record is the open, in-repository store for per-item state, and refine, alternatives and stage use it the same way. No library is needed. The change builds one small function (`skip_hash`) and one key family. Cost: about 35k tokens and 2 h to build, about 2k tokens per quarter to keep, and about 8k tokens and 0.5 h to fix. The change deletes no internal code.

## Dependencies

None.
