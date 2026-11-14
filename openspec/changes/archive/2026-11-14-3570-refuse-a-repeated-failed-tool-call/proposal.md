# Proposal: #3570

## Why

The agent of a repair round can send the same failed tool call again. #3053 asks that no attempt repeats a previous failed action unchanged, and nothing in the tool executor stops it. The step then spends turns and tokens on a call that already failed. `ToolCallLog` already computes the digest of each call for the trace, but it keeps no set of the failed ones. Closes #3570.

## What Changes

- `ToolCallLog` keeps the digest of each call that ends as a retry or as a failure, with the reason that the log masked for it.
- `_execute` refuses a call whose digest is in that set: it returns the earlier reason to the model as a tool result, and the handler does not run. A call that changes one argument has another digest and runs.
- A call that returns a result is not recorded, so the model may read the same file twice.
- The refusal text carries the masked reason, so a path outside the checkout stays hidden.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step/trace`: A repeated failed tool call is refused with its earlier reason.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_tool_log.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_tool_log.py`

## Feasibility

Read on 2026-11-14 against `origin/main` at `04107728d`.

- The digest exists: `src/devops_cli/roadmap/implement/implement_trace.py:136:def argument_digest`.
- The log already computes it for each outcome: `src/devops_cli/roadmap/implement/implement_tool_log.py:493` (retry), `:497` (failed) and `:505` (ok), and `_note` at `:417` writes the line and the trace event.
- The masked reason exists: `logged_reason` at `:290` replaces a path outside the checkout with `implement_tool_path_hidden` (`src/devops_cli/lang/en/messages.py:3282`).
- The execute hook is one place: `_execute` at `src/devops_cli/roadmap/implement/implement_tool_log.py:460`.
- The new tests pass on the branch: `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_tool_log.py`.

## Existing Tool Considered

pydantic-ai's `ModelRetry` returns a message but keeps no set of failed actions across rounds, and the harness registers one executor hook, `_execute`, so the project builds the guard there. The cost is about 30 lines of code and 90 lines of tests.
