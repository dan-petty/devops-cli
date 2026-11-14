# Tasks

## 1. Add the toolset option to the eval stage command

Kind: behavior. Reads: `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/roadmap/stage/stage_eval_run.py`, `src/devops_cli/roadmap/stage/stage_eval_render.py`, `src/devops_cli/roadmap/stage/stage_eval_score.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`, `tests/roadmap/stage/test_roadmap_stage_eval_run.py`, `tests/roadmap/stage/test_roadmap_stage_gate_extension.py`, `tests/roadmap/stage/test_roadmap_stage_eval_facts_context.py`, `tests/roadmap/stage/test_roadmap_stage_measure.py`, `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/roadmap/stage/stage_eval_run.py`, `src/devops_cli/roadmap/stage/stage_eval_render.py`, `src/devops_cli/roadmap/stage/stage_eval_score.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`.

- [ ] 1.1 `test_the_toolset_option_names_the_toolset_in_the_report` in `tests/roadmap/stage/test_roadmap_stage_eval_command.py` fails: the report of a score with the toolset `base` names no toolset
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_command.py` fails on the base
- [ ] 1.2 Add `--toolset` to `eval_stage_cmd` in `src/devops_cli/commands/roadmap_eval_stage.py` with the value `StageToolset`, defaulted from `roadmap.stage.toolset`, and pass it through `_run` and `run_cases` of `src/devops_cli/roadmap/stage/stage_eval_run.py` to the `toolset` argument of `ToolboxClient` in `run_case`, so each plan run reads the tools of that toolset. Add a `toolset` field to `StageScore` in `src/devops_cli/roadmap/stage/stage_eval_score.py`, print it on the title line of `render_score` in `src/devops_cli/roadmap/stage/stage_eval_render.py`, and write it in `score_json`. Add the help text to `src/devops_cli/lang/en/help.py` and the message to `src/devops_cli/lang/en/messages.py`, and update the assertions of the eval test modules that read the rendered report
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_command.py` passes

## 2. Build the comparison engine and its table

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_eval_run.py`, `src/devops_cli/roadmap/stage/stage_eval_score.py`, `src/devops_cli/roadmap/stage/stage_eval_usage.py`, `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `tests/roadmap/stage/test_roadmap_stage_eval_run.py`, `tests/roadmap/stage/test_roadmap_stage_eval_facts_context.py`, `tests/support/fakes/model.py`. Changes: `src/devops_cli/roadmap/stage/stage_eval_compare.py` (new), `src/devops_cli/roadmap/stage/stage_eval_run.py`, `tests/roadmap/stage/test_roadmap_stage_eval_compare.py` (new).

- [ ] 2.1 `test_the_engine_measures_each_toolset` in `tests/roadmap/stage/test_roadmap_stage_eval_compare.py` fails: `run_case` of `src/devops_cli/roadmap/stage/stage_eval_run.py` takes no trace list and returns no plan, and no module measures a toolset
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_compare.py` fails on the base
- [ ] 2.2 Add `Measure` to `src/devops_cli/roadmap/stage/stage_eval_compare.py` for one run of one case, with its case name, gate defects, verification defects, tool calls, requests, input tokens, output tokens, elapsed seconds and cost. Add `run_toolset`, which runs `run_case` of `src/devops_cli/roadmap/stage/stage_eval_run.py` for each case with the toolset and a trace list, sums the `RunTrace` counters of `src/devops_cli/roadmap/agent_run.py`, times the run, and prices the tokens with `RunUsage.spend_usd` of `src/devops_cli/roadmap/stage/stage_eval_usage.py`. Give `run_case` an optional `traces` list, passed to the `traces` keyword of `ToolboxClient` of `src/devops_cli/roadmap/stage/stage_toolbox.py`, and a `plan` field on `CaseRun`, so the caller reads the trace and the reply of each run. Add `ComparisonRow`, `spread` (the minimum and the maximum), `delta` (the value less the value of the first row) and `render_compare`, which prints one row for each toolset with the eight columns
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_compare.py` passes

## 3. Add the compare form to the command

Kind: behavior. Reads: `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/roadmap/stage/stage_eval_compare.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/support/fakes/model.py`. Changes: `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/roadmap/stage/stage_eval_compare.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_eval_compare.py`.

- [ ] 3.1 `test_the_compare_form_prints_one_table_with_a_fake_client` in `tests/roadmap/stage/test_roadmap_stage_eval_compare.py` fails: `eval_stage_cmd` in `src/devops_cli/commands/roadmap_eval_stage.py` refuses the positional `compare` and the two toolset names
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_compare.py` fails on the base
- [ ] 3.2 Add a positional list argument to `eval_stage_cmd` in `src/devops_cli/commands/roadmap_eval_stage.py`. When its first token is `compare`, read the rest as toolset names, refuse fewer than two with a message that names the option, and call `run_toolset` of `src/devops_cli/roadmap/stage/stage_eval_compare.py` for each name over the cases that `load_cases` and `select_cases` pick. Print `render_compare` of the rows. A name that is no value of `StageToolset` raises `ConfigurationError` with the names of the setting. Add the help text to `src/devops_cli/lang/en/help.py` and the messages to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_compare.py` passes

