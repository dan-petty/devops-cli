# Tasks

## 1. Name both command registration forms in the stage prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [x] 1.1 Add a case to `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` that reads the stage prompt and asserts the two registration forms and the bare-name negative search
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` fails on the base
- [x] 1.2 Add the rule to `src/devops_cli/ai/tasks/roadmap_stage_change.md`: a command registers by `@app.command("name")` or by the function name under `@app.command()` or `@<group>.command()`, and a check for a command name is a negative search for the bare name, such as `! git grep -n <name> src/ tests/`, which finds both `@app.command("<name>")` and `def <name>(`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes

## Criteria

- Group 1: The stage prompt SHALL state that `@app.command("name")` registers the string literal and that `@app.command()` or `@<group>.command()` registers the function name.
- Group 1: The stage prompt SHALL state that `! git grep -n <name> src/ tests/` finds both `@app.command("<name>")` and `def <name>(`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
