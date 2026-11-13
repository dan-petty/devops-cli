# Proposal

## Why

Each `devops` command writes an `Elapsed:` line to stderr at exit, also when stderr is a pipe, as `src/devops_cli/main.py:32:print_muted(f"Elapsed: {format_duration(elapsed)}", to_stderr=True)` shows. An agent tool captures stdout and stderr together, so the line enters the agent context on almost every call, and a `2>&1` JSON pipe fails with `JSONDecodeError: Extra data`. #5448 keeps the line for a person at a terminal and removes it from every other stderr.

## What Changes

- Guard the exit hook in `src/devops_cli/main.py` with `sys.stderr.isatty()`, so the elapsed line reaches a terminal only.
- Add `tests/invariants/test_cli_elapsed_line.py` with three cases that run the CLI as a child process: stderr in a pipe, `FORCE_COLOR=1` and `TTY_COMPATIBLE=1` with a pipe, and stderr on a pseudo-terminal; the two pipe cases fail on the base.
- Add the new module name to the invariant test list in `docs/TESTING.md`.
- Add a case to `tests/telemetry/test_telemetry_instruments.py` that runs a command and reads one `devops_cli_subcommand_duration_seconds` point through the `otlp` fake.
- Remove the elapsed-line cause from the JSON section of `CONTRIBUTING.md` and keep the uv bytecode and zsh echo warnings.
- Add the terminal rule to the `console-output` capability and update the `command-error-exit` requirement that names the elapsed line.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `console-output`: The elapsed line goes only to a terminal
- `command-error-exit`: A command run from a deleted working directory stops with one error line

## Impact

- Code: `src/devops_cli/main.py`
- Documents: `docs/TESTING.md`, `CONTRIBUTING.md`
- Tests: `tests/invariants/test_cli_elapsed_line.py`, `tests/telemetry/test_telemetry_instruments.py`

## Feasibility

