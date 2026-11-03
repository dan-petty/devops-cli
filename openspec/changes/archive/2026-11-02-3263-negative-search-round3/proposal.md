# Proposal

## Why

Refs #3263. The review of the second pull request for #3263 (the agent learns that the step runs a bang command) found one blocker, one major defect and five minor defects in the merged change.

1. The stop reason named the raw command. The escape of a word in the reason was bypassed: `commands_failure` wrote `{command}` into the same sentence and only cut it. A `tasks.md` line with ESC, VT, NEL or a bidi override reached `outcome.reason`, which the job posts to the item. The gate echoed the command uncut and unescaped (300190 characters for a command of 300000).
2. `failure.py` read the old text `command \S+ is not allowed`. The new message lists `mypy` and `ruff`, so a refused one-word program (`curl`, `python`, `rg`) changed from `refused_tool` / `wait` to `types` / `repair`.
3. The accepted case "a path that matches no file passes" relied on a plan-time check that does not cover `src/` and `tests/`: `StagedTree.paths_in("! git grep -n name src/ tests/")` is empty, so `! git grep -n hello scr/ testz/` passes and searches nothing.
4. The limit of 2000 characters covered `!` only. `grep -n zz <300000 characters>` and `uv run devops ci test <300000>` still raised `OSError: [Errno 7] Argument list too long`.
5. `!` was a known program of the tool log, so the free words after it were logged.
6. Seven mutants survived: the value 2000, the two cuts, the escape of an option word and of the first word, and the two parts of the step-5 sentence of the prompt.
7. The documents did not cite #3276, the issue for a search with several names.

## What Changes

- One function, `shown`, escapes and cuts a text for a reason. The step names the command with it in every message of `commands_failure`, and the gate names the command with it in every `verify` problem. A test reads `outcome.reason` of a real step and the problems of `form_problems`.
- `failure.py` takes the rule for a refused verification command from the message of the step (`implement_stop_command_refused`), so the rule cannot drift from the text. A refused command is `refused_tool` / `wait` for a program, an option, a shape and a length. The dead alternative `command \S+ is not allowed` is gone.
- The plan-time path check reads the paths of a negative search from the reader of the step, so `src/`, `tests/` and `.` are judged: a path must be a file or a folder of the staged commit, or one that the plan creates. A group that deletes a folder still passes, because the folder exists at plan time.
- The limit of 2000 characters moves from the negative search to `read_verification`, so it holds for every verification command. The longest line in the committed `tasks.md` files is 414 characters.
- The tool log does not name `!` as a program, so the words after it are not logged.
- Tests pin the value 2000, the cuts at 60 and 2000 characters, the escape of an option word and of the first word, and the two parts of the sentence in step 5.
- Observable behavior changes (a message, a limit, a class, a check of paths), so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the limit and the safe reason of a verification command, and the log of a bang command.
- `roadmap-stage`: the paths of a negative search.
- `roadmap-failure-taxonomy`: a refused verification command.

## Impact

- Code: `src/devops_cli/roadmap/implement_shell_policy.py`, `implement_step.py`, `implement_tool_log.py`, `stage_form.py`, `stage_paths.py`, `failure.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: the new `tests/roadmap/test_roadmap_implement_verification_reason.py`, and `test_roadmap_failure.py`, `test_roadmap_stage_paths.py`, `test_roadmap_implement_tool_log.py`, `test_roadmap_implement_negative_search.py`.

## Feasibility

- Each defect was reproduced first. The new tests fail on origin/main for these reasons: a raw ESC, VT, NEL, bidi override, NUL or line break in the reason; `classify_failure` gives `types` and `repair` for the reason of a refused `curl`; `StagedTree.paths_in` is empty for `src/ tests/`; the `OSError` for a long `grep`; the log line of `! Authorization: Bearer ...`.
- The corpus run (the step reader over every `tasks.md`, 554 files, 1528 commands) refuses 45 commands. Only the active change 2610 has refused lines (5), and 4 of them are prose code spans (`tagged_image`, `nginx:1.27`, `resolve_image`, `docker buildx`). So #3276 does not unblock #2610 alone. Of the 5 negative searches in the corpus, 4 are refused: `-E` (2610), repeated `-e` (3043), parentheses in a literal (3091), and quotes in a literal (3208).
- The longest verification command in the corpus is 414 characters, so a limit of 2000 for every command refuses none of them.

## Existing Tool Considered

`str.encode("unicode_escape")` and `re.escape` cover the escape and the rule, and `git ls-files` (already read by `StagedTree`) covers the paths. No library is added. The change builds about 70 lines of source and 330 lines of tests: roughly 60000 tokens to build and fix, 2500 tokens a year to keep, and about 2 hours. It deletes `_command_shown` and the alternative `command \S+ is not allowed` of the classifier.
