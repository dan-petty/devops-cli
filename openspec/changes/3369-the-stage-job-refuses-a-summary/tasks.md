# Tasks

## 1. Refuse an overlong title summary in the stage title check

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_title.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_title.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_title.py`, a Ready item whose title is `fix(roadmap): ` and a summary of 61 UTF-16 units is left out with a reason that names 61 and 60, and a Ready item with a summary of 60 UTF-16 units is not refused for its summary length
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py` fails on the base
- [ ] 1.2 In `_Judge._title` in `src/devops_cli/roadmap/stage.py`, after the type check and before the slug check, compare `summary_length(summary)` with `SUMMARY_MAX_CHARS` imported from `src/devops_cli/roadmap/pull_form.py`. Return the new message `stage_left_title_long` with the current length and the limit. Add that message to `src/devops_cli/lang/en/messages.py` beside `stage_title_long`. Add the two cases to `tests/roadmap/test_roadmap_stage_title.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py` passes

## 2. Keep the cut of an overlong delivery title

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/pull_form.py`, `tests/roadmap/test_roadmap_stage_title.py`. Changes: `tests/roadmap/test_roadmap_stage_title.py`.

- [ ] 2.1 Keep the cut in `delivery_title` in `src/devops_cli/roadmap/stage_change.py` as it is. In `tests/roadmap/test_roadmap_stage_title.py`, hold that `delivery_title` of an issue title whose summary is longer than `SUMMARY_MAX_CHARS` returns the first 60 UTF-16 code units and then `...`, so the fallback stays tested
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py` passes

## Criteria

- Group 1: The stage job SHALL refuse an item whose issue title has a valid Conventional Commit type and a summary longer than `SUMMARY_MAX_CHARS` UTF-16 code units, as `summary_length` counts them.
- Group 1: The stage job SHALL accept an item whose issue title has a valid Conventional Commit type and a summary of exactly `SUMMARY_MAX_CHARS` UTF-16 code units.
- Group 2: The implement job SHALL keep the cut in `delivery_title` for an item whose issue title summary is longer than `SUMMARY_MAX_CHARS`, so an old staged item still gets a delivery title.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
