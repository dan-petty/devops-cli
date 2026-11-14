# Tasks

## 1. Generate a subcommand for each row of the check registry

Kind: behavior. Reads: `src/devops_cli/commands/ci.py`, `tests/commands/test_ci_dry_run.py`, `tests/invariants/test_dry_run_class_ratchet.py`. Changes: `src/devops_cli/commands/ci.py`, `tests/commands/test_ci_row_commands.py` (new).

- [ ] 1.1 The case `test_a_row_command_plans_only_its_row` runs the row constructs and the row test-tree, each with `--dry-run`, and fails on the base, where neither word is a command of the `ci` group; the case `test_the_row_tuple_matches_the_registry` compares `CHECK_ROW_NAMES` with `get_check_specs()` and fails on the base
  - Verification: `$ uv run devops ci test tests/commands/test_ci_row_commands.py` fails on the base
- [ ] 1.2 Add `CHECK_ROW_NAMES` to `src/devops_cli/commands/ci.py` as the 25 row names in registry order. Add `_row_command(name)`, which returns a command decorated with `@dry_run_class("request-plan")` and the `--dry-run` option: it sets the dry run, reads `get_check_spec(name)`, runs `_run_all_checks_async` for that one spec inside `_gate_slot(spec.heavy)`, prints the failures and the summary, and exits 1 when a result failed. At the end of the module, register one generated command for each name that `app.registered_commands` does not already hold, and bind the name as a default argument of the closure so the import stays lazy
  - Verification: `$ uv run devops ci test tests/commands/test_ci_row_commands.py` passes

## 2. Select rows by name and name them in the option help

Kind: behavior. Reads: `src/devops_cli/commands/ci.py`, `src/devops_cli/telemetry/usage_errors.py`, `src/devops_cli/core/cli.py`, `tests/commands/test_ci.py`. Changes: `src/devops_cli/commands/ci.py`, `tests/commands/test_ci_row_commands.py`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`.

- [ ] 2.1 The case `test_a_misspelled_only_name_records_bad_value` runs the root CLI with `ci --only constructz` and fails on the base, where the run exits 2 with no ledger record; the case `test_a_misspelled_skip_name_records_bad_value` runs `ci --skip constructz`; the case `test_the_selection_help_names_the_rows` reads the help of `--only` and `--skip` and fails on the base
  - Verification: `$ uv run devops ci test tests/commands/test_ci_row_commands.py` fails on the base
- [ ] 2.2 Add `_row_name_callback` to `src/devops_cli/commands/ci.py`: it splits each value at the commas, checks each name against `CHECK_ROW_NAMES`, raises `typer.BadParameter` with up to 3 names from `difflib.get_close_matches` and the valid names, and returns the value unchanged. Pass it as `callback=` to the `--only` and `--skip` options and set their help from `CHECK_ROW_NAMES`. Leave `resolve_selected_specs` as it is. Give the new cases a ledger fixture of their own that reads the JSON lines of the usage ledger. Regenerate the MCP tool listing snapshot with its `--snapshot-update` run, because the snapshot holds the old help of both options
  - Verification: `$ uv run devops ci test tests/commands/test_ci_row_commands.py` passes

## 3. Delete the run command and its old test cases

Kind: behavior. Reads: `src/devops_cli/commands/ci.py`, `tests/commands/test_ci_dry_run.py`, `tests/commands/test_net_construct_rules.py`, `tests/commands/test_ci_row_commands.py`. Changes: `src/devops_cli/commands/ci.py`, `tests/commands/test_ci_dry_run.py`, `tests/commands/test_net_construct_rules.py`, `tests/commands/test_ci_row_commands.py`.

- [ ] 3.1 The case `test_the_removed_run_command_records_unknown_command` runs the root CLI with `ci run` and fails on the base, where the run exits 0 and starts the gate
  - Verification: `$ uv run devops ci test tests/commands/test_ci_row_commands.py` fails on the base
- [ ] 3.2 Delete the `run` command from `src/devops_cli/commands/ci.py` with its options and its `@dry_run_class` line. Delete the case `test_ci_run_command_dry_run` from `tests/commands/test_ci_dry_run.py`. Remove the second invocation of the removed command from `test_ci_dry_run_unlinks_nothing`, with its docstring. Reword the docstring of `tests/commands/test_net_construct_rules.py` so that it names the constructs row and `CONST_AST_GREP_SCAN_ARGS`. Add the case `test_the_removed_run_command_records_unknown_command` to `tests/commands/test_ci_row_commands.py`
  - Verification: `$ uv run devops ci test tests/commands/test_ci_row_commands.py` passes

## 4. Name no removed command in the gate-slot metric description

Kind: behavior. Reads: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/telemetry/test_consolidation_serialization.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [ ] 4.1 The case `test_the_gate_slot_histogram_description_names_no_command` in `tests/telemetry/test_telemetry_instruments.py` reads the description of `CI_GATE_SLOT_WAIT` and fails on the base, whose text holds the removed command name
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` fails on the base
- [ ] 4.2 Set the description of `CI_GATE_SLOT_WAIT` in `src/devops_cli/telemetry/instruments.py` to `Time a gate run waited for a free gate slot before its checks started`. Add the case `test_the_gate_slot_histogram_description_names_no_command` beside `test_the_roadmap_tool_instruments_are_declared_with_their_kinds_and_units`: it asserts that the description equals that text, so the description names no command and holds no removed command name
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes

