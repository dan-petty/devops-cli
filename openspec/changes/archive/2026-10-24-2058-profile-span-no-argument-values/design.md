# Design

## Context

`devops telemetry profile <command line>` runs a devops-cli command line under a `telemetry.profile` span, then reads the trace back from Tempo and shows its waterfall. The profiled command runs through `run_subprocess`, so its `subprocess.<program>` span is a child of the profile span, and the spans of the child process are under that span. See proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**

- The profile span names the profiled command and counts its arguments, and holds no argument value.
- One rule for all spans: only a subprocess span records the arguments of a program, and only when a person turns on `telemetry.capture_command_args`.

**Non-Goals:**

- The `cli.command` alias to `process.command_line` on the command spans (#2059). The profile span does not set `cli.command`.
- The text that the command shows to the person (`Profiling command: <command line>`). It goes to the terminal of the person who typed it, and not to the trace backend.

## Decisions

- **The span uses the names of the command spans: `cli.command_path` and `cli.args_count`.** #1996 put them on the command spans. Rejected: `process.args_count` on the profile span. The profile span is not a process span, and the subprocess span under it already holds `process.args_count` for the program that it runs (the interpreter, its flags and the words), so two different counts would have one name in one trace.
- **`cli.args_count` counts the words that are not command names.** `devops config set <key> <value>` gives `devops config set` and 2, as `_delegate` counts the words after the command that its span names. Rejected: the count of all words after `devops`. Then the count also holds the command names that the path already shows.
- **The walk is Typer's shell completion walk (`_resolve_context`), from the module app of the first word.** It parses resiliently, so no prompt and no command callback runs, and the help, version and completion callbacks return at once. Rejected: take the words before the first option as the path. The words of `config set <key> <value>` look like command names, and only the command tree tells them apart. Rejected: a walk of our own with `resolve_command` and `make_context`. It repeats the 20 lines of `_resolve_context`. Rejected: walk from the root app of `devops`. Its `--version` option has a callback that prints the version also in a resilient parse, and each top-level command is a lazy proxy that the walk must leave for the module app anyway. A command line that starts with an option of `devops` itself thus gives the path `devops`.
- **The profile span does not read `telemetry.capture_command_args`.** The profiled command runs through `run_subprocess`, and with the setting on its subprocess span, the child of the profile span, holds every argument in `process.command_args` through the secret mask (#2025). A copy on the profile span would put the same values in a second attribute that a person cannot turn off apart. The test `test_a_person_who_turns_on_capture_gets_the_profiled_arguments_on_the_subprocess_span_only` holds this rule.

## Risks / Trade-offs

- [`_resolve_context` is a private function of the vendored Click] → `tests/test_docs_command_resolver.py` holds the paths and counts at each depth, so a Typer upgrade that changes or removes it fails the test. `src/devops_cli/core/command_resolver.py` already reads `_protected_args` of the vendored Click on the same terms.
- [The resolution imports the module of the profiled command in the profile process] → The import occurs one time for each profile, and the child process imports it again. This is a cost of a fraction of a second for a diagnostic command.