- `probes` reports "The path `src/devops_cli/main.py` is a file of the staging commit." and "The path `CONTRIBUTING.md` is a file of the staging commit.", so the two paths the issue cites exist at the staged commit and the premise of the issue holds.
- `probes` reports "The path `Console.is_terminal` is no file of the staging commit.", so the Rich property that the issue rejects is no repository path, and the change touches no file for it.
- `search_code` with `_print_elapsed` returned two lines, `src/devops_cli/main.py:27:def _print_elapsed() -> None:` and `src/devops_cli/main.py:35:atexit.register(_print_elapsed)`, so no test calls the hook today.
- `src/devops_cli/main.py:32:print_muted(f"Elapsed: {format_duration(elapsed)}", to_stderr=True)` is the write that the issue cites, and the hook guards it with no terminal check, which is the defect.
- The finding on the missing test of the changed module is fixed: `search_code` with `devops_cli.main import app` returned `tests/ai/ast/test_treesitter_engine.py:17:from devops_cli.main import app`, so group 1 now lists that importing test in `reads`.
- `search_code` with `from devops_cli import main` returned `tests/invariants/test_dry_run_class_ratchet.py:20:from devops_cli import main as main_module`, and `search_code` with `devops_cli.main as main_module` returned `tests/ai/mcp/test_mcp_tool_argv.py:436:import devops_cli.main as main_module`, so group 1 lists both importing tests in `reads` too and changes neither.
- `docs/TESTING.md:95` holds the list of invariant test files, `tests/invariants/test_source_tree.py:717:def _read_testing_md_invariant_subjects(doc_path: Path) -> frozenset[str]:` parses that list, and `tests/invariants/test_source_tree.py:730: allowed = _read_testing_md_invariant_subjects(testing_md)` fails on an invariant file that the doc does not list, so group 1 adds the new module name there.
- `_print_elapsed()` takes no argument; it reads the module's `_timing` start entry and writes through `print_muted` to `sys.stderr`, so it needs no checkout, no client and no network.
- `docs/TESTING.md:85` says "No test patches a devops-cli module, class, function or attribute, and no test imports a private name (one that starts with `_`) from `devops_cli`", so no test imports the hook or its timing table and the tests reach the hook through the CLI process.
- `tests/support/cli.py:14:def cli() -> Callable[..., Any]:` runs the app in process with `CliRunner`, which never runs the `atexit` hook, so the pipe and pseudo-terminal cases start the CLI as a child process.
- `src/devops_cli/entry.py:28:def main(argv: list[str] | None = None) -> None:` is the child entry, and `tests/commands/test_telemetry_profile.py:205: ) == (0, [sys.executable, "-P", "-m", "devops_cli.entry", "version"], False)` shows the child command shape of the project.
- `tests/invariants/test_hermetic_floor.py:873:@pytest.mark.live("python")` marks a test that starts a python child, which the floor allows, and the runner image holds `python` and `python3`.
- The child gets `PYTHONPATH` set to `src` under `REPO_ROOT` of `tests/support/paths.py`, so it imports the source of the tree under test and the replay of `devops ci fail-to-pass --base origin/main` runs the base source, where the line still prints.
- `src/devops_cli/telemetry/tracer.py:1665:if not sys.stderr.isatty():` already guards the export warning with the same call, so the guard uses the standard library call the repository already trusts.
- `src/devops_cli/core/cli.py:46:emit(SUBCOMMAND_DURATION, dur, {**labels, "status": "ok"})` sends the sub-command duration inside the command span, and `src/devops_cli/telemetry/instruments.py:54:SUBCOMMAND_DURATION = Instrument(` declares it, so the guard of the printed line leaves both unchanged.
- `src/devops_cli/telemetry/instruments.py:875:def emit(instrument: Instrument, value: float, attributes: dict[str, Any] | None = None) -> None:` records on the process tracer, so the duration case reads the export through the OTLP fake instead of replacing `emit`.
- `docs/TESTING.md:248:Telemetry export is off unless a test opts in with the OTLP fake` gives the fake, and `tests/telemetry/test_telemetry_instruments.py:1026:def test_a_histogram_observation_lands_in_its_bucket(otlp: FakeCollector) -> None:` is the existing case that reads one metric through it, so group 2 follows that pattern.
- `tests/telemetry/test_telemetry_instruments.py:68:from tests.support.fakes.otlp import FakeCollector` imports the fake, and the duration case runs `devops config show --format json` through `tests/support/cli.py:14:def cli() -> Callable[..., Any]:`, a command that reads settings and reaches no network.
- `tests/telemetry/test_telemetry_instruments.py:79:("prefix", "devops_cli_", "src/devops_cli/telemetry/instruments.py"),` is the registry entry of the `devops_cli_` prefix, so group 2 names `src/devops_cli/telemetry/instruments.py` as the declared registry place and reads the declaration without changing it.
- `tests/conftest.py:132: "devops_cli.main": ("reset_timing",),` clears the recorded start after each test, so each test starts from no timing entry and the child process records its own start before it exits.
- `search_code` with `Elapsed:` returned 21 lines, and exactly one of them sits in `CONTRIBUTING.md`, at `CONTRIBUTING.md:131:breaks in two ways`, the JSON section that group 3 rewrites.
- `references` with `Elapsed` returned 25 files and 26 lines, and no file of the answer sits under `.claude/`, `.agents/` or `.kilocode/`, so no agent brief or skill tells agents to filter the line; each other file is covered by a design decision or by a group.
- `src/devops_cli/output/console.py:470:def print_muted(` writes the line through the cached stderr console, which reads `sys.stderr` at write time, so the change edits no file of the output package.
- `subprocess.run([sys.executable, "-P", "-m", "devops_cli.entry", "gh", "--help"])` needs a checkout of the repository and a python child, and it starts no client and reaches no network.
- `_delegate()` needs a checkout of the repository, because `require_working_directory()` runs before a command that is no help query; the child runs `gh --help`, which skips that check.
- `pty.openpty()` needs the device file `/dev/ptmx` of the host and no checkout, no client and no network, and the pseudo-terminal case skips with that reason when the call raises `OSError`.
- The plan introduces no program: `python`, `python3`, `git` and `uv` are runner tools, and the new tests start no client, so no `NOT_IN_RUNNER` entry applies.
- A failed test stops a step with class `test`, a ruff finding with `lint` and a mypy finding with `types`; the new tests write no file and open no socket, so `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault` hold.
- The first checks of the implementation are `uv run devops ci test tests/invariants/test_cli_elapsed_line.py`, which must fail on the base before the guard lands, and `uv run devops ci fail-to-pass --base origin/main` after it.
- `uv run devops ci test tests/telemetry/test_telemetry_instruments.py` needs a checkout of the repository, and the `otlp` fake replaces the exporter, so the duration case reaches no network.

