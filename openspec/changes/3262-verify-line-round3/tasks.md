# Tasks

## 1. A text of the reply cannot add a section, a group or a command

Kind: behavior. Reads: `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`. Changes: `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_text_lines.py` (new), `tests/roadmap/test_roadmap_stage_task_verification.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_text_lines.py`, add the tests of the parser (a heading in a list item or a quote), of the criteria section (a criterion of the model and of the issue body), of every line terminator in each text, of `verify` with two spaces, of a text set after validation, of the two problems of one command, and of the headings of a rendered `spec.md`, `proposal.md` and `design.md`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_text_lines.py` fails on the base: 51 tests fail
- [x] 1.2 In `src/devops_cli/roadmap/step_files.py`, take a heading at the top level only. In `src/devops_cli/roadmap/stage_change.py`, fold the texts of the files, refuse a mark at the start of a line, join `verify` by line, validate an assignment, and write the criteria lines after a fixed word. In `src/devops_cli/roadmap/stage_form.py`, give every problem of a command. Update the texts of the criteria lines in `tests/roadmap/test_roadmap_stage_plan.py` and the backtick test in `tests/roadmap/test_roadmap_stage_task_verification.py`
  - Verification: `uv run devops ci test tests/roadmap` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
