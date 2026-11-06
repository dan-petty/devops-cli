# Proposal

## Why

#3520 asks for two changes. The shell of the implement agent refuses every command that holds a pipe, and the refusal log writes `other` for the first word of 91 of 201 refused commands. The Job log of #2116 shows the refused commands: `git show HEAD:<file> | head -100`, `head -n 170 <file> | tail -n 20`, `ls -la <file> | head -1`, `cd <checkout> && grep ...` and `grep -n a\|b <file>`. #3271 made a refusal a normal tool result, so a refusal adds no tool retry. A refused read pipe still costs one model request and one tool call, and the model then runs the same search in two calls.

## What Changes

- A new constant `CONST_ROADMAP_IMPLEMENT_READ_PIPE_PROGRAMS` lists the programs that may stand to the right of a pipe: `head`, `tail`, `grep` and `wc`. Each one is a program of `SHELL_PROGRAMS` with access `read`.
- The shell of the agent admits a command whose pipe stages name only those programs, and refuses a pipe to any other program. The refusal names the program and the table. A stage must not redirect to a file.
- The shell of the agent admits the exact prefix `cd <checkout> &&` before a command, and runs the command without the prefix. Every other `&&` stays refused.
- `|` stays in `CONST_ROADMAP_IMPLEMENT_DENIED_OPERATORS`. The wrapper `ShellRefusal` reads that tuple. The harness gets the tuple without `|`, because it matches an operator as plain text and so cannot tell a pipe from `\|` in a `grep` pattern. The wrapper reads each pipe stage itself.
- `wc` joins `SHELL_PROGRAMS` with access `read`, so the log and the prompt know it.
- `logged_program` writes a known program by name. For any other first word it writes `other:` and the first 12 hexadecimal characters of the HMAC-SHA256 of the word, with a random key of the process, never the word. The line of a call that starts with `cd <checkout> &&` names the program after the prefix.
- `python -c` and `uv run python -c` need no change. The Job log of #2116 shows that `uv run python -c` runs. A bare `python -c` gets the refusal that names `uv run python`.
- The change modifies three requirements of `roadmap-implement-step`: the shell policy, the line of each tool call, and the bang line.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: The shell admits read pipes and the checkout prefix, and the log names a refused program or its digest

## Impact

- Code: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/implement_shell_refusal.py`, `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`
- Prompt and documents: `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_implement_read_pipe.py`, `tests/roadmap/test_roadmap_implement_shell_policy.py`, `tests/roadmap/test_roadmap_implement_tool_log.py`

## Feasibility

- The harness `pydantic-ai-harness` (installed in `.venv`, `shell/_toolset.py`, method `_first_denied_operator`) returns the first operator of `denied_operators` that is a substring of the command. It reads quotes and escapes as text. A `grep` pattern `a\|b` therefore holds `|` and is refused. The harness has no setting for a table of right-hand programs. So the wrapper `ShellRefusal`, which already wraps `call_tool`, must read the pipe stages, and the harness must not see `|`.
- `shlex.shlex(command, posix=True, punctuation_chars=True)` with `whitespace_split` was run on 18 commands. `ls|sh`, `ls "x"|sh` and `ls |sh>x` give `|` as its own token. `grep a\|b f` gives the one word `a|b`. `grep "a|b" f | wc -l` gives the word `a|b` and one `|` token. `ls |& head` gives the token `|&`. With the default comment character, `ls # | sh` hid the pipe, so the lexer needs `commenters=""`.
- The harness wraps the command as `<command>\n__harness_ec=$?\npwd > <file>\nexit $__harness_ec` (`_build_cwd_capture`). A pipe in `<command>` works with it. The tests run the real shell tool and check what reaches the process edge.
- The Job log of #2116 (comments of 2026-11-01) shows `uv run python -c <masked>` with the outcome `ok` and `python -c <masked>` with the outcome `refused`. Bare `python -c` is already a refusal with a hint, so it is outside this issue.
- The first checks are `uv run devops ci test tests/roadmap/test_roadmap_implement_read_pipe.py`, then the other test files in "Impact", then `uv run devops openspec check`.

## Existing Tool Considered

Python `shlex` from the standard library splits the command into words and pipe tokens, and it is maintained with CPython. The harness `Shell` has no table of right-hand programs. `bashlex` adds a third-party parser, and it is not needed because the policy reads only the pipe tokens. The new code is one function of about 40 lines, one constant and one message. The cost is about 15,000 tokens to build, about 2,000 tokens to keep and fix, and about 3 hours. The change deletes nothing.

## Dependencies

None.
