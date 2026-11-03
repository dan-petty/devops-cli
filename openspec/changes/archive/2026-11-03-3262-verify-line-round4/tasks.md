# Tasks

## 1. The split reply, U+FEFF and the HTML marks

Kind: behavior. Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/step_files.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_text_lines.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_kind.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_text_lines.py`, `tests/roadmap/test_roadmap_stage_plan.py` and `tests/roadmap/test_roadmap_stage_kind.py`, add the tests of a split group with a wrong `verify`, of U+FEFF in each text, of the marks `~~~`, `___`, `##` and an HTML tag, of `section_text` with a nested heading, of the prompt sentence, and the ratchet over the text fields
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_text_lines.py tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_stage_kind.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage.py`, check the form of the groups of a split reply. In `src/devops_cli/roadmap/stage_change.py`, fold U+FEFF and refuse an HTML tag. In `src/devops_cli/roadmap/step_files.py`, take a heading of `section_text` at the top level only. In `src/devops_cli/ai/tasks/roadmap_stage_change.md`, state the rule for the line-start texts
  - Verification: `uv run devops ci test tests/roadmap` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
