# Tasks

## 1. Put the scratch rule in the implement prompt

Reads: `src/devops_cli/ai/tasks/roadmap_implement_step.md`. Changes: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `tests/roadmap/test_roadmap_implement_prompt.py` (new).

- [x] 1.1 Add `tests/roadmap/test_roadmap_implement_prompt.py`, which fails while the prompt lacks the rule, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_prompt.py` fails on the base
- [x] 1.2 Add the rule to the prompt, and verify that `uv run devops ci test tests/roadmap/test_roadmap_implement_prompt.py tests/roadmap/test_roadmap_implement_shell_refusal.py` passes
