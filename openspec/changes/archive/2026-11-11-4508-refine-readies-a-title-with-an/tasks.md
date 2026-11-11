# Tasks

## 1. Behavior: retitle corrects an unlisted title type

- [x] 1.1 Write failing tests for `unlisted_type`, `corrected_title`, the retitle correction, the comment and log line of a skip, and the stage reason
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_retitle_type.py tests/roadmap/test_roadmap_commit_title.py tests/roadmap/stage/test_roadmap_stage_command.py`
- [x] 1.2 Add `unlisted_type` and `corrected_title`; select and correct the title in `retitle.py` (`retitle_items` replaces `long_title_items`); log each skip
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_retitle_type.py tests/roadmap/test_roadmap_retitle.py tests/roadmap/test_roadmap_retitle_skip.py tests/roadmap/test_roadmap_commit_title.py`
- [x] 1.3 Keep the correction table as `_TITLE_TYPE_CORRECTIONS` in `commit_title.py`, its one reader, and keep the early return of the intake summary check
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_retitle_type.py tests/roadmap/test_roadmap_retitle.py`
- [x] 1.4 Write failing tests, then build `unlisted_type_reason` for the reason of the stage job and the implement job; a title with no type keeps its reason
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_command.py tests/roadmap/stage/test_roadmap_stage_selection.py tests/roadmap/implement/test_roadmap_implement_planned.py`
- [x] 1.5 Write failing tests, then make the refine selection and `--item` leave an item with an unlisted type, with no model call
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_title_type.py`

## 2. Documents

- [x] 2.1 Regenerate the command reference and README, and update the retitle text of `CONTEXT.md` and the skip mark row of `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops ci docs`
- [x] 2.2 Update the selection, the correction and the skip log line in `docs/roadmap/intake.md`, the retitle sentence of `docs/roadmap/implement.md`, and the retitle docstrings of `src/devops_cli/roadmap/run.py`
  - Verification: `$ uv run devops ci docs`
- [x] 2.3 Describe the refine wait in `docs/roadmap/refine.md` and in the `--item` help, and the intake that keeps the candidate in `docs/roadmap/intake.md`
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
