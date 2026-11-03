# Tasks

## 1. Refuse a living-spec path in a task group

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_paths.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_paths.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_paths.py`, add a case that builds a `StageGroup` whose `changes` and `creates` hold `openspec/specs/config-commands/spec.md` and expects `ValidationError` naming that path, and a case whose `changes` hold `src/devops_cli/sample.py` and whose `reads` hold `openspec/specs/config-commands/spec.md` and expects success
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` fails on the base
- [ ] 1.2 Add the constant `openspec/specs/` to `src/devops_cli/roadmap/stage_change.py` and a `StageGroup` model validator `_no_living_spec` that raises `ValueError` with `MESSAGES.roadmap.stage_bad_living_spec` for each path in `changes` and `creates` that starts with the prefix. Add the message `stage_bad_living_spec` to `src/devops_cli/lang/en/messages.py`, with the path and the words that only `openspec archive` writes living specs
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` passes

## 2. State the living-spec rule in the stage prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 2.1 In `tests/roadmap/test_roadmap_stage_prompt_rules.py`, add a case that reads `src/devops_cli/ai/tasks/roadmap_stage_change.md` and asserts that its text says a task group must not change or create a file under `openspec/specs/` and that `openspec archive` writes living specs
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` fails on the base
- [ ] 2.2 Add the rule to the section of `src/devops_cli/ai/tasks/roadmap_stage_change.md` that describes `changes` and `creates`: a task group never names a path under `openspec/specs/`, in `changes` or in `creates`, because `openspec archive` writes living specs from the spec deltas of the change folder
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
