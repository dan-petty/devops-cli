# Design

## Decisions

- **The comparison lives in `devops roadmap eval stage` as a `compare` form, not in a new top-level command.**: The command already owns the golden set, the stage evaluation and its report, so one entry point keeps one documentation page and one MCP exposure decision.
- **The toolset names come from the stage toolset setting `StageToolset`, which holds `base`, `extended` and `research`.**: The eval names then match the planner, and a new named toolset needs no eval change.
- **Each case runs `--runs` times, three by default, and the table states the runs and the minimum and maximum of each measured value.**: The reply of a model differs between runs, so one reply is a sample and not a measurement; a minimum and a maximum show the spread in a form a test can assert.
- **The cost of a row comes from `RunUsage.spend_usd`, which reads the AI spend pricing registry.**: One price source stays current with the ledger and the rest of the CLI.
- **The verification column runs the verification pass only with `--verify` and holds `not run` otherwise.**: The pass costs a second model call for each case, and ADR 0005 keeps findings on the existing pass rather than a new verifier.
- **The staged-item replay cases sit in their own directory and are read with the existing `load_cases` and case format.**: The golden set counts stay stable, and the two sets share one schema, one loader and one set of tests.
- **The dry run estimates the cost from two estimate constants and the pricing registry.**: A dry run makes no model call, so it cannot measure tokens, and the constants come from a measured plan run.
- **Leave `roadmap eval stage` out of `CONST_MCP_EXPOSURE_TABLE` and add no exclusion record, and pin the derived exclusion with one test that resolves the command in the tree and asserts that the server publishes no tool for it.**: `tests/ai/mcp/test_mcp_exposure_table.py` records exclusion by omission from the command tree (#3204), so a new tuple or a generator section would restate derived state and could drift from the tree.

## Rejected alternatives

- **Add a new top-level `devops roadmap eval compare` command.**: `src/devops_cli/commands/roadmap_eval_stage.py` already holds the case loader, the run and the report, so a second command duplicates the entry point and splits the docs and the MCP exposure decision.
- **Hard-code `base` and `extended` in the eval command.**: `src/devops_cli/config/defaults.py:1111:StageToolset = Literal["base", "extended", "research"]` holds the names, so a hard-coded pair would need a second change for each new toolset.
- **Run each case once.**: The replies of a model differ between runs, so one reply measures no spread and the issue asks for the spread.
- **Add a second price table in the eval command.**: `src/devops_cli/roadmap/stage/stage_eval_usage.py:31:def spend_usd(self, model: str) -> float | None:` already prices tokens with the pricing registry, and a copy would drift from it.
- **Add a new model verifier for the verification column.**: docs/adr/0005-review-findings-come-from-tools-not-models.md records that the model verifier is deleted, and `src/devops_cli/roadmap/stage/stage_verify_eval.py:71:def matched_defects(defects: Sequence[Defect], findings: Sequence[Finding]) -> tuple[Defect, ...]:` already counts the defects that the existing pass finds.
- **Read live GitHub issues and pull requests during the comparison.**: The issue requires an offline comparison with a fake client in the tests, and a live read needs a token and gives a different answer on each run.
- **Add a new `CONST_MCP_EXCLUDED_COMMANDS` tuple and an excluded-commands section of the MCP page.**: `search_code` for `CONST_MCP_EXCLUDED` returned `No match`, and `tests/ai/mcp/test_mcp_exposure_table.py:64:A command of the tree that` states that a command of the tree that the exposure table does not name is excluded, so the tuple and the section would restate state that the tree already derives.
- **Expose `roadmap eval stage` as a row of `CONST_MCP_EXPOSURE_TABLE`.**: `src/devops_cli/commands/roadmap_eval_stage.py:126:Path | None, typer.Option("--cases", help=HELP.roadmap.eval_stage_cases)` and its `--source` option show two paths of the caller, which an exposure row would publish to a model, and a comparison run spends model money.
- **Pin the exclusion with a test that reads an exposure row of the command, and also regenerate `docs/MCP_TOOLS.md` with an excluded section.**: `search_code` for the command path of `roadmap eval` returned no line of `src/devops_cli/config/constants.py`, so the command has no tool row and the MCP page has nothing to add; the page stays the output of its generator and group 11 runs `uv run devops ci docs` to prove it.
