# Design

## Context

`cut` in `src/devops_cli/roadmap/refine/refine_investigation.py` limits a tool answer to 240 lines and a character cap. It adds `(more lines are left out)` when it drops text, but the run trace records only the size after the cut. The stage planner and its verifier send tool metrics through `end_run` in `src/devops_cli/roadmap/tool_metrics.py`.

## Goals

- Record the name of the cap that cut each answer.
- Send one counter that a later item can read to tune each cap.

## Decisions

- **A mapping metadata carries the cut.** `ToolReturn.metadata` already carries a `ToolOutcome` or a mapping with `outcome`. The change adds the key `cut` to the mapping for a cut answer. `_outcome_of` reads it and `ToolCallRecord` keeps it.
- **The cap names are short and bounded.** `lines` is `CONST_ROADMAP_REFINE_TOOL_MAX_LINES`, `chars` is the default character cap, `spec` is `CONST_ROADMAP_STAGE_SPEC_MAX_CHARS`, `log` is `CONST_ROADMAP_STAGE_LOG_MAX_COUNT`, and `map` is `CONST_ROADMAP_STAGE_MAP_MAX_FILES`.
- **`cut` keeps its text result.** `cut_with_cap` returns the pair, and `cut` returns the first element, so refine's callers stay unchanged.
- **`git_log` reads one commit over the cap.** It then knows whether the history is longer than the cap. `repo_map` already reads one file over its cap.

## Risks

- A cut metadata changes the metadata of a `ToolReturn` that a test compares with `ok_answer`. Only a cut answer changes, and no test compares a cut answer with `ok_answer`.

## Tests

- A long tool answer carries the name of its cap and a short one carries none.
- `git_log` over the commit cap carries the `log` cap, and a shorter history carries none.
- `repo_map` over the file cap carries the `map` cap.
- `RunTrace.absorb` keeps the cap in `ToolCallRecord`.
- `end_run` adds one count for each cut call and none for a whole call.
