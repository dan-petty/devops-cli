# Proposal

## Why

Issue #2789. An implement step that wrote correct code stops on a formatting check, and the job discards the work. Job `devops-cli-runner-20261030-165513-98d9` ran on #2656. The agent fixed `round_trip.py` and added a test. The step then stopped because `uv run ruff format --check` exited with status 1: one `raise` line was too long.

A formatter gives one result for one input. An editor or a pre-commit hook applies it without asking. A model has no reason to be the one that applies it, and a stop on a format error costs a whole step of correct work.

## What Changes

- After the step stages the checkout, the job runs `uv run ruff format <changed Python files>` in the checkout. It runs outside the shell of the agent, before the verification commands and the static checks.
- The job stages the files that the formatter changed, so the commit holds the formatted files.
- The job prints one muted line to the error stream: `Formatted: <paths>`. A run that changes no file prints no line. The paths are bounded like the paths of other step reasons.
- A file with a syntax error makes `ruff format` exit with status 2. The step stops with that command and its output. The step does not swallow the error.
- The format run is one command. It has the same timeout as the other commands of the exit checks, and a timeout stops the step.
- The static checks run `ruff check` and `mypy --strict`. The `ruff format --check` row goes. `ruff check` does not fix: a lint rule can point at a real defect that the model must see.
- The formatter gets only the changed files that end in `.py`, from the list that the step already builds. It touches no other file.
- The job gives the file names to `ruff format`, `ruff check` and `mypy --strict` after `--`. A name that starts with `-` is then a path, not an option.
- The job stops the step before the format run when a changed Python file is a symbolic link. The formatter writes, and it follows a link to a file outside the checkout. The reason names the link.
- The prompt of the step says that the job formats the changed Python files, so the model need not run the formatter.
- A consumer observes the exit of a step, so the change carries a spec delta. It adds one requirement to `roadmap-implement-step`. It modifies none, because no requirement names the format check.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: one requirement is added. The job formats the changed Python files before the other exit checks.

## Impact

- `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `src/devops_cli/lang/en/messages.py`.
- `tests/test_roadmap_implement_step_format.py` is new. `tests/test_roadmap_implement_step.py` changes its list of commands.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The failure is real. The stop comment of the Service on #2656 reads "uv run ruff format --check src/devops_cli/config/round_trip.py exited with status 1", with a diff that wraps one `raise ConfigurationError(...)` line over three lines. The discarded diff holds the correct fix and its test.
- The cause is in `_static_failure` of `implement_step.py`. It runs `ruff check`, `ruff format --check` and `mypy --strict` and stops on the first failure.
- A probe with ruff 0.16.8 shows how the formatter treats a file with a syntax error. `uv run ruff format bad.py ok.py` prints `error: Failed to parse .../bad.py:1:7: Expected a parameter or the end of the parameter list`, formats `ok.py`, leaves `bad.py` as it was, and exits with status 2. `_command_failure` turns a non-zero status into a stop that holds the tail of the output, so the error is visible and nothing is swallowed.
- Explicit file arguments make ruff format only those files. A probe shows that it reports `1 file reformatted` for one path. The formatter cannot touch a file outside the list.
- The files that the formatter changed come from git, not from the output of ruff. After `git add -A` the index holds the files before the format run, so `git diff --name-only -z` lists exactly the files that the formatter changed. No output of ruff is parsed.
- The timeout is per command. `_command_failure` passes `CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS` to `run_subprocess` for each verification command and each static check. The format run uses the same function, so it counts as one command with the same limit.
- A probe with ruff 0.16.8 shows that `ruff format link.py` writes through a link to a file outside the checkout, and that a link to a directory makes ruff format every Python file below it. The file name comes from the agent, which can make a link with `git` or `uv run python`. `Path.is_symlink` finds the link, so no parser is needed.
- A probe shows that a file named `--config=exclude = ['*.py'] #.py` is read as a ruff option unless `--` comes before the paths. With `--` the same name is a path. `mypy --strict -- <file>` and `ruff check -- <file>` also run as before.

## Existing Tool Considered

`ruff format`, which the project pins and the step already runs as `ruff format --check`. The job calls the same program without `--check`. Git lists the changed files. The change builds no formatter and no parser. It builds one function of about 15 lines, and it deletes the `ruff format --check` row of `_static_failure`.

Cost of what it builds, estimated: about 20 lines of code and 120 lines of tests, about 40k tokens of agent work and one hour of elapsed time. The upkeep is small: the code calls a pinned tool.
