# Proposal

## Why

The stage job reads the module-level `REGISTRY_COUNTS` declarations of the test modules to find the registry and ratchet entries that a plan needs (#3332). No command lists those declarations and no command reports a ratchet assertion that no declaration covers, so a new ratchet test in `tests/invariants/` or a budget test such as `tests/commands/test_cli_startup_imports.py` can miss its declaration, and a plan then misses a required entry.

## What Changes

- Add `src/devops_cli/roadmap/registry_audit.py`, which reads the module-level `REGISTRY_COUNTS` declarations of a test tree with `ast` and reports an invalid declaration and a ratchet assertion that no declared entry covers.
- Add `Declaration` and `declarations_in` to `src/devops_cli/roadmap/stage/stage_registry.py`, so one `ast` reader serves the stage plan and the audit, and `counts_in` keeps its entries and its behavior.
- Add the `registries` subcommand to the `roadmap` group in `src/devops_cli/commands/roadmap.py`, with a table, `--format`/`-f`, `--json`/`-j`, `--path`, the count of valid declarations on exit 0 and exit 1 on a finding.
- Report a `len(<name>) == <int>` assertion and a tuple of upper-case constant names compared with plain integers, in any test module whose declarations cover no such name, with its `path:line`, and exit 1.
- Declare the `no-external-request` dry-run class on the subcommand, so the dry-run ratchet reports no unclassified command.
- Add the help texts of the subcommand and of its `--path` option to `src/devops_cli/lang/en/help.py`, and the title, the column names and the valid-audit line of the report to `src/devops_cli/lang/en/messages.py`.
- Add `tests/roadmap/test_registry_audit.py` for the scan and `tests/commands/test_roadmap_registries.py` for the command, with the exit codes, the printed count and the JSON output.
- Regenerate `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md` with `uv run devops docs generate`, and pass `uv run devops docs check`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-registries-audit`: The audit lists each declared registry entry, The audit reads the test modules without importing one, The audit lists the declarations of the test tree, A valid audit exits 0 and prints the count, The audit reports a length ratchet with no declaration, The audit reports a limit tuple with no declaration, The audit does not report a local length assertion, The audit reports a declaration that is no plain literal, The audit emits JSON with --json, The command declares the no-external-request dry-run class, The generated documents name the command

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_registry.py`, `src/devops_cli/roadmap/registry_audit.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/commands/roadmap.py`
- Documents: `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`
- Tests: `tests/roadmap/test_registry_audit.py`, `tests/commands/test_roadmap_registries.py`

## Feasibility

- The probe answers: "The path `src/devops_cli/roadmap/stage_registry.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_registry.py`. No commit in the history deleted or renamed it." The reader that the issue describes is that candidate, so the premise holds at that path, and the plan reads and changes it.
- The probe answers: "The path `tests/commands/test_roadmap_registries.py` is no file of the staging commit. No commit in the history deleted or renamed it." `list_files` of `tests/roadmap` names no `test_registry_audit.py` and `list_files` of `src/devops_cli/roadmap` names no `registry_audit.py`, so the change creates both.
- The probe answers: "The path `tests/roadmap/test_roadmap_dry_runs.py` is a file of the staging commit." and the same line for `tests/roadmap/test_roadmap_limit_classes.py`, `tests/support/fakes/roadmap_store.py` and `tests/telemetry/test_telemetry_instruments.py`.
- The set that the issue names is each module-level `REGISTRY_COUNTS` declaration under `tests/`, and it holds four modules and 7 entries. `read_file` of `tests/roadmap/test_roadmap_limit_classes.py` (lines 46-49), `tests/support/fakes/roadmap_store.py` (lines 105-107) and `tests/telemetry/test_telemetry_instruments.py` (lines 79-82) shows two, one and two entries, and the context shows two in `tests/roadmap/test_roadmap_dry_runs.py`. The plan decides each of the four as unchanged, because each declaration holds literal triples and the plan changes no declaration; the census test of group 1 asserts the four paths and the 7 entries and stops when a declaring module or an entry differs.
- The set of ratchet assertions across `tests/` is unverified: no tool of this run counts it. The census command is the `verify` of group 1, `uv run devops ci test tests/roadmap/test_registry_audit.py`; its census test prints each finding of the repository, the step records each finding in the change, and the group stops when a finding is an invalid declaration or names a declaring module outside the four. Each ratchet finding is restricted: the audit reports it with its `path:line` and exits 1, so no plan misses it.
- The reader parses a module with `ast` and imports none: `src/devops_cli/roadmap/stage/stage_registry.py:def counts_in` and `src/devops_cli/roadmap/stage/stage_registry.py:def registry_table`. Its target name is `src/devops_cli/roadmap/stage/stage_registry.py:17:_TARGET_CONSTANT: Final[str] = "REGISTRY_COUNTS"`.
- `src/devops_cli/roadmap/stage/stage_registry.py:def _extract_entries` skips an element that is not a literal triple in silence, so the audit adds `Declaration` and `declarations_in`, which report that value with its line, and `counts_in` returns the entries of `declarations_in`; the existing case `tests/roadmap/stage/test_roadmap_stage_registry.py:def test_counts_in_handles_non_tuple_and_short_entries` keeps its answer of an empty tuple.
- The declarations use the kinds `prefix` and `table`: `tests/roadmap/test_roadmap_limit_classes.py:47:("prefix", "CONST_ROADMAP_", "tests/roadmap/test_roadmap_limit_classes.py"),` and `tests/telemetry/test_telemetry_instruments.py:80:("table", "INSTRUMENTS", "src/devops_cli/telemetry/instruments.py"),`. An entry covers a name when its token equals the name, or its kind is `prefix` and the name starts with the token.
- The budget test that the issue names is `tests/commands/test_cli_startup_imports.py:def test_the_four_limits_keep_their_values`, which compares the four imported limits at `tests/commands/test_cli_startup_imports.py:104:) == (550, 75, 1100, 250)` and declares no entry. The audit therefore reports that assertion and the command exits 1 on this checkout; the exit-0 case is tested on a temporary tree, and the plan adds no declaration there because the audit's job is to report it and the count of the other such modules is unverified.
- The subcommand is a flat entry of the `roadmap` group, as `inbox` is: `src/devops_cli/commands/roadmap.py:76:app = new_typer(help=HELP.roadmap.app, no_args_is_help=True)` and `src/devops_cli/commands/roadmap.py:1045:@app.command("inbox", help=HELP.roadmap.inbox)`. A failed roadmap read exits 1 through `src/devops_cli/commands/roadmap.py:def _exit_on_failure`.
- The report commands resolve a format and print a table: `src/devops_cli/commands/roadmap_eval_grades.py:64:fmt = resolve_format(output_format, json_output=json_output)`, `src/devops_cli/output/serialization.py:def resolve_format`, `src/devops_cli/output/serialization.py:def emit_serialized` and `src/devops_cli/output/formatters/tables.py:def render_table`.
- The subcommand declares `no-external-request`, one of the values of `src/devops_cli/dry_run/decorator.py:19:CONST_DRY_RUN_CLASSES: Final[tuple[str, ...]] = ("request-plan", "no-external-request")`, through `src/devops_cli/dry_run/decorator.py:def dry_run_class`; the ratchet reads it with `src/devops_cli/dry_run/decorator.py:def get_dry_run_class` and `tests/invariants/test_dry_run_class_ratchet.py:def audit_dry_run_ratchet`.
- `src/devops_cli/commands/docs.py:def generate` declares `--output-dir`, `--format` and `--check` and no `--sync-readme`, and a `search_code` for `sync-readme` finds the option only in archived documents and in the ADR that deleted it, so the plan runs `uv run devops docs generate`.
- The help texts live in the catalog `src/devops_cli/lang/en/help.py:class RoadmapCommandHelp`, next to `inbox`; group 2 reads it and group 3 reads it again for the command decorator.
- The review finding is answered: group 2 reads the existing test of the help catalog, `tests/ai/mcp/test_ai_benchmark_mcp_tool.py:15:from devops_cli.lang import ERRORS, HELP`. The new `registries` and `registries_path` texts add attributes and change none of its rows, and the group edits no line of it.
- Preconditions of the calls: `audit_registries(root)` needs a checkout of the repository, because it reads each `.py` module under `<root>/tests`; `declarations_in(path)` needs a checkout of the repository; `registry_table(root)` needs a checkout of the repository; the subcommand needs a checkout of the repository, and no client and no network.
- The plan introduces no program. Each verify runs `uv run devops ci test` or `uv run devops docs check`, and `uv`, `devops` and `pytest` are in the runner image with no `NOT_IN_RUNNER` entry. The failure classes that apply are `test`, `lint`, `types` and `plan_defect`; the pod runs with `readOnlyRootFilesystem: true` and `runAsNonRoot: true`, and no verify writes a file.
- The first checks of the implementation are `uv run devops ci test tests/roadmap/test_registry_audit.py`, then `uv run devops ci test tests/commands/test_roadmap_registries.py`, then `uv run devops docs check`.
- The declaration of `tests/telemetry/test_telemetry_instruments.py` sits at `tests/telemetry/test_telemetry_instruments.py:79:REGISTRY_COUNTS: Final[tuple[tuple[str, str, str], ...]] = (` and not at the line 75 of the issue block, and the one of `tests/roadmap/test_roadmap_limit_classes.py` sits at `tests/roadmap/test_roadmap_limit_classes.py:46:REGISTRY_COUNTS: Final[tuple[tuple[str, str, str], ...]] = (` and not at line 41.
- Pull request #5528 changes `tests/telemetry/test_telemetry_instruments.py`, which holds one of the four declarations; this change reads that file and changes no line of it.

## Existing Tool Considered

`ast-grep` is the open, maintained structural search tool that this repository already pins and runs over the test tree, and it finds a Python pattern inside an `assert` and prints its `path:line`. It cannot split a `REGISTRY_COUNTS` entry into kind, token and target path, compare an assertion with the declarations of its own module, count the valid entries or set the exit code of a command. The audit therefore reads the modules with the Python `ast` module through `src/devops_cli/roadmap/stage/stage_registry.py` and adds no second parser. Cost of the own code: 40k tokens to build, 6k tokens a month to keep, 15k tokens to repair the first defects, and 3 hours of elapsed time.

## Dependencies

- Pull request #5528 changes `tests/telemetry/test_telemetry_instruments.py`, which holds one of the four declarations that the audit lists; this change reads that file and does not change it.
