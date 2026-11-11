# Proposal: #4547

## Why

The Feasibility trace gate of the stage job reads a toolbox tool name before a path only when a space follows it, as in `read_file src/devops_cli/sample.py` (#4463). For the call form, `read_file("src/devops_cli/sample.py", 60, 80)`, `_citation` in `src/devops_cli/roadmap/stage/stage_change.py` keeps the whole span as the path. `_was_read` then finds no match, also when the run read the file. The stored refusal `4472.refused.json` of the roadmap-service pod holds this false refusal. Closes #4547.

## What Changes

- `_citation` takes the first quoted string argument of a call to a known stage tool as the citation. The existing `path:line` rules and the `./` rule then apply to it.
- A call of a word that is no stage tool stays whole, as before.
- Tests cover the double-quoted and single-quoted call, a call with a line range in the path, a call of an unread path, and a call of a word that is no stage tool.

## Capabilities

- `roadmap-stage` (modified): the trace gate reads the path of a tool call citation.

## Impact

- A stage proposal that cites a read in the call form is no longer refused when the run read the path. A call of an unread path is still refused, and the refusal names the path. No setting, command or manifest changes.

## Feasibility

- Source: `_claimed_path` and `_citation` (`src/devops_cli/roadmap/stage/stage_change.py`) split a span at the first space only, so `read_file("a.py", 60, 80)` stays whole. The test `test_a_line_or_a_tool_call_citation_of_a_read_path_passes` failed for the call form on `origin/main` before the change.
- Evidence: the issue cites the stored refusal of 4472: "The Feasibility section states that `read_file("tests/commands/test_test_selection.py", 60, 80)` was read, but the run did not read it."

## Existing Tool Considered

No open library parses a free-text citation of this project. The change adds one regular expression of three lines to the existing citation function and does not add a second parser (the Python `ast` module would need a complete call expression, and a citation may be cut). Cost: about 6,000 tokens and 1 hour to build, about 2,000 tokens per year to keep.
