# Tasks

## 1. A span starts without VCS attributes when the working directory is gone

Reads: `src/devops_cli/telemetry/tracer.py` (lines 627-660, `_resolve_git_dir` and `_detect_vcs_metadata`; lines 855-870, where the client reads them), `tests/telemetry/test_telemetry.py` (the `collector` fixture and `test_span_vcs_and_k8s_attributes_detection`). Changes: `src/devops_cli/telemetry/tracer.py`, `tests/telemetry/test_telemetry.py`.

- [ ] 1.1 In `tests/telemetry/test_telemetry.py`, write the tests first. They use the public interface only: no patch of a devops-cli name and no import of a private name. Annotate every test with `-> None`, because `mypy --strict` covers `tests/`. Call `reset_tracer()` before and after each test, because it clears the cache of `_detect_vcs_metadata`.
  - Test A: make `tmp_path / "gone"`, change into it with `monkeypatch.chdir`, remove it with `rmdir`, start `OTelTelemetryClient(endpoint=collector, enabled=True).span(...)`, and assert that no attribute key starts with `vcs.`.
  - Test B: build `tmp_path / ".git"` with a `HEAD` file `ref: refs/heads/feat/example`, and a branch file `refs/heads/feat/example` that holds a 40-character revision. Change into `tmp_path` and start a span. Assert `vcs.ref.name`, `vcs.branch`, `vcs.revision_id` and `vcs.commit`.
  - Run `uv run devops ci test tests/telemetry/test_telemetry.py`. Test A must fail on the base with `FileNotFoundError` from `Path.cwd()`. Test B passes on the base: it pins the behavior that must not change.
- [ ] 1.2 In `_resolve_git_dir`, return `None` when `(start_dir or Path.cwd()).resolve()` raises `OSError`. Leave the walk over the parent directories as it is. Verify that `uv run devops ci test tests/telemetry/test_telemetry.py` passes.

## 2. A command run from a deleted working directory stops with one error line

Reads: `src/devops_cli/core/cli.py` (the whole file, 10 KB), `tests/commands/test_command_error_exit.py` (2.7 KB), `ARCHITECTURE.md` (section 7, the exit seam). Changes: `src/devops_cli/core/cli.py`, `tests/commands/test_command_error_exit.py`, `ARCHITECTURE.md`.

- [ ] 2.1 In `tests/commands/test_command_error_exit.py`, write the tests first, in the style of the file. Annotate every test with `-> None`.
  - Test A: an app from `new_typer()` with a command whose body records that it ran. Change into a directory of `tmp_path`, remove it, and invoke the command with `CliRunner`. Assert exit status 1, one non-empty output line that holds `The working directory does not exist.`, no `Traceback`, and that the body did not run.
  - Test B: the same removed directory, and `cli("gh", "--help")` from the shared `cli` fixture. Assert exit status 0 and `Usage: devops gh` in the output.
  - Run `uv run devops ci test tests/commands/test_command_error_exit.py`. Test A must fail on the base because the body runs or the tracer raises `FileNotFoundError`. Test B passes on the base: it pins the help of a group.
- [ ] 2.2 In `OTelTyper.command`, in `traced_fn` and inside `_report_devops_error()`, call `os.getcwd()` before `_execute_traced_cli_command`. On `FileNotFoundError`, raise `DevOpsCLIError("The working directory does not exist. Change to a directory that exists and run the command again.")`. Do not add the check to `callback` or to `_report_devops_error`. Verify that `uv run devops ci test tests/commands/test_command_error_exit.py` passes.
- [ ] 2.3 In the paragraph "The one exit seam" of `ARCHITECTURE.md`, add one sentence: a command of a `new_typer()` app stops with one error line and exit status 1 when the working directory of the process no longer exists, and its body does not run. Run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes.
- [ ] 2.4 Verify the whole change with these steps. First, run `mkdir /tmp/gone && cd /tmp/gone && rmdir /tmp/gone`. Second, run `<repository>/.venv/bin/devops gh api rate_limit` from `/tmp/gone` (`uv run` itself fails in a removed directory). It prints `The working directory does not exist.` and exits with status 1. Third, run `<repository>/.venv/bin/devops gh --help` from `/tmp/gone`. It prints the help.