## Existing Tool Considered

The Python standard library's `sys.stderr.isatty()`, which `src/devops_cli/telemetry/tracer.py:1665:if not sys.stderr.isatty():` already uses to keep a non-interactive run quiet, the standard library `pty` module for the pseudo-terminal case, and the `otlp` fixture's `FakeCollector` for the duration case. No new dependency and no new tool.

## Dependencies

- The metric `devops_cli_subcommand_duration_seconds` also appears in `docs/TELEMETRY.md`; the plan leaves that document unchanged and only guards the printed elapsed line.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `k8s/devops/dashboards/devops-cli.json`; the plan changes no dashboard panel.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `openspec/changes/archive/2026-10-28-817-metrics-through-instruments/design.md`; an archived change stays as it is.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `openspec/changes/archive/2026-10-29-2700-sub-command-dashboard/design.md`; an archived change stays as it is.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `openspec/changes/archive/2026-10-29-2700-sub-command-dashboard/proposal.md`; an archived change stays as it is.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `openspec/changes/archive/2026-10-29-2700-sub-command-dashboard/specs/command-telemetry/spec.md`; an archived delta stays as it is.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `openspec/changes/archive/2026-11-05-2479-service-dashboard-row-job-variable/specs/command-telemetry/spec.md`; an archived delta stays as it is.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `openspec/changes/archive/2026-11-12-4707-make-the-github-and-command-panels/proposal.md`; an archived change stays as it is.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `openspec/changes/archive/2026-11-12-4707-make-the-github-and-command-panels/specs/command-telemetry/spec.md`; an archived delta stays as it is.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `openspec/changes/archive/2026-11-12-4707-make-the-github-and-command-panels/specs/devops-cli-dashboard/spec.md`; an archived delta stays as it is.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `openspec/changes/archive/2026-11-13-5292-split-the-product-dashboards-and-rules/specs/command-telemetry/spec.md`; an archived delta stays as it is.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `openspec/specs/command-telemetry/spec.md`; the plan adds no requirement there and keeps the metric unchanged.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `openspec/specs/devops-cli-dashboard/spec.md`; the plan changes no dashboard requirement.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `src/devops_cli/ai/knowledge_base/it_domains/tools/prometheus.md`; the knowledge-base text stays as it is.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `src/devops_cli/core/cli.py`; the plan changes no caller of the metric.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `src/devops_cli/telemetry/instruments.py`; the instrument and its name stay as they are, and group 2 names that path in its task.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `tests/fixtures/dashboard_queries/devops-cli.yaml`; the fixture stays as it is.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `tests/grafana/test_grafana_dashboards.py`; the plan changes no dashboard query.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `tests/prometheus/test_k8s_monitoring_dashboards.py`; the plan changes no dashboard rule.
- The metric `devops_cli_subcommand_duration_seconds` also appears in `tests/telemetry/test_telemetry_instruments.py`; group 2 adds a duration case to that file and changes no instrument.
