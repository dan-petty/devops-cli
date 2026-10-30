# Tasks

## 1. The log and the reason name the refused program

- [x] Write failing tests in `tests/test_roadmap_implement_tool_log.py` and `tests/test_roadmap_implement_step.py`: a refused known program shows in the line; any other word, such as an assignment with `=`, a path, a quote, a space, an escape sequence, a short password and a word that `mask_secrets` changes, shows "other"; the reason counts refused commands by program, in order of count; more programs than `CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS` join "other"; no refusal gives "0".
  - Verification: `uv run devops ci test tests/test_roadmap_implement_tool_log.py tests/test_roadmap_implement_step.py`
- [x] Add `command_word`, `is_policy_refusal` and `logged_program` to `src/devops_cli/roadmap/implement_tool_log.py`, make `ToolCallLog.refused` a `Counter` with `refused_text()`, add `CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS` to `src/devops_cli/config/constants.py`, and use the text in `_stop_reason` of `src/devops_cli/roadmap/implement_step.py`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_tool_log.py tests/test_roadmap_implement_step.py`

## 2. The refusal names the replacement

- [x] Write failing tests in `tests/test_roadmap_implement_shell_refusal.py`, with the model as a `FunctionModel`: the refusal of `python`, `cat` and `cd` holds the replacement of the table and the original text; an unknown program gets the list of allowed programs; an operator gets the rule of one command; five refusals reach the model and the sixth ends the run; a file tool refusal gets no hint; nothing that the shell allows changes.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_shell_refusal.py`
- [x] Add `IMPLEMENT_SHELL_REPLACEMENTS` to `src/devops_cli/config/commands.py`, the hint texts to `src/devops_cli/lang/en/messages.py`, the new module `src/devops_cli/roadmap/implement_shell_refusal.py`, and the capability in `build_agent`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_shell_refusal.py tests/test_roadmap_implement_step.py`

## 3. The prompt table

- [x] Write a failing test in `tests/test_roadmap_implement_shell_refusal.py` that pins the line of allowed programs and the table of the prompt to `IMPLEMENT_SHELL_PROGRAMS` and `IMPLEMENT_SHELL_REPLACEMENTS`, and that each replacement names an allowed program or a tool that the agent has.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_shell_refusal.py`
- [x] Add the table to `src/devops_cli/ai/tasks/roadmap_implement_step.md`, next to the line of allowed programs.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_shell_refusal.py`

## 4. Findings of the review

- [x] Write failing tests, then log only a known program (`logged_program`), cut the text of the shell in the hint, add `python -m pip` to the replacement of `python` and `python3`, and change the directory command of the prompt to one that has no refused operator. A test checks each shell command of the prompt against `CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS`.
  - Verification: `uv run devops ci test tests/test_roadmap_implement_shell_refusal.py tests/test_roadmap_implement_tool_log.py tests/test_roadmap_implement_step.py`

## 5. The documentation

- [ ] Regenerate the documentation.
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 6. Archive

- [ ] Archive the change.
  - Verification: `uv run devops openspec archive 2773-refused-shell-programs`