## 4. Run each case three times and show the spread

Kind: behavior. Reads: `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/roadmap/stage/stage_eval_compare.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/support/fakes/model.py`. Changes: `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/roadmap/stage/stage_eval_compare.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_eval_compare.py`.

- [ ] 4.1 `test_three_runs_state_the_count_and_the_spread` in `tests/roadmap/stage/test_roadmap_stage_eval_compare.py` fails: `eval_stage_cmd` in `src/devops_cli/commands/roadmap_eval_stage.py` takes no `--runs`, each case runs once, and the table states no spread
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_compare.py` fails on the base
- [ ] 4.2 Add `--runs` to the compare form of `eval_stage_cmd` in `src/devops_cli/commands/roadmap_eval_stage.py` with a minimum of 1 and a default of 3, and run each case that many times for each toolset in `run_toolset` of `src/devops_cli/roadmap/stage/stage_eval_compare.py`. Sum the measures of a toolset for its row, and add a line for each case with its number of runs and the minimum and the maximum of its tool calls, requests, input and output tokens, elapsed time and cost. The row of a toolset sums its cases
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_compare.py` passes

## 5. Report the verification pass or not run

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_eval_compare.py`, `src/devops_cli/roadmap/stage/stage_verify_eval.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/support/fakes/model.py`. Changes: `src/devops_cli/roadmap/stage/stage_eval_compare.py`, `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_eval_compare.py`.

- [ ] 5.1 `test_the_verification_column_shows_not_run_without_a_pass` in `tests/roadmap/stage/test_roadmap_stage_eval_compare.py` fails: the column of `src/devops_cli/roadmap/stage/stage_eval_compare.py` holds a number with no pass, and `eval_stage_cmd` in `src/devops_cli/commands/roadmap_eval_stage.py` takes no `--verify`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_compare.py` fails on the base
- [ ] 5.2 Add `--verify` to the compare form of `eval_stage_cmd` in `src/devops_cli/commands/roadmap_eval_stage.py`. With it, `verify_plan` in `src/devops_cli/roadmap/stage/stage_eval_compare.py` checks out the case, builds the verification input from the plan of the run and a `ToolboxClient` of the verification model, runs the existing pass of `src/devops_cli/roadmap/stage/stage_verify.py`, and counts the defects with `matched_defects` of `src/devops_cli/roadmap/stage/stage_verify_eval.py`. Without it, the verification column holds `not run` and no pass runs
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_compare.py` passes

## 6. Add the two estimate constants to the limit registry

Kind: other. Reads: `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/roadmap/stage/test_roadmap_stage_constants.py`, `tests/config/test_isolation_tripwire.py`. Changes: `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [ ] 6.1 Add `CONST_ROADMAP_STAGE_EVAL_ESTIMATE_INPUT_TOKENS = 40_000` and `CONST_ROADMAP_STAGE_EVAL_ESTIMATE_OUTPUT_TOKENS = 6_000` to `src/devops_cli/config/constants.py`, from the tokens of one plan run of the stored golden score, and add both names to the `LIMITS` table of `tests/roadmap/test_roadmap_limit_classes.py` with the class `other` and the reason that an estimate of a dry-run cost cuts no run. The registry test is the census: stop when it reports a member that the plan does not decide
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_limit_classes.py` passes

## 7. State the plan and the cost on a dry run

Kind: behavior. Reads: `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/roadmap/stage/stage_eval_compare.py`, `src/devops_cli/roadmap/stage/stage_eval_render.py`, `src/devops_cli/dry_run/__init__.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/roadmap/stage/stage_eval_compare.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_eval_compare.py`.

- [ ] 7.1 `test_the_compare_dry_run_states_the_plan_and_the_cost_with_no_model_call` in `tests/roadmap/stage/test_roadmap_stage_eval_compare.py` fails: the dry run of `eval_stage_cmd` in `src/devops_cli/commands/roadmap_eval_stage.py` states no cost and calls the client
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_compare.py` fails on the base
- [ ] 7.2 Add `estimated_spend` to `src/devops_cli/roadmap/stage/stage_eval_compare.py`, which multiplies the tokens of one plan run from `CONST_ROADMAP_STAGE_EVAL_ESTIMATE_INPUT_TOKENS` and `CONST_ROADMAP_STAGE_EVAL_ESTIMATE_OUTPUT_TOKENS` of `src/devops_cli/config/constants.py` by the cases, the runs and the toolsets, and prices them with `RunUsage.spend_usd` of `src/devops_cli/roadmap/stage/stage_eval_usage.py`. On `--dry-run`, the compare form of `eval_stage_cmd` in `src/devops_cli/commands/roadmap_eval_stage.py` prints the cases, the runs, the toolset names and the estimated cost through the message of `src/devops_cli/lang/en/messages.py`, and returns before it builds a client
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_compare.py` passes

## 8. Load the staged-item replay cases

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_compare.py`, `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/lang/en/help.py`, `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`. Changes: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_compare.py`, `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/lang/en/help.py`, `tests/roadmap/stage/test_roadmap_stage_eval_compare.py`.

- [ ] 8.1 `test_the_comparison_runs_a_golden_case_and_a_staged_item_case` in `tests/roadmap/stage/test_roadmap_stage_eval_compare.py` fails: `load_cases` in `src/devops_cli/roadmap/stage/stage_eval_cases.py` reads only the golden directory
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_compare.py` fails on the base
- [ ] 8.2 Add `STAGED_CASES_DIRECTORY` and `load_staged_cases(directory)` to `src/devops_cli/roadmap/stage/stage_eval_cases.py`, which reads a directory of the same case format and gives an empty list when the directory holds no case. Add `--staged-cases` to the compare form of `eval_stage_cmd` in `src/devops_cli/commands/roadmap_eval_stage.py` with its help text in `src/devops_cli/lang/en/help.py`, defaulted to that directory, and run the union of the golden cases and the staged cases through the same selection of `src/devops_cli/roadmap/stage/stage_eval_compare.py` and the same case checks
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_compare.py` passes

## 9. Add the first staged-item replay case

Kind: manifest. Reads: `tests/fixtures/roadmap_eval/stage/good-2950-the-alert-case-is-a-manifest-group/case.json`, `tests/fixtures/roadmap_eval/stage/good-2950-the-alert-case-is-a-manifest-group/plan.json`, `tests/fixtures/roadmap_eval/stage/good-2950-the-alert-case-is-a-manifest-group/facts.json`, `tests/fixtures/roadmap_eval/stage/good-2950-the-alert-case-is-a-manifest-group/issue.txt`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`. Changes: `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/case.json` (new), `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/issue.txt` (new), `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/plan.json` (new), `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/facts.json` (new), `tests/roadmap/stage/test_roadmap_stage_eval_compare.py`.

