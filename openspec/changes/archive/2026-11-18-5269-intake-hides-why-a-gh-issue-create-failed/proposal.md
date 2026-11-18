# Proposal: #5269

## Why

`devops roadmap intake --confirm` failed once to open a new issue and hid why. The error was
`Could not open the issue '<title cut to 64 characters>' in dan-petty/devops-cli (exit 1):
unexpected end of JSON input` (`_failure`, `src/devops_cli/roadmap/stores/github_store.py`). It
cuts the title to 64 characters, so the reader cannot see what intake sent; it names no `gh`
command; and it presents gh's stderr as an unlabeled blob, which reads like a JSON parse failure of
intake. The intake summary cuts the title again, to 80 characters
(`PlacementFailure.name`, `src/devops_cli/roadmap/intake/intake.py`). Closes #5269.

## What Changes

- The error for a failed roadmap store write names the `gh` command up to the first field value,
  its exit code and its stderr, and labels the stderr or says it is empty.
- The `create_issue` error names the full issue title that intake sent, and the intake failure
  summary names the candidate by its full title.

## Capabilities

- `roadmap-store-write-failure` (new): what the error of a failed roadmap store write holds.
- `roadmap-intake-failures` (modified): the failure line names the full title of a new candidate.

## Impact

- A failed create shows the cause: the command, the exit code, gh's stderr and the full title.
- The command names no field value, so the body and the labels never print and the stderr stays
  within its bound.
- The change fits one pull request.

## Feasibility

- Read 2026-11-18: `_failure` builds the message from `proc.stderr` and `proc.stdout`
  (`src/devops_cli/roadmap/stores/github_store.py:1495`), `create_issue` cuts the title to 64
  (`:1013`), and `PlacementFailure.name` cuts the title to 80
  (`src/devops_cli/roadmap/intake/intake.py:463`). `create_issue_args` gives the args the command
  name is read from (`:646`).
- An intake parse failure reads `GitHub returned malformed issue after it was opened`; the reported
  text was gh's own stderr, which `_failure` puts in the message, so the exit-code check stays
  first and no second parse path is added.

## Existing Tool Considered

No new tool is needed. The alternatives check of 2026-11-16 found no library that reports a failed
gh command with its stderr and the full title. `plumbum`'s `ProcessExecutionError` carries argv,
stdout, stderr and the return code, but the project already receives the same fields from
`subprocess.CompletedProcess`, so it lacks only what this change adds. The change edits `_failure`,
`create_issue`, `gh_command_name` and `PlacementFailure.name`.
