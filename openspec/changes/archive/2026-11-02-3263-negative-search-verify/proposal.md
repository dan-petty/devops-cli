# Proposal

## Why

Issue #3263: the stage gate admits a `verify` command that the implement step refuses. `_valid_verify` in `stage_form.py` accepts any command that starts with `! git grep `, and `docs/TESTING.md` names this form as the check of a deletion. The step splits a verification command with `shlex` and runs it only when its first word is on the verification list. The first word of `! git grep -n name src/ tests/` is `!`, which is on no list, so a plan passes the gate and the step then stops with "The verification command ... is not allowed. ! is not one of: git, uv, ...".

The gate and the step read two different tables. This change makes them read one.

## What Changes

- `implement_shell_policy.py` gets the one definition of the negative search: `! git grep [options] <literal> [--] <path>...`. `read_negative_search` reads the words of a command into `NegativeSearch` or gives the reason that the step refuses it. `verification_problem` gives the reason for any verification command, or None when the step runs it.
- The step runs a negative search itself, as a list of words and never through a shell. It runs `git grep <options> <literal> -- <paths>`, with `--` put before the paths, and the search passes only when git exits 1 (no match). A match (exit 0) stops the step with the matching lines. Any other status (an error) stops the step.
- Only these options are allowed, as letters in one word or in several: `-n -I -F -i -w -l -c -q`. No other option is allowed. A literal has letters, digits, spaces and `_ . : / = @ + , # % ~ -`. A path is relative, has the characters `\w . + @ ~ * / -`, does not start with `-` or `/`, and has no `..` part.
- The stage gate asks `verification_problem` for a `verify` command of the project form. A command that the step refuses gets a problem that holds the reason of the step.
- `!` followed by another command, a pipe, `;`, `&&`, a redirect, a subshell, `--no-index`, `-O`, `-f`, `-e` and every other option are refused with a reason, and the step starts no process for them.
- The stage prompt names the options and the signs of the literal.
- Observable behavior changes (the step runs a new form, the gate gives a new problem), so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the verification commands of a group, and the negative search.
- `roadmap-stage`: the form of a `verify` command.

## Impact

- Code: `src/devops_cli/roadmap/implement_shell_policy.py`, `implement_step.py`, `stage_form.py`, `src/devops_cli/lang/en/messages.py`.
- Prompt: `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Documents: `docs/TESTING.md`.
- Tests: the new `tests/roadmap/test_roadmap_implement_negative_search.py`, and `test_roadmap_implement_shell_policy.py`, `test_roadmap_stage_form.py`.
- Security: the step runs one more fixed shape of `git`. The agent's own shell is unchanged: `!` is still on no allowlist of the shell.

## Feasibility

- The premise holds on `origin/main` (`e0de9ba1`), and it was run, not only read. `commands_failure(checkout, ["! git grep -n absent_name src/ tests/"])`, the function that the step calls for the verification commands of a group, returns "The verification command ! git grep -n absent_name src/ tests/ is not allowed. ! is not one of: git, uv, ruff, mypy, grep, cat, ls, head, tail, find, openspec, devops." The same plan passes `form_problems` with no problem. The new test `test_every_verify_form_that_the_gate_admits_is_a_command_that_the_step_runs` fails on the base with this text.
- The step does not use a shell for a verification command (`run_subprocess(list(argv), ...)` after `shlex.split`), so a pipe or `;` in a command is a plain argument and never runs a second command. The fixed shape is still needed: `git grep` has options that open a program (`-O`, `--open-files-in-pager`), read a file (`-f`) or leave the repository (`--no-index`).
- git 2.43.0 exit codes of `git grep`: 1 with no match, 0 with a match, 128 for an error. A path that is no file or revision gives 128 ("ambiguous argument") without `--` and 1 with `--`; a path outside the repository (`/etc`, `../x`) gives 128. So the step puts `--` before the paths and checks the exit code is exactly 1.

## Existing Tool Considered

`git grep` itself is the tool, and `shlex` reads the words. No new library is added. A shell-word parser or a command sandbox would cover more forms, but the need is one fixed form, and the project's rule is that a verification command runs as a list of words. The change builds about 90 lines of source and 330 lines of tests: roughly 60000 tokens to build and fix, 3000 tokens a year to keep, and about 2 hours. The change deletes `_valid_verify` and `_NEGATIVE_SEARCH_PREFIX` from `stage_form.py`: the gate no longer keeps its own prefix check for the negative search.
