# Tasks

## 1. Read the declarations and the ratchet assertions of a test tree

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_registry.py`, `tests/roadmap/stage/test_roadmap_stage_registry.py`, `tests/commands/test_cli_startup_imports.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/support/fakes/roadmap_store.py`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `src/devops_cli/roadmap/stage/stage_registry.py`, `src/devops_cli/roadmap/registry_audit.py` (new), `tests/roadmap/test_registry_audit.py` (new).

- [x] 1.1 In `tests/roadmap/test_registry_audit.py`, `test_a_computed_declaration_is_reported_with_its_line` writes a module whose `REGISTRY_COUNTS` value calls a function and asserts that `audit_registries` returns that declaration with its `path:line` and no entry; it fails before `src/devops_cli/roadmap/registry_audit.py` exists
  - Verification: `$ uv run devops ci test tests/roadmap/test_registry_audit.py` fails on the base
- [x] 1.2 Add `Declaration` and `declarations_in` to `src/devops_cli/roadmap/stage/stage_registry.py`, and let `counts_in` return the entries of `declarations_in`, so one `ast` reader serves both callers and `counts_in` keeps its empty answer for a value that is no literal tuple. Add `src/devops_cli/roadmap/registry_audit.py` with `RegistryFinding`, `RegistryAudit` and `audit_registries(root: Path)`: it walks each `.py` module under `<root>/tests`, reads the module-level `REGISTRY_COUNTS` declaration, reports a value that is not a tuple or a list of literal triples with its line, collects the entries, and reports a `len(<NAME>) == <int>` assertion and a tuple of upper-case names compared with a tuple of plain integers that no entry of that module covers. An entry covers a name when its token equals the name, or its kind is `prefix` and the name starts with the token. Add to `tests/roadmap/test_registry_audit.py` the cases of an invalid declaration, a declared entry, a covered prefix, a length assertion with no entry, a limit tuple with no entry, a local list that reports nothing, a module that raises at import and is still read, and `test_the_repository_census`, which runs `audit_registries(REPO_ROOT)` and asserts the four declaring paths and 7 entries, prints each finding, and stops the group when a finding is an invalid declaration or names a declaring module outside the four
  - Verification: `$ uv run devops ci test tests/roadmap/test_registry_audit.py` passes

## 2. Add the help texts of the roadmap registries subcommand

Kind: behavior. Reads: `src/devops_cli/lang/en/help.py`, `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`. Changes: `src/devops_cli/lang/en/help.py`, `tests/commands/test_roadmap_registries.py` (new).

- [x] 2.1 In `tests/commands/test_roadmap_registries.py`, `test_the_registries_help_texts_exist` asserts that `HELP.roadmap.registries` and `HELP.roadmap.registries_path` are non-empty; it fails before the help texts exist
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_registries.py` fails on the base
- [x] 2.2 Add the help texts `registries` and `registries_path` to the catalog `src/devops_cli/lang/en/help.py:class RoadmapCommandHelp`, next to `inbox`, and create `tests/commands/test_roadmap_registries.py` with the help text test. Read `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`, the existing test that imports the catalog at `tests/ai/mcp/test_ai_benchmark_mcp_tool.py:15:from devops_cli.lang import ERRORS, HELP`: the two new attributes change none of its rows, and the step edits no line of it
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_registries.py` passes

## 3. Add the roadmap registries subcommand with its table, JSON output and exit codes

Kind: behavior. Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/roadmap_eval_grades.py`, `src/devops_cli/roadmap/registry_audit.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/output/serialization.py`, `src/devops_cli/output/formatters/tables.py`, `src/devops_cli/dry_run/decorator.py`, `tests/commands/test_roadmap_registries.py`, `tests/commands/test_all_commands_help_dryrun.py`. Changes: `src/devops_cli/commands/roadmap.py`, `tests/commands/test_roadmap_registries.py`.

- [x] 3.1 `test_a_ratchet_assertion_with_no_declaration_exits_one` in `tests/commands/test_roadmap_registries.py` runs the subcommand with `--path` on a temporary tree that holds `TABLE = ("a", "b", "c")` and `assert len(TABLE) == 3`, and asserts exit 1 and a warning with the `path:line`; the group also adds `test_the_table_lists_each_entry_of_a_tree`, `test_the_json_output_lists_each_entry`, `test_a_valid_tree_exits_zero_and_prints_the_count`, `test_the_command_lists_the_four_declaring_modules` on `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/support/fakes/roadmap_store.py` and `tests/telemetry/test_telemetry_instruments.py`, and `test_the_command_declares_the_no_external_request_class` with `get_dry_run_class`; all fail before the subcommand exists
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_registries.py` fails on the base
- [x] 3.2 Add `registries_cmd` to `src/devops_cli/commands/roadmap.py` under `@app.command("registries", help=HELP.roadmap.registries)` and `@dry_run_class("no-external-request")`, with `--path`, `--format`/`-f` and `--json`/`-j`. Resolve the format with `resolve_format`, print the table of entries with `render_table`, emit `emit_serialized` for a non-table format, print the count of valid declarations and exit 0 when there is no finding, and raise `typer.Exit(1)` when a finding exists. Add the six tests to `tests/commands/test_roadmap_registries.py`. The existing `roadmap_app` rows of `tests/commands/test_all_commands_help_dryrun.py` keep their behavior and change no line
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_registries.py` passes

## 4. Regenerate the command documents

Kind: other. Reads: `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`, `src/devops_cli/commands/roadmap.py`. Changes: `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`.

- [x] 4.1 Run `uv run devops docs generate` and commit the regenerated `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md`, which name the new `registries` subcommand of the `roadmap` group
  - Verification: `$ uv run devops docs check` passes
- [x] 4.2 Regenerate `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md` with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: `devops roadmap registries` prints the active test registry declarations in tabular format.
- Group 3: A test asserts that the command discovers all module-level `REGISTRY_COUNTS` declarations across `tests/`.
- Group 3: The command exits 0 and reports when all ratchet declarations are valid.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
