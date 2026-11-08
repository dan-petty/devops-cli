# Tasks

## 1. Compute the golden-set replay once in the eval gate test module

Reads: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`. Changes: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

- [ ] 1.1 In `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, add a module-level list of cases from `load_cases` and a module-scoped report fixture that calls `replay_all` on the whole list once. Change the six report tests to read the fixture's report, keep the registry-count test, and add one parametrized test per case that reads that case's replay from the shared report. Add a shape test that the whole-set `replay_all` call sits in the module-scoped fixture and that the parametrize mark holds the loaded cases; build the searched text from parts so the shape test does not count itself
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes

## 2. State in the prompt that a shell call returns when its command ends

Reads: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/implement/test_roadmap_implement_prompt.py`, `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/implement/test_roadmap_implement_prompt.py`.

- [ ] 2.1 In `tests/roadmap/implement/test_roadmap_implement_prompt.py`, write `test_the_prompt_says_a_shell_call_returns_when_its_command_ends` for `src/devops_cli/ai/tasks/roadmap_implement_step.md`; it fails because the prompt holds no such rule
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_prompt.py` fails on the base
- [ ] 2.2 In `tests/roadmap/implement/test_roadmap_implement_prompt.py`, write the failing test first: it reads the prompt and asserts the sentence that a shell call returns when its command ends, and that the prompt names `sleep`, `time.sleep` and a repeated `tail` as forbidden. In `src/devops_cli/ai/tasks/roadmap_implement_step.md`, add that rule to the runner rules of the prompt, beside the paragraph that gives the shell
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_prompt.py` passes

## 3. Record the replay rule in the testing document

Reads: `docs/TESTING.md`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`. Changes: `docs/TESTING.md`.

- [ ] 3.1 In `docs/TESTING.md`, add a bullet to the section that holds the worker choice: a test module that replays a shared set computes the replay once in a module-scoped fixture and gives each case its own parametrized item, so a narrowed run stays inside the budget and xdist can distribute the cases
  - Verification: `$ uv run devops ci docs` passes
- [ ] 3.2 In `docs/TESTING.md`, add the replay rule to the section that holds the worker choice
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
