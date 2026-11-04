# Tasks

## 1. Return a shell refusal as a tool result

Reads: `src/devops_cli/roadmap/implement_shell_refusal.py`, `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/roadmap/implement_step.py`, `tests/roadmap/test_roadmap_implement_shell_refusal.py`. Changes: `src/devops_cli/roadmap/implement_shell_refusal.py`, `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_shell_refusal.py`, `tests/roadmap/test_roadmap_implement_tool_log.py`.

- [x] 1.1 Add cases to `tests/roadmap/test_roadmap_implement_shell_refusal.py`: a refusal of the shell reaches the model as a `ToolReturnPart`, more refusals than `CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES` do not stop the run, a failed `read_file` still stops the run at the retry limit, the model gets `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS` refusals and the next call ends the run with the stop text, and the stop is in the class `refused_tool`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_shell_refusal.py` fails on the base
- [x] 1.2 Add `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS` to `src/devops_cli/config/constants.py` and the stop text to `src/devops_cli/lang/en/messages.py`. Replace `shell_refusal_hooks` and `argument_refusal_hooks` in `src/devops_cli/roadmap/implement_shell_refusal.py` with the capability `ShellRefusal`, which wraps the toolset and returns a refusal as text. Add `ToolCallLog.refuse` and the limit to `src/devops_cli/roadmap/implement_tool_log.py`, and use `ShellRefusal` in `build_agent` of `src/devops_cli/roadmap/implement_step.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_shell_refusal.py tests/roadmap/test_roadmap_implement_tool_log.py` passes
- [x] 1.3 Update the tests that counted a refusal as a retry: the stop at the sixth call in `tests/roadmap/test_roadmap_implement_step.py` and `tests/roadmap/test_roadmap_implement_shell_policy.py`, the log test of every outcome in `tests/roadmap/test_roadmap_implement_tool_log.py`, and the table of limits in `tests/roadmap/test_roadmap_limit_classes.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_implement_shell_policy.py tests/roadmap/test_roadmap_limit_classes.py` passes

## 2. State the rule in the workflow document

Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 2.1 In `docs/ROADMAP_WORKFLOW.md`, replace the sentence that each refusal counts against the retry limit of the tool with the rule that a refusal returns as a tool result, adds no tool retry, and counts against the limit of refusals of the step
  - Verification: `! git grep -n "Each refusal counts against the retry limit" docs/`
- [x] 2.2 Regenerate the documentation
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- The read pipe through a table of right-hand programs, and the table or digest for the first word that the log shows as `other`, go to #3520. A change to the rule on a free first word goes to the owner.
- Pending a person: edit #3041 as the evaluation of #3271 says: remove criterion 3 ("The refusal limit counts only calls that the catalog has no entry for") and add a `### Dependencies` heading that names #3271 above its refine block.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
