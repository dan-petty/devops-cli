# Tasks

## 1. Render the task prompts through Jinja2

Reads: `src/devops_cli/ai/task_loader.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/roadmap/stage/stage_plan_record.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`. Changes: `src/devops_cli/ai/task_loader.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/roadmap/stage/stage_plan_record.py`, `tests/ai/test_ai_task_loader.py`, `tests/roadmap/implement/`.

- [x] 1.1 Add cases to `tests/ai/test_ai_task_loader.py`: a prompt renders a context value, a missing value raises, a prompt with no context keeps its text and its markers, the implement prompt gets its three tables and equals today's `str.replace` output, the source holds no `fill_prompt`, and the prompt version covers the context
  - Verification: `$ uv run devops ci test tests/ai/test_ai_task_loader.py` fails on the base
- [x] 1.2 Add the cached environment and the `**context` rendering to `load_task_prompt`, add `step_instructions` and remove `fill_prompt` and the three placeholders, and hash the context in `prompt_version`
  - Verification: `$ uv run devops ci test tests/ai/test_ai_task_loader.py` passes
- [x] 1.3 Move the implement tests to `step_instructions`
  - Verification: `$ uv run devops ci test tests/roadmap/implement tests/roadmap/stage` passes

## Criteria

- Group 1: `load_task_prompt` SHALL render a task prompt through one cached Jinja2 `SandboxedEnvironment` when the caller passes a context.
- Group 1: The environment MUST raise `jinja2.UndefinedError` when a prompt names a value that the context does not hold.
- Group 1: A prompt with no context MUST return the stripped file text with its markers.
- Group 1: The implement step prompt SHALL get its three tables through context, and MUST equal the output of today's filling.
- Group 1: The source MUST NOT hold `fill_prompt` or `PROGRAMS_PLACEHOLDER`.
- Group 1: `stage_plan_record.prompt_version` SHALL hash the raw templates and the context values.
- Group 1: The change MUST NOT add a template dependency, and Jinja2 stays at 3.1.6.

## Workflow follow-up

- The project facts of `stage_change`, `stage_split`, `stage_tools_research` and `alternatives` are a follow-up issue (#5638).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
