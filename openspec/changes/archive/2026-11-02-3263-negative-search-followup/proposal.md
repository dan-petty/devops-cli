# Proposal

## Why

Refs #3263. The review of the first pull request for #3263 (the step runs a negative search verify) found four defects in the merged change and two choices to record.

1. The prompt of the implement step says "Run the verification command of each task". The shell of the agent refuses `!`, and the refusal gave only the list of allowed programs. Each refusal counts against a limit that stops the step and loses its work, so a model that follows the prompt spends refusals on a check that it cannot run.
2. `re.ASCII` on the literal and the path patterns had no test: removing it left all tests green.
3. A word of 300000 characters made `execve` fail with E2BIG, and the step crashed.
4. A refusal reason echoed the raw word, with a NUL byte or a line break.
5. `commands_failure` repeated the branches of `verification_problem`.
6. A path that matches no file passes, and `-e` and `-E` are refused. The first is a choice, the second is deferred.

## What Changes

- The refusal table gets the row `!`. The hint says to run `git grep -n <literal> -- <paths>`, to read no output as a pass, and that the step runs a verification command that starts with `!` itself. Step 5 of the prompt says the same, and the table of `docs/ROADMAP_WORKFLOW.md` gets the row.
- A test pins that a fullwidth or accented literal and path are refused. Removing `re.ASCII` now fails four tests.
- The words of a negative search hold at most `CONST_ROADMAP_IMPLEMENT_SEARCH_CHARS` (2000) characters in all. A longer search is refused with a reason, and a stop reason shows the command cut to that length.
- A word in a refusal reason is escaped (`unicode_escape`) and cut to 60 characters.
- `read_verification` returns the process to start (or the reason) for any verification command, and `commands_failure` calls it. The two refusals of the step (not a command line, not an allowed program) and the refusal of a search are one message: "The verification command {command} is refused: {reason}." The step and the gate read the same function, and a test holds that no command is refused by one side only.
- Observable behavior changes (a refusal hint, a limit, a message), so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the negative search and the refusal of `!` in the shell of the agent.

## Impact

- Code: `src/devops_cli/roadmap/implement_shell_policy.py`, `implement_step.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/constants.py`.
- Prompt: `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- Documents: `docs/ROADMAP_WORKFLOW.md`.
- Tests: `tests/roadmap/test_roadmap_implement_negative_search.py`, `test_roadmap_implement_shell_refusal.py`, `test_roadmap_implement_shell_policy.py`, `test_roadmap_implement_step.py`, `test_roadmap_limit_classes.py`.

## Feasibility

- Each defect was reproduced first. `refusal_hint("!")` on origin/main returned only "These programs are allowed: ...". The new hint tests, the prompt test and the changed message tests fail on origin/main (`devops ci fail-to-pass`).
- A word of 300000 characters: `execve` limits one argument to 131072 bytes (`MAX_ARG_STRLEN`), and the review ran the real `commands_failure` into `OSError: [Errno 7] Argument list too long`.
- The mutation was run again: with `re.ASCII` removed from both patterns, 4 tests fail now.
- `-E` is refused on the plan of #2610: `parse_task_groups` and `verification_problem` give "the option `-E` is not allowed" for the Verification line of its group 3.

## Existing Tool Considered

`git grep`, `shlex` and `str.encode("unicode_escape")` cover the need. No library is added. The change builds about 60 lines of source and 150 lines of tests: roughly 40000 tokens to build and fix, 2000 tokens a year to keep, and about 1.5 hours. It deletes the two messages `implement_stop_command_denied` and `implement_stop_command_unparsed` and the search message: one message replaces them.
