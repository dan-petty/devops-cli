# Tasks

## 1. Stop the step on consecutive refusals

Reads: `src/devops_cli/roadmap/implement/implement_tool_log.py`, `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py`. Changes: `src/devops_cli/roadmap/implement/implement_tool_log.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 1.1 Write the failing tests: 3 refusals in a row end the run with class `refused_tool`; refusals split by an accepted call do not; alternating calls reach the total limit; the constant is 3
  - Verification: `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_refusal.py` fails on the base
- [x] 1.2 Add the constant, the message and the counter in `ToolCallLog`
  - Verification: `uv run devops ci test tests/roadmap/implement tests/roadmap/test_roadmap_limit_classes.py` passes
- [x] 1.3 Change the tests that looped on one refused command to alternate it with an accepted call when they prove the total limit

## 2. Documents

- [x] 2.1 State the rule in `docs/ROADMAP_WORKFLOW.md` and regenerate the documents
  - Verification: `uv run devops ci docs` passes
