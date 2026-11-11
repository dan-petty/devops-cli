# Tasks

## 1. Behavior: retitle corrects an unlisted title type

- [x] 1.1 Write failing tests for `unlisted_type`, `corrected_title`, the retitle correction, the comment and log line of a skip, the intake refusal and the stage reason
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_retitle_type.py tests/roadmap/test_roadmap_commit_title.py tests/roadmap/stage/test_roadmap_stage_command.py`
- [x] 1.2 Add `CONST_ROADMAP_TITLE_TYPE_CORRECTIONS`, `unlisted_type` and `corrected_title`; select and correct the title in `retitle.py` (`retitle_items` replaces `long_title_items`); log each skip; refuse the type in `NewCandidate.refuse_title` (it replaces `refuse_long_summary`); name the retitle job in the stage reason
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_retitle_type.py tests/roadmap/test_roadmap_retitle.py tests/roadmap/test_roadmap_retitle_skip.py tests/roadmap/test_roadmap_commit_title.py tests/roadmap/stage/test_roadmap_stage_command.py`

## 2. Documents

- [x] 2.1 Regenerate the command reference and README, and update the retitle text of `CONTEXT.md` and the skip mark row of `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops ci docs`
- [x] 2.2 Update the intake refusal, the selection, the correction and the skip log line in `docs/roadmap/intake.md`, the retitle sentence of `docs/roadmap/implement.md`, and the retitle docstrings of `src/devops_cli/roadmap/run.py`
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