- [ ] 9.1 `test_the_staged_item_case_loads_with_its_commit` in `tests/roadmap/stage/test_roadmap_stage_eval_compare.py` fails: the staged directory holds no case, and `load_staged_cases` of `src/devops_cli/roadmap/stage/stage_eval_cases.py` finds none
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_compare.py` fails on the base
- [ ] 9.2 Write one staged-item replay case in the case format of `tests/fixtures/roadmap_eval/stage/good-2950-the-alert-case-is-a-manifest-group/case.json`: `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/case.json` with its issue text, its plan and the facts of its tree, `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/issue.txt`, `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/plan.json` and `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/facts.json`, with a commit that a run can check out and the labeled defects of its review. Keep every path relative to the repository root
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_compare.py` passes

## 10. Pin that the eval stage command publishes no MCP tool

Kind: other. Reads: `tests/ai/mcp/test_mcp_exposure_table.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/ai/mcp/server.py`, `src/devops_cli/commands/roadmap_eval_stage.py`. Changes: `tests/ai/mcp/test_mcp_exposure_table.py`.

- [ ] 10.1 Add `test_the_roadmap_eval_stage_command_publishes_no_mcp_tool` to `tests/ai/mcp/test_mcp_exposure_table.py`. It resolves the `stage` subcommand of `roadmap eval` with `src/devops_cli/ai/mcp/generator.py:199:def resolve_click_command(path: tuple[str, ...]) -> Any:` and asserts that the resolution raises no `LookupError`. It then asserts that the server of `src/devops_cli/ai/mcp/server.py` returns no tool named `roadmap_eval_stage`, so the command stays excluded. The group adds no row to `CONST_MCP_EXPOSURE_TABLE` and no exclusion record, because `tests/ai/mcp/test_mcp_exposure_table.py:63:def test_every_exposed_mcp_command_is_a_command_of_the_tree() -> None:` states that a command of the tree that the table does not name is excluded (#3204), and this test is the census of the exposure rows that would name the command
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_exposure_table.py` passes

## 11. Regenerate the docs

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`.

- [ ] 11.1 Edit the runbook with the `--toolset` option, the `compare` form, the columns of the table, the dry-run cost and the MCP exclusion, then regenerate the generated documents from the help texts and the command tree with `uv run devops docs generate`. The generated documents take the option and the form from their sources, so no hand edit stays in them
  - Verification: `$ uv run devops ci docs` passes
- [ ] 11.2 Edit `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/stage.md` with the toolset option, the compare form and the MCP exclusion, then regenerate `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md` with `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: `devops roadmap eval stage --toolset extended` runs and names the toolset in its report.
- Group 3: `devops roadmap eval stage compare base extended` prints one table with the columns above and runs offline with a fake client in the tests.
- Group 4: The report states the number of runs for each case and the spread.
- Group 10: The command is in the MCP exposure list as excluded or exposed, the docs are regenerated, and `eval stage --dry-run` states what it would run and what it would cost.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
