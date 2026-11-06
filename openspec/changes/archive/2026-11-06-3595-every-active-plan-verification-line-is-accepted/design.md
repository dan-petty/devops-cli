# Design

## Context

See proposal.md (#3595, #3579). The step runs a `Verification:` command as a list of words. A plan whose line the step refuses stops at its group. The test finds such a line before the step does.

## Decisions

### 1. Rewrite the plans, keep no exception list

- **Decision**: Rewrite each refused line in the grammar of `read_verification`. The test has no exception list.
- **Rejected**: A list of excepted spans with a stale check (#3579). Every refused line has a form in the grammar, so the list would hold no entry. A list invites the next refused line to land as an exception, and the step still stops at it.
- **Rejected**: A wider grammar. The `-E` option and the program `test` would pass the guard for every plan. #3276 chose a narrow grammar on purpose, and a wide one weakens it.

### 2. The test takes its refusals from the function of the step

- **Decision**: The test calls `verification_problem`, which calls `read_verification`. It holds no table of options or programs. When the step accepts a new form, the test accepts it with no edit.
- **Rejected**: A copy of the grammar in the test. It drifts from the step.

### 3. The test reads the tasks as the step reads them

- **Decision**: `parse_task_groups` gives each task and each code span of its `Verification:` lines. The test checks every span, not the first span of a task.
- **Rejected**: `read_change`. It reads one command for each task, and it raises an error on a plan that is wrong in form, so it cannot list every refused span.

### 4. How the refused lines are rewritten

- **Prose code spans (#2610)**: the explanation moves into the text of the task and loses its backticks. The `Verification:` line holds the one command and the suffix `fails on the base`, as the stage template writes it.
- **`test -z "$(find ...)"` (#3187)**: the shell cannot run `test`, and a negative search reads file content, not file names. The new line proves the move in two ways that the grammar allows: `ls` of the new paths fails when a file is missing, and a negative search with literals fails when an import still names the old module path. The invariant tests of group 9 hold the rest: no old top-level module name remains.
- **`! git grep -n -E ...` (#3187)**: the regex of 4 alternations becomes `-e` literals. A literal that ends in `_`, or that holds a space (`devops_cli.roadmap.stage import`), cannot match the new path `devops_cli.roadmap.stage.stage_change`. The bare module name `store` uses the option `-w`, so `stores` does not match.
- **`':!tests/roadmap/'` (#3187)**: a pathspec with `:` is refused. Group 7 names the directories that hold a reference. Task 8.2 searches the whole `tests/` tree.
- A string target of a monkeypatch such as `devops_cli.roadmap.stage.foo` cannot be told from the new path by a literal. The invariant test of task 9.1 holds that check in Python.
