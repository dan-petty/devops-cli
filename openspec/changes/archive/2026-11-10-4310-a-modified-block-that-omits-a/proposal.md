# Proposal: #4310

## Why

A reply whose `MODIFIED` requirement leaves out a scenario of the living spec fails the OpenSpec validation, and the model does not repair it in the one return that it gets (#4310). OpenSpec refuses a `MODIFIED` block that omits a scenario of the base requirement, because the block replaces the whole requirement and `openspec archive` refuses to drop a scenario. The model reads the requirement with `read_spec` and still writes fewer scenarios. A live stage run on #3599 failed this way, and the stage job logs show the same for #3488 and #3478. Closes #4310.

## What Changes

- `restore_omitted_scenarios` in `src/devops_cli/roadmap/stage/stage_validate.py` adds each base scenario that a `MODIFIED` block omits at the end of that block, with the raw text that `openspec show <capability> --type spec --json` gives. The planner calls it before it validates the change, so the files that it validates are the files that it writes.
- The scenarios of the reply keep their text and their order. A requirement that the base spec lacks, a capability with no base spec, and an `ADDED` requirement are left as they are.
- `src/devops_cli/roadmap/stage/stage_change.py` renders a spec delta with the omitted scenarios through `spec_file`.
- The change carries a spec delta because it changes the files that the stage job writes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A MODIFIED requirement gets the base scenarios that it omits

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_validate.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_restore_scenarios.py`
- The job starts one more OpenSpec command, `openspec show`, for each capability with a `MODIFIED` requirement.

## Feasibility

- The failure text of the live run is in the issue, word for word: `MODIFIED "The job rewrites the pull request after the push" omits scenario(s) the current spec still has: "A refused body stops the item"`.
- Checked with the real pinned OpenSpec 1.14.3 on a scratch checkout: a base requirement with two scenarios (one with an `AND` line) and a block with one scenario gives the omit problem before the repair and no problem after it. The restored scenario keeps its `AND` line.
- `openspec show comment-thread --type spec --json` gives the `name` and the `rawText` of each scenario, which is the source of the copy.
- Check: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_restore_scenarios.py`, and `uv run devops roadmap eval stage --replay` keeps its result.

## Existing Tool Considered

`openspec show <capability> --type spec --json` already gives the name and the raw text of each scenario, and `read_spec` uses it. OpenSpec has no command that repairs a `MODIFIED` block, and `openspec validate` only reports the problem. No new parser is needed, because the repair copies the raw text and renders the block with the renderer of the job. Cost: about 40 000 tokens to build, 5 000 to keep and 2 hours.
