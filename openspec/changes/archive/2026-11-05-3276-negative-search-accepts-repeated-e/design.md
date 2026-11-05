# Design

## Context

The negative search is `! git grep [options] <literal> [--] <path>...` (#3263). The step reads the words in `read_negative_search` (`src/devops_cli/roadmap/implement_shell_policy.py`). The stage job reads the same function through `negative_search_parts` (`src/devops_cli/roadmap/stage_form.py`) and `_literal` (`src/devops_cli/roadmap/stage_move.py`). One literal is the only form the reader accepts.

## Decisions

### Repeat `-e`, and keep the positional literal

Git matches a line that holds any of several `-e` patterns, with no `--and` and no `--all-match` (checked on git 2.55.0). A group with four names then needs one line, not four tasks.

- Rejected: one `! git grep` line for each name. Each name adds a line or a task, and the plan loses its one-line check of a group. The two-name search of the first acceptance criterion cannot run as one line.
- Rejected: replace the positional literal with `-e` only. Committed plans, such as task 1.1 of #2610, use the positional form. Dropping it refuses every committed line of that shape.

### Each `-e` value is a plain literal

Each value passes the same check as the positional literal: the signs of `NEGATIVE_SEARCH_LITERAL_SIGNS` and no leading `-`. A value that starts with `-` is refused with its own reason, so `-E`, `-P` and an option word stay refused as a value. The value `--` gets its own reason: it is a missing literal.

- Rejected: let a value start with `-`. Git would read it as a pattern, but the grammar could no longer tell an option word from a literal, and `-E` as a value would pass unnoticed.

### `--` is required with `-e`, and no word may come before it

With `-e`, git reads a positional word as a path. The search would then cover other paths, and the plan would not say so. The reader requires `--` after the last `-e` value and refuses any word between them.

- Rejected: let git read the word as a path. The search covers paths that the plan does not name.
- Rejected: accept a mixed form with a positional literal and `-e`. A plain word is both a literal and a path, so the reader cannot tell which the plan meant.

### The stage job checks each literal

`record_search_evidence` records the staged hits for each literal. `search_problems` refuses each literal with no staged hit, and each literal that a created module keeps. A literal with no staged hit already passes before the change, so the check holds for each literal alone.

- Rejected: check only the first literal. A second literal with no hit proves nothing, and the stage job would accept it.

### Move groups check each literal

`move_verify_problems` refuses a move group when any literal names one module of the moved prefix.

## Rejected for the scope of this change

- A test over every committed `tasks.md` (AC3 of #3276). Three active plans hold refused commands that this change does not fix. #3187 holds regex lines with boundaries that the grammar cannot express, and its plan needs a rewrite by its owner. The test waits for that rewrite (see Workflow follow-up in the proposal).
- A fix of the prose code spans of `step_files.py`. It is a separate cause, so it gets its own issue.
