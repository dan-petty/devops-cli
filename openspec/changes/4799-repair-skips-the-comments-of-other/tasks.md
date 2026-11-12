# Tasks

## 1. The repair pass reads past the comments of other jobs
kind: behavior

- [x] 1.1 Write failing tests: an alternatives, intake reason or retitle comment after the refine question or the stage return is no reply; a person reply before such a comment keeps the item; a confirm clears such a stub block; the census texts are stubs and placeholders, and three real texts with the same words are not
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_repair.py tests/roadmap/test_roadmap_pull_form.py`
- [x] 1.2 Read the newest comment of the job with `replies_after_marker` and `CONST_ROADMAP_JOB_COMMENT_MARKERS` in `src/devops_cli/roadmap/repair.py`, and add the census texts to `_PLACEHOLDERS` of `src/devops_cli/roadmap/pull_form.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_repair.py tests/roadmap/test_roadmap_pull_form.py tests/roadmap/test_roadmap_repair_command.py tests/roadmap/refine/test_roadmap_refine_placeholder.py tests/roadmap/stage/test_roadmap_stage_verify.py`

## 2. Documents
kind: documents

- [x] 2.1 State the comment rule and a census text in `docs/roadmap/repair.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- After the merge, an agent runs `uv run devops roadmap repair --confirm` on dan-petty/devops-cli. The preview of 2026-11-12 lists 14 items.
