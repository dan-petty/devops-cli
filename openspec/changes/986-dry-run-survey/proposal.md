# Proposal

## Why

Issue #986: commands that take arguments must be checked under their `--dry-run` flag.
Issue #885 surveyed 80 argument-free command paths at commit `9c879ae`.
The remaining 40 argument-taking paths were not run because they required input parameters.
Core execution runners print `Would run command` under `DEVOPS_CLI_DRY_RUN` but do not block subprocess execution.
Commands that do not evaluate `is_dry_run()` or `dry_run` before calling subprocess runners or external APIs run for real under `--dry-run`.
Under #412 and #986, an offender contacts external servers, writes outside temporary directories, or changes local state.
This survey determines whether argument-taking commands honor `--dry-run` or perform unintended actions.

## What Changes

- Derives all argument-taking commands declaring `--dry-run` from the Click and Typer tree.
- Reconciles command counts against the 120-path baseline from issue #885 (80 argument-free, 40 argument-taking at `9c879ae`) to the current HEAD (174 argument-free, 51 argument-taking at `a155b0ca`).
- Executes all 51 argument-taking commands under `CliRunner` with valid placeholder arguments, monkeypatched `subprocess.run`, and network isolation.
- Records every executed subprocess call and classifies it as `local read`, `local write`, or `external`.
- Records any command that attempts network or external server access.
- Files roadmap candidate issues for identified offenders outside `commands/ci.py`.
- Documents all 51 argument-taking command paths, placeholder arguments, exit codes, and process classifications in `design.md`.
- Modifies no production or test code in `src/` or `tests/`. It sets `skip_specs: true` in `.openspec.yaml` and fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documentation: `openspec/changes/986-dry-run-survey/` (archived upon completion).
- Product code: none.
- Test code: none.
- Candidate issues: filed in the project backlog via `devops roadmap intake`.

## Feasibility

- The Click and Typer command tree allows recursive enumeration of subcommands, arguments, and declared options.
- At surveyed commit `a155b0ca`, 225 total commands declare `--dry-run`.
- Among the 225 commands, 51 commands require positional arguments or required options.
- The remaining 174 commands run without required inputs (114 zero-argument commands and 60 optional-argument commands).
- Running each command with `CliRunner` and intercepting `subprocess.run` captures all invoked child commands deterministically.
- Network socket calls are blocked and verified under the standard test isolation contract.
- Each identified offender is verified through code inspection and filed as a backlog candidate.

## Existing Tool Considered

`tests/test_all_commands_help_dryrun.py` tests a hardcoded list of argument-free commands for exit code 0.
It does not inspect the full command tree dynamically and does not run argument-taking commands.
Automating the enumeration directly from the Click tree covers all current commands without maintaining a manual list.
