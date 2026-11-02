# Tasks

## 1. Hold the planner prompt to its sources

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_form.py`, `docs/TESTING.md`, `openspec/config.yaml`. Changes: `tests/roadmap/test_roadmap_stage_prompt_rules.py` (new), `src/devops_cli/ai/tasks/roadmap_stage_change.md`.

- [x] 1.1 Write `tests/roadmap/test_roadmap_stage_prompt_rules.py`, which reads the keys, the limits, the closing words, the no-spec paths, the forms and the commands of `verify`, and the shared phrases of the prompt and compares each with its source, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
- [x] 1.2 Name `closed`, `fixed` and `resolved` in the closing words of `src/devops_cli/ai/tasks/roadmap_stage_change.md`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