## 5. Regenerate the documents after the removal and the new description

Kind: other. Reads: `README.md`, `docs/TELEMETRY.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ci.md`, `docs/MCP_TOOLS.md`, `src/devops_cli/ai/knowledge_base/devops_cli/cli_command_reference.md`. Changes: `README.md`, `docs/TELEMETRY.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ci.md`, `docs/MCP_TOOLS.md`, `src/devops_cli/ai/knowledge_base/devops_cli/cli_command_reference.md`.

- [ ] 5.1 Write `devops ci` in place of the removed command in the quick-start block of `README.md`. Delete the row of the removed command from the table of `src/devops_cli/ai/knowledge_base/devops_cli/cli_command_reference.md`. Run `uv run devops docs generate` to regenerate `docs/TELEMETRY.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ci.md` and `docs/MCP_TOOLS.md` from the app and from the instrument descriptions, so that the gate-slot row holds the new description and no document names the removed command, and run this check by hand: Run `uv run devops docs generate`. Run `uv run devops docs check` and confirm that it reports every documentation file as up to date. Run `git grep -n -F -w 'devops ci run' -- README.md docs/ src/` and confirm that it finds no match. Confirm that the row of `devops_cli_ci_gate_slot_wait_seconds` in `docs/TELEMETRY.md` reads the description of `CI_GATE_SLOT_WAIT`.
- [ ] 5.2 Edit `README.md` and `src/devops_cli/ai/knowledge_base/devops_cli/cli_command_reference.md`, and regenerate `docs/TELEMETRY.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ci.md` and `docs/MCP_TOOLS.md`
  - Verification: `$ uv run devops ci docs` passes

## 6. Name the scoped rows in the implement prompt table

Kind: behavior. Reads: `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `src/devops_cli/config/constants.py`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`. Changes: `src/devops_cli/roadmap/implement/implement_shell_policy.py`, `docs/ROADMAP_WORKFLOW.md`, `tests/roadmap/implement/test_roadmap_implement_shell_policy.py`.

- [ ] 6.1 The case `test_the_local_commands_are_the_eight_commands_of_the_project_and_none_uses_the_network` reads `LOCAL_COMMANDS` and fails on the base, because the table holds no row of `ci` besides `ci test`; `test_the_document_of_the_workflow_holds_the_same_tables` compares the text of `local_commands_table()` with `docs/ROADMAP_WORKFLOW.md`; and `test_each_local_command_is_a_command_of_the_devops_app` runs `--help` for each of the eight commands
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_policy.py` fails on the base
- [ ] 6.2 Add `LocalCommand(("ci", "constructs"), ShellAccess.READ, ...)`, `LocalCommand(("ci", "docs"), ShellAccess.READ, ...)` and `LocalCommand(("ci", "openspec"), ShellAccess.READ, ...)` to `LOCAL_COMMANDS` in `src/devops_cli/roadmap/implement/implement_shell_policy.py`, each naming the row that it runs and carrying the argv `ci` with that row name. Replace the table of `docs/ROADMAP_WORKFLOW.md` with the text that `local_commands_table()` renders. Rename the case that counts the five commands to the eight commands and update the cases that hold the old names
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_shell_policy.py` passes
- [ ] 6.3 Edit `docs/ROADMAP_WORKFLOW.md` with the table that `local_commands_table()` renders
  - Verification: `$ uv run devops ci docs` passes

## 7. Search the tracked files for the removed command

Kind: other. Reads: `tests/commands/test_ci_row_commands.py`, `README.md`, `docs/TELEMETRY.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ci.md`, `docs/MCP_TOOLS.md`, `src/devops_cli/ai/knowledge_base/devops_cli/cli_command_reference.md`, `src/devops_cli/telemetry/instruments.py`. Changes: `tests/commands/test_ci_row_commands.py`.

- [ ] 7.1 Add the case `test_no_other_file_names_the_removed_command` to `tests/commands/test_ci_row_commands.py`: it runs `git grep -n -I -F -w -l` for the removed command name over `README.md`, `docs/`, `src/` and `tests/`, leaves its own file out, and asserts that no line comes back. The case runs on the head only, after groups 3 to 5 removed the name from the code, the metric description and the documents
  - Verification: `$ uv run devops ci test tests/commands/test_ci_row_commands.py` passes

## Criteria

- Group 1: A test (written first, fails on the base) runs `devops ci constructs --dry-run` and `devops ci test-tree --dry-run` and proves that each selects only its row.
- Group 2: A test runs `devops ci --only constructs,openspec --dry-run` and proves that both rows run.
- Group 2: A test runs `devops ci --only constructz` and proves exit code 2, a close-name hint `constructs`, and one `cli_usage_error` record of kind `bad_value`.
- Group 1: A test proves that the static row tuple equals the names from `get_check_specs()`.
- Group 3: `devops ci run` exits 2 as an unknown command, and no document names it (`git grep` in the test).
- Pending person: `uv run devops ci fail-to-pass --base origin/main` shows that the new tests fail on the base., The replay runs on the pull request after every group has written its test, so no group of this change runs it; the Fail-to-Pass Check runs it on the pull request.
- Pending person: Measure in telemetry, 7 days after the release: `cli_usage_error` records with command path `ci` and kind `unknown_command` or `bad_value` go to near 0 (Loki). In implement runs, `ci` help calls and wrong `ci` forms per run go down (runner log lines)., The measurement reads Loki and the runner logs 7 days after the release, which no group of this change can run.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
