# Tasks

## 1. Guard the elapsed line with the stderr terminal check

Kind: behavior. Reads: `src/devops_cli/main.py`, `docs/TESTING.md`, `tests/invariants/test_source_tree.py`, `tests/support/cli.py`, `tests/support/paths.py`, `tests/commands/test_telemetry_profile.py`, `src/devops_cli/entry.py`, `tests/ai/ast/test_treesitter_engine.py`, `tests/invariants/test_dry_run_class_ratchet.py`, `tests/ai/mcp/test_mcp_tool_argv.py`. Changes: `src/devops_cli/main.py`, `tests/invariants/test_cli_elapsed_line.py` (new), `docs/TESTING.md`.

- [x] 1.1 `test_a_pipe_gets_no_elapsed_line` in `tests/invariants/test_cli_elapsed_line.py` fails on the base, whose child writes the elapsed line into the piped stderr
  - Verification: `$ uv run devops ci test tests/invariants/test_cli_elapsed_line.py` fails on the base
- [x] 1.2 Add `import sys` to `src/devops_cli/main.py` and return from `print_elapsed` (public, see design.md) when `sys.stderr.isatty()` is false, before it prints. Write `tests/invariants/test_cli_elapsed_line.py` with one helper that runs `[sys.executable, "-P", "-m", "devops_cli.entry", "gh", "--help"]` through `subprocess.run`, with `cwd` and `PYTHONPATH` set from `REPO_ROOT` of `tests/support/paths.py`, and mark each case `@pytest.mark.live("python")`. `test_a_pipe_gets_no_elapsed_line` captures the child's stderr in a pipe and asserts that it holds no `Elapsed:` line. `test_force_color_with_a_pipe_gets_no_elapsed_line` sets `FORCE_COLOR=1` and `TTY_COMPATIBLE=1` in the child environment, keeps the pipe, and asserts the same; both fail on the base, whose child prints the line. `test_a_pseudo_terminal_gets_the_elapsed_line` opens a pair with `pty.openpty()`, runs the child with `stderr` the slave descriptor, closes the slave in the parent, reads the master to its end, and asserts that the output holds the `Elapsed:` line; it skips with a reason that names the missing pseudo-terminal when `openpty()` raises `OSError`. The three existing tests that import the changed module, `tests/ai/ast/test_treesitter_engine.py`, `tests/invariants/test_dry_run_class_ratchet.py` and `tests/ai/mcp/test_mcp_tool_argv.py`, keep their assertions, because the guard changes no name that they import. Add `test_cli_elapsed_line.py` to the invariant test list in `docs/TESTING.md`, the list that the source-tree invariant test reads
  - Verification: `$ uv run devops ci test tests/invariants/test_cli_elapsed_line.py` passes
- [x] 1.3 Edit `docs/TESTING.md` to add `test_cli_elapsed_line.py` to the list of invariant test files
  - Verification: `$ uv run devops ci docs` passes

## 2. Prove the sub-command duration survives a piped stderr

Kind: other. Reads: `tests/telemetry/test_telemetry_instruments.py`, `tests/support/fakes/otlp.py`, `tests/support/cli.py`, `src/devops_cli/core/cli.py`, `src/devops_cli/telemetry/instruments.py`. Changes: `tests/telemetry/test_telemetry_instruments.py`.

- [x] 2.1 Add `test_a_piped_command_still_emits_its_subcommand_duration` to `tests/telemetry/test_telemetry_instruments.py` with the `cli` and `otlp` fixtures: run `devops config show --format json`, whose stderr is the runner's pipe, then read `otlp.metrics` and assert that exactly one entry is named `devops_cli_subcommand_duration_seconds` and that its point holds the labels `command` of `config` and `status` of `ok`. `src/devops_cli/telemetry/instruments.py` declares that histogram as `SUBCOMMAND_DURATION` and holds the `devops_cli_` prefix entry of the registry counts; the case reads both and changes no line of that file, and changes no dashboard
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes

## 3. Drop the elapsed workaround from the contributing guide

Kind: other. Reads: `CONTRIBUTING.md`. Changes: `CONTRIBUTING.md`.

- [x] 3.1 Rewrite point 3 of the shell notes in `CONTRIBUTING.md`, at the line that says JSON from `uv run devops gh api` breaks in two ways: remove the sentence that says the command writes an `Elapsed:` line to stderr and every word that refers to it, name the uv `Bytecode compiled` line as the remaining stderr cause, keep the zsh `echo` escape warning and the wrong `2>&1` example with a comment that names the uv line only
  - Verification: `$ ! git grep -n -F Elapsed: CONTRIBUTING.md` passes
- [x] 3.2 Edit `CONTRIBUTING.md` to remove the elapsed-line cause from its JSON section and keep the uv bytecode and zsh echo warnings
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test runs a command with stderr in a pipe and proves that stderr holds no `Elapsed:` line. The test fails on the base.
- Group 1: A test with stderr on a pseudo-terminal proves that the line is still there.
- Group 1: A test proves that `FORCE_COLOR=1` with stderr in a pipe gives no line.
- Group 1: `uv run devops ci fail-to-pass --base origin/main` shows that the new tests fail on the base.
- Group 2: Measure in telemetry: `devops_cli_subcommand_duration_seconds` still records each command after the change, so no duration is lost.
- Pending person: Measure in the agent transcripts, 7 days after the release: the share of `devops` results that hold `Elapsed:` goes to 0, and new `grep -v Elapsed` filters go down., Only a person can read the Claude Code transcripts of the 7 days after the release, and no command of the repository holds them.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
