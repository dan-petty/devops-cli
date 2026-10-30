# Tasks

## 1. The reason of a stop

- [ ] Write failing tests in `tests/test_roadmap_implement_step.py`: the existing stops on `UsageLimitExceeded` give a reason with the class and the message; a model that calls a refused program until the retry limit gives `UnexpectedModelBehavior` with its message and the count of refused commands; arguments that fail validation give the count of other retries; a token in the message is masked; a long message is cut and keeps the counts.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py`
- [ ] Add `src/devops_cli/roadmap/implement_tool_log.py` with `ToolCallLog` and its `Hooks`, add the constants `CONST_ROADMAP_IMPLEMENT_ERROR_CHARS`, `CONST_ROADMAP_IMPLEMENT_ERROR_READ_CHARS` and `CONST_ROADMAP_IMPLEMENT_PROGRAM_CHARS` to `src/devops_cli/config/constants.py`, add the reason texts to `src/devops_cli/lang/en/messages.py`, and build the reason in `src/devops_cli/roadmap/implement_step.py`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_step.py tests/test_roadmap_implement_job.py`

## 2. The log line of each tool call

- [ ] Write failing tests in `tests/test_roadmap_implement_tool_log.py`: one line for each tool call with the outcomes `ok`, `refused`, `retry` and `failed`; the first word of a shell command and no other argument; no file content and no refusal text; a masked first word; a cut first word; no line for a call that the model never made.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_tool_log.py`
- [ ] Write the line in `ToolCallLog` with `print_muted(..., to_stderr=True)`, and give `build_agent` the capability.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_tool_log.py tests/test_roadmap_implement_step.py`

## 3. The documentation

- [ ] Regenerate the documentation, and update the term "Stop reason" in `CONTEXT.md` if it names the class only.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 4. Archive

- [ ] Archive the change.
  - Verification: `uv run devops openspec archive 2758-implement-stop-cause`
