# Proposal: #4630

## Why

Nine prompt files of `src/devops_cli/ai/tasks/` and the two files of `src/devops_cli/ai/prompts/` have no reader in the code. `review_prompt_digest` in `src/devops_cli/ai/personas/__init__.py` hashes every `.md` file of `ai/tasks/`, so an edit of an orphan file moves the arm of the review benchmark. `load_task_prompt` in `src/devops_cli/ai/task_loader.py` returns an empty string for a missing file. A misspelt name thus sends a model an empty prompt, and two modules keep a second copy of their prompt in code as a fallback, which `docs/SDLC.md` forbids. Closes #4630.

## What Changes

- Delete the nine orphan files of `ai/tasks/`: `agent_direct_response_from_reasoning.md`, `agent_direct_response_from_tools.md`, `agent_invoke_tool_request.md`, `agent_tool_already_called.md`, `agent_tool_feedback.md`, `guardrails_isolation.md`, `summarize_memory.md`, `summarize_memory_system.md` and `tool_execution_protocol.md`. The folder keeps 51 files.
- Delete `ai/prompts/benchmark_suite_system.md` and `ai/prompts/benchmark_suite_user.md`, and with them the folder. Remove its glob from `CONST_DOCS_CLASS_PROMPT` and from the agent-instruction globs of `tests/invariants/test_agents_md.py`.
- `load_task_prompt` raises the new `TaskPromptNotFoundError` (error code `TASK_PROMPT_NOT_FOUND`) for a name that is not a file of `ai/tasks/`, and for a name that resolves outside the folder. It no longer returns an empty string.
- Delete the fallback prompts `_DEFAULT_SOCRATIC_SYSTEM` (`ai/research/socratic.py`) and `_DEFAULT_SYNTHESIS_SYSTEM` (`ai/research/mental_model.py`).
- Move the check that each prompt name the code loads exists from a pytest test into the `test-tree` row of `devops ci` (`tests/gate/tree_checks/task_prompts.py`), as `docs/TESTING.md` asks for a check of committed files. It now resolves a name that holds a constant, also through a `from` import, and not only a literal. A second check of the row fails when a file of `ai/tasks/` has no string literal in `src/` that names it, so a new orphan fails CI.
- `docs/TESTING.md` lists the new invariant file `tests/invariants/test_task_prompts_check.py`, and the error catalog `docs/ERRORS.md` lists the new error.
- The new error and its message are output that a consumer can see, so the change has a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `ai-task-prompts`: how the package loads a task prompt by name, and the error for a name that is not a prompt of the package.

### Modified Capabilities

None.

## Impact

- A missing prompt now stops the call with `TaskPromptNotFoundError` and does not send an empty prompt to a model. Each name in the code exists, so no command changes its output.
- The prompt digest of a review changes once, because eleven files leave the hashed folders. A benchmark compares arms of one digest, so runs before and after the merge are two arms.
- No setting, command, manifest or dependency changes.

## Feasibility

- `git grep -n <name> -- ':!src/devops_cli/ai/tasks' ':!src/devops_cli/ai/prompts'` for each of the nine names prints nothing in code. Only `CHANGELOG.md` and `docs/agent/archive/historical-phases-1-to-50.md` name `guardrails_isolation`, as history.
- A census over the syntax trees of `src/` (the `unread_prompts` check of this change, run on `origin/main`) lists exactly the nine files as the files of `ai/tasks/` that no string literal names. It lists no other file.
- `git grep -n "benchmark_suite_system\|ai/prompts"` prints only `src/devops_cli/config/constants.py:499` and two test lines. The code stopped reading the two benchmark-suite files when the suite was removed (`git log -S benchmark_suite_system -- src`, commit `79119417`), and those reads already went to `ai/tasks/`, where the files never were.
- Source: `review_prompt_digest` hashes `directory.rglob("*.md")` of `ai/tasks/` and of `ai/personas/`. `load_task_prompt` returned `""` when `target_path.is_file()` was false.
- Only `socratic.py:139` and `mental_model.py:225` read the result of `load_task_prompt` with an `or` fallback.

## Existing Tool Considered

The change deletes code and adds no tool: `git grep` and the `ast` module of the standard library find the readers. Cost: about 60,000 tokens and 1 hour to build. The upkeep is the two checks of the `test-tree` row, about 120 lines. Internal code deleted: eleven prompt files (67 lines), the two fallback prompts (10 lines), the empty-string branch of `load_task_prompt` and the literal-only prompt test of `tests/ai/test_ai_task_loader.py`.
