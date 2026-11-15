# Proposal

## Why

The stage planner has named toolsets (#3238), and nothing measures which set gives the best plans for its cost. The offline golden set judges only the defects that a gate sees, so a person has no measured comparison of gate defects, tokens, time and cost. #3239 adds that measurement to `devops roadmap eval stage`.

## What Changes

- `devops roadmap eval stage` takes `--toolset <name>` from the stage toolset setting and names the toolset in its report.
- `devops roadmap eval stage compare <toolset>...` runs every named toolset on the same cases and prints one table.
- The table gives, for each toolset, the gate defects, the verification defects, the tool calls, the requests, the input and output tokens, the elapsed time and the cost.
- The comparison runs each case three times by default, states the number of runs and shows the minimum and the maximum of each measured value.
- The comparison prints one delta line for each measured column against the first toolset.
- The comparison prices its tokens with the AI spend pricing registry and prints `unpriced` for a model that the registry holds no price for.
- The verification column holds `not run` unless `--verify` asks for the verification pass.
- `--dry-run` states the cases, the runs, the toolsets and the estimated cost from two estimate constants and makes no model call.
- The comparison loads the staged-item replay cases beside the golden cases, and the first such case is committed at `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/case.json`.
- `roadmap eval stage` stays out of `CONST_MCP_EXPOSURE_TABLE`, so the MCP server publishes no tool for it, and a new test pins that the command resolves in the tree and that the server publishes no tool for it.
- `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md` are regenerated with the new option and the compare form.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage-eval`: The eval stage command takes a toolset, The compare form runs each toolset on the same cases, The comparison states the runs and the spread, The comparison reports the verification pass, The comparison prints one delta line for each measured column, The comparison prices a row from the pricing registry, The compare dry run states the cases, the runs and the cost, The comparison loads the staged-item replay cases, The MCP server publishes no tool for the eval stage command

## Impact

- Code: `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/roadmap/stage/stage_eval_run.py`, `src/devops_cli/roadmap/stage/stage_eval_render.py`, `src/devops_cli/roadmap/stage/stage_eval_score.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_eval_compare.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_eval_command.py`, `tests/roadmap/stage/test_roadmap_stage_eval_compare.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/case.json`, `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/issue.txt`, `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/plan.json`, `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/facts.json`, `tests/ai/mcp/test_mcp_exposure_table.py`

## Feasibility

- The probes state "The path `src/devops_cli/commands/roadmap_eval_stage.py` is a file of the staging commit." and "The path `tests/ai/mcp/test_mcp_exposure_table.py` is a file of the staging commit.", so both files that the plan changes exist at the staged commit.
- The probes state "The path `roadmap.stage.toolset` is no file of the staging commit. No commit in the history deleted or renamed it." It names a setting and not a path, so no commit removed it.
- `read_file` of `src/devops_cli/commands/roadmap_eval_stage.py` showed `src/devops_cli/commands/roadmap_eval_stage.py:110:def eval_stage_cmd(` with the options `--case`, `--model`, `--limit`, `--json`, `--dry-run`, `--replay`, `--cases`, `--source` and `--no-toolbox`, and no `--toolset` option and no `compare` form, so the issue premise holds.
- `search_code` for `StageToolset = Literal` showed `src/devops_cli/config/defaults.py:1111:StageToolset = Literal["base", "extended", "research"]`, so the set that the issue names holds 3 members, and each is decided: `base`, `extended` and `research` are accepted, and a new name needs no eval change.
- `file_symbols` of `src/devops_cli/roadmap/stage/stage_eval_run.py` showed `class CaseRun` and `def run_case(` and `def run_cases(`, so the toolset and the trace list of each run pass through these two functions.
- `file_symbols` of `src/devops_cli/roadmap/stage/stage_toolbox.py` showed `class ToolboxClient` and `def __init__(`, and its lines 117 to 119 hold `toolset: StageToolset | None = None,` and `traces: list[RunTrace] | None = None,`, so the client of a chosen toolset already keeps the traces of its runs.
- `file_symbols` of `src/devops_cli/roadmap/agent_run.py` showed `class RunTrace`, and its lines 237 to 240 hold the fields `tool_calls`, `requests`, `input_tokens` and `output_tokens`, the four counters of a table row.
- `file_symbols` of `src/devops_cli/roadmap/stage/stage_eval_render.py` showed `def render_score(` and `def score_json(`, so the toolset line and the dry-run plan extend the existing renderers.
- `file_symbols` of `src/devops_cli/roadmap/stage/stage_eval_score.py` showed `class StageScore`, which takes the new `toolset` field.
- `read_file` of `src/devops_cli/roadmap/stage/stage_eval_usage.py` showed `src/devops_cli/roadmap/stage/stage_eval_usage.py:31:def spend_usd(self, model: str) -> float | None:`, which prices the tokens of a row with the pricing registry, so the cost needs no second price table.
- `search_code` for `CASES_DIRECTORY` showed `src/devops_cli/roadmap/stage/stage_eval_cases.py:72:CASES_DIRECTORY`, and `file_symbols` of that file showed `def load_cases(` and `def select_cases(`, the loader and the selection that the staged cases reuse.
- `search_code` for `def matched_defects` showed `src/devops_cli/roadmap/stage/stage_verify_eval.py:71:def matched_defects(defects: Sequence[Defect], findings: Sequence[Finding]) -> tuple[Defect, ...]:`, which counts the defects that the verification pass finds.
- The finding on the exposure key is fixed at its place: the plan cites no key of `CONST_MCP_EXPOSURE_TABLE`. `search_code` for the command path of `roadmap eval` returned no line of `src/devops_cli/config/constants.py`, and `src/devops_cli/config/constants.py:304:CONST_MCP_EXPOSURE_TABLE: Final[tuple[tuple[tuple[str, ...], float, bool, bool], ...]] = (` opens the table, so the table holds 0 rows for that family of commands and derives the exclusion of `roadmap eval stage` by omission.
- `read_file` of `tests/ai/mcp/test_mcp_exposure_table.py` showed `tests/ai/mcp/test_mcp_exposure_table.py:63:def test_every_exposed_mcp_command_is_a_command_of_the_tree() -> None:` with the docstring `tests/ai/mcp/test_mcp_exposure_table.py:64:A command of the tree that`, which states that a command of the tree that the table does not name is excluded (#3204). Group 10 pins that derived exclusion with a test and adds no exclusion record.
- `read_file` of `src/devops_cli/ai/mcp/generator.py` showed `src/devops_cli/ai/mcp/generator.py:199:def resolve_click_command(path: tuple[str, ...]) -> Any:`, which walks the subcommands of a path and raises `LookupError` for one that the tree does not hold, so the test of group 10 resolves the `stage` subcommand of `roadmap eval` and asserts that it resolves.
- The findings on the tests of a changed module are fixed at their place: group 1 lists `tests/roadmap/stage/test_roadmap_stage_gate_extension.py` and `tests/roadmap/stage/test_roadmap_stage_eval_facts_context.py` in `reads`, groups 1, 3, 4, 5 and 7 list `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`, and groups 1, 3, 4, 5 and 7 list `tests/roadmap/implement/test_roadmap_implement_amend.py`, so the implement job can edit every test of a module it changes.
- `CONST_ROADMAP_STAGE_EVAL_ESTIMATE_INPUT_TOKENS` and `CONST_ROADMAP_STAGE_EVAL_ESTIMATE_OUTPUT_TOKENS` are new, so the staged tree holds no value for them: the plan sets 40000 and 6000 from one plan run of the stored golden score, and `read_file` of `tests/roadmap/test_roadmap_limit_classes.py` showed the `LIMITS` table, so each new name needs an entry.
- First check against the real system: `uv run devops roadmap eval stage --replay --json` runs the golden set through the gates and makes no model call.
- First check against the real system: `uv run devops roadmap eval stage --dry-run --limit 1` prints the request plan of one case and makes no model call.
- First check against the real system: `uv run devops ci docs` regenerates the pages and fails when a committed page differs from its generator.
- Precondition of `run_case` in `src/devops_cli/roadmap/stage/stage_eval_run.py`: a checkout of the repository, which the commit of the case needs.
- Precondition of `run_cases`: a checkout of the repository and a client of the stage model.
- Precondition of `load_cases` in `src/devops_cli/roadmap/stage/stage_eval_cases.py`: a checkout of the repository, which holds the case directories.
- Precondition of `run_toolset` in the new compare module: a checkout of the repository and a client of the stage model.
- Precondition of `verify_plan` in the new compare module: a checkout of the repository and a client of the verification model.
- Precondition of `resolve_click_command` in `src/devops_cli/ai/mcp/generator.py`: a checkout of the repository, because it loads the module of the first path segment; it needs no client and no network.
- Precondition of `RunUsage.spend_usd`: none; it reads the pricing registry of the data directory and reaches no network.
- Precondition of `matched_defects`: none; it matches two lists in memory.
- The two commands add no failure class: a model call that fails ends its case as `failed`, as `run_case` does today, and a rejected client stops the run.
- Each verify program is `uv run devops ci test` or `uv run devops ci docs`: `uv`, `python`, `devops` and `pytest` are runner tools of the image and none is `NOT_IN_RUNNER`. The pod runs them with `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false` and `capabilities.drop: ALL`.
- The paid comparison of real plans needs a client of the model gateway and a network, so a person approves that run (#3207). No test of this change makes a network call.

## Existing Tool Considered

promptfoo (MIT, maintained, last activity 2026-11-05) partly covers the need: it runs one eval over the same cases with several configurations, prints a comparison table, repeats each case (`repeat: 3`), records cost, latency and input and output tokens, and runs offline with recorded inputs and custom Python assertions. It lacks the repository's stage toolsets, its gate and verification defect counts, its golden and staged-item replay case format, its AI spend pricing, its delta line against the first toolset, and its MCP exposure list and docs regeneration. The change extends `devops roadmap eval stage` for these parts, at 25k tokens to build, keep and fix, and 16 hours of elapsed time.

## Dependencies

None.
