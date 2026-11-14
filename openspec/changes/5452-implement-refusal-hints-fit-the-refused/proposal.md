# Proposal

## Why

The implement step answers every refused shell form with one text. Commands such as `uv run python -c` and `git status && git log` read identical advice. The advice about the file comes last.

The prompt and text direct the model to `.data/agent/scratch/`. A fresh checkout does not have this directory. The prompt tells it to make a directory with `uv run python -c`. The shell refuses that form. The model sends the same form again, or it stops after three refusals in a row. #5452

## What Changes

- Select the refusal hint from the whole command in `src/devops_cli/roadmap/implement/implement_shell_refusal.py:def refusal_hint`. Python code with a separator gets the `write_file` text first. A chain of allowed programs gets two separate calls.
- Rewrite `implement_refusal_operator` in `src/devops_cli/lang/en/messages.py` to the two-call text, and add `implement_refusal_python_code` for the script file under the scratch directory.
- Name `read_file` with `offset` and `limit` in the refusal of a pipe to a program that the shell does not allow.
- Add `SHELL_REFUSALS` rows for `openspec` and bare `devops`. Render them in `docs/ROADMAP_WORKFLOW.md`. Compare the refusal table with the shell programs in its test.
- Offer the harness tool `create_directory` in the implement step by configuring `FileSystem` in `_tune`. Make `.data/agent/scratch/` in the job before the first step.
- Replace the `python -c` mkdir text of `src/devops_cli/ai/tasks/roadmap_implement_step.md` with `create_directory`.
- Name `create_directory` and the scratch directory in the shell section of `docs/ROADMAP_WORKFLOW.md`. Test that text in `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`. Run `uv run devops ci fail-to-pass --base origin/main` in the same step.
- Update `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md` to document `create_directory`.
- Carry spec deltas for `roadmap-implement-step/shell`, `roadmap-implement-step/inputs`, and `roadmap-implement-step/budgets`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step/shell`: A chain of allowed programs names two calls, The pipe refusal names read_file, The refusal table names openspec and devops, The step offers create_directory, The python -c refusal names the write_file call first, The shell of a step waits for its command up to the command limit
- `roadmap-implement-step/inputs`: The job makes the scratch directory before the first step, The prompt names create_directory for a new directory
- `roadmap-implement-step/budgets`: A run that reaches a limit ends stopped

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_shell_refusal.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_run.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py`, `tests/roadmap/implement/test_roadmap_implement_read_pipe.py`, `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`, `tests/roadmap/implement/test_roadmap_implement_prompt.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`

## Feasibility

- The probes confirm each cited path at the staging commit: `src/devops_cli/roadmap/implement/implement_shell_refusal.py` is a file of the commit.
- The prompt is under the package: `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- `refusal_hint(word: str)` in `src/devops_cli/roadmap/implement/implement_shell_refusal.py:52` selects hints by first word. Line 105 calls it with `word`.
- `src/devops_cli/lang/en/messages.py:3235:implement_refusal_operator` holds the operator text, and line 3242 holds the pipe text.
- `src/devops_cli/roadmap/implement/implement_step.py:648:IMPLEMENT_LOCAL_TOOL_NAMES` holds the tool names, and `build_agent` builds the agent.
- `pydantic_ai_harness.filesystem` provides `create_directory` with `_safe_resolve`. `Coder` registers only `FILE_TOOL_NAMES`. Adding `create_directory` in `_tune` (`src/devops_cli/roadmap/implement/implement_step.py:587-588`) gives the harness tool without a new module.
- `tests/roadmap/implement/test_roadmap_implement_step.py:752:test_the_agent_has_the_file_tools_and_the_shell_and_no_delegate` asserts the exact offered tools. Group 4 updates this test and verifies it.
- `src/devops_cli/ai/tasks/roadmap_implement_step.md` lines 40 and 59 hold the mkdir text that calls follow.
- `src/devops_cli/ai/knowledge_base/devops_cli/libraries/pydantic_ai_harness.md` lines 34 and 59 state outdated information about directory creation. The plan updates that page.
- `SHELL_REFUSALS` and `IMPLEMENT_ALLOWED_PROGRAMS` sit in `src/devops_cli/roadmap/implement/implement_shell_policy.py`.
- `test_a_refused_program_is_not_an_allowed_program` in `tests/roadmap/implement/test_roadmap_implement_shell_policy.py:108` asserts disjoint sets. Group 3 edits this assertion.
- `tests/roadmap/implement/test_roadmap_implement_shell_policy.py:475:test_the_document_of_the_workflow_holds_the_same_tables` reads `docs/ROADMAP_WORKFLOW.md`.
- `tests/invariants/test_roadmap_workflow_doc.py:194:assert workflow_problems(_document()) == []` reads the same document and still passes.
- `docs/ROADMAP_WORKFLOW.md:286` holds the shell section and line 314 holds the refusal table.
- `tests/roadmap/implement/test_roadmap_implement_shell_refusal.py` holds the refusal tests that group 1 updates.
- `src/devops_cli/roadmap/implement/implement_run.py:471:def _worktree` makes the checkout before the first step.
- `.gitignore:73:.data/*` ignores the scratch directory.
- `src/devops_cli/ci/fail_to_pass.py:706:def run_fail_to_pass` replays changed test files on the base commit.
- Group 6 runs `uv run devops ci fail-to-pass --base origin/main` in its implementation after the document edit.
- The commands of the groups are `uv run devops ci test` and `uv run devops ci fail-to-pass`.
- The first check is `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_refusal.py`.
- The post-release telemetry criterion reads Loki 7 days after the release, so it is pending-person.

## Existing Tool Considered

The locked `pydantic-ai-harness` 0.59.0 provides `create_directory` in its `FileSystem` capability. `Coder` registers only `FILE_TOOL_NAMES`. The step tunes `FileSystem` in `_tune` to include `create_directory`. Using the existing harness tool avoids building custom tool modules.

## Dependencies

- #5528 also changes `src/devops_cli/lang/en/messages.py`; it touches the decision texts and this change touches the refusal texts, so the later pull request rebases on the earlier.
- #5547 also changes `src/devops_cli/lang/en/messages.py`; it touches the test-worker texts, and the two sets of lines do not meet.
- #5575 also changes `src/devops_cli/lang/en/messages.py`; it touches the golden-base texts, and the two sets of lines do not meet.
