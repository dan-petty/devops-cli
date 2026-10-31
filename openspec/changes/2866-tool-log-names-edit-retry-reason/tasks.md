# Tasks

## 1. The line of a retried call names the reason

- [x] Write the failing tests in `tests/roadmap/test_roadmap_implement_tool_log.py`: an `edit_file` call whose `old_text` is missing shows its reason and no part of `old_text`; a retry without a path in its message shows `Path: <path>`; a secret in a reason is masked; a plain string as `path` is hidden unless the checkout holds it; a long reason without the path still ends with the path; a long reason is cut to `CONST_ROADMAP_IMPLEMENT_LOG_REASON_CHARS`; a refusal by policy and a failed validation show no reason.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_tool_log.py`
- [x] Change `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/lang/en/messages.py` and `src/devops_cli/config/constants.py`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_tool_log.py tests/roadmap/test_roadmap_implement_step.py`

## 2. The reason of a stopped run names the last reasons

- [x] Write the failing tests in `tests/roadmap/test_roadmap_implement_step.py`: a step whose `edit_file` misses its `old_text` in every reply ends with the line of the last reasons; a run that ends on a limit has no such line; the reasons hold no secret.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py`
- [x] Keep the last reasons of each tool in `ToolCallLog` and add the line in `_with_counts` of `src/devops_cli/roadmap/implement_step.py`.
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_implement_tool_log.py`

## 3. The documentation

- [ ] Regenerate the documentation.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 4. Archive

- [ ] Archive the change.
  - Verification: `uv run devops openspec archive 2866-tool-log-names-edit-retry-reason`
