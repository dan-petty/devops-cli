# Proposal: #4272

## Why

In a dry run, `devops openspec check` prints `openspec list --json failed with exit code 0: not JSON:` and exits 1. A dry run starts no process: `run_subprocess` returns a planned result with exit code 0 and empty output. The gate reads that empty output as the change list of the tool and fails. The message points at the tool, not at the dry run, and the dry run does not show the commands that the gate would run. Closes #4272.

## What Changes

- `devops openspec check` in a dry run (`devops --dry-run` or `DEVOPS_CLI_DRY_RUN=1`) starts no process. It lists the `openspec` commands of the gate in the order that the gate runs them, each with the variables that the run sets, and says that it would run the gate. It exits 0.
- `plan_check` in `src/devops_cli/openspec/gate.py` gives this plan as `PlannedRequest` entries. A scratch directory is a named placeholder. The `show` command of the overlap check runs once for each active change, so the plan names that repetition.
- The real run and the plan take each command from one place: the settings of the isolated configuration, the change list, the validations, the regeneration of the skills, the probe change, the instructions and the `show` command. So the plan cannot differ from the real run.
- The command output is observable behavior, so the change has a spec delta for the new capability `openspec-check`.

## Capabilities

### New Capabilities

- `openspec-check`: The gate command plans without running in a dry run.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/commands/openspec.py`, `src/devops_cli/openspec/gate.py`, `src/devops_cli/openspec/tool.py`, `src/devops_cli/openspec/skills.py`, `src/devops_cli/openspec/overlap.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/openspec/test_openspec_gate.py`.
- The real run keeps its commands and findings: `test_the_gate_passes_a_tree_with_no_change_and_no_spec` asserts the same command list as before.
- Fits one pull request.

## Feasibility

Checked on 2026-11-12 with the pinned `openspec` 1.14.3 and the code of `main` at `e80db62c8`:

- `uv run devops --dry-run openspec check` printed `openspec list --json failed with exit code 0: not JSON:`. `DEVOPS_CLI_DRY_RUN=1 uv run devops openspec check` exited 1.
- In a dry run, `run_subprocess` (`src/devops_cli/core/process.py`) returns a `PlannedProcessResult` with exit code 0 and empty output. `active_changes` passes that output to `json.loads`, which raises, and `read_json` reports `not JSON`.
- The gate runs a fixed list of commands over a tree with no change (`EMPTY_TREE_COMMANDS` in `tests/openspec/test_openspec_gate.py`), and one `show` command for each active change. Each of them can be listed without a run.

## Existing Tool Considered

`render_request_plan` and `PlannedRequest` (`src/devops_cli/dry_run/requests.py`) give the plan output. The archive command uses them for its dry run (#4270). No new tool or library is needed. The plan function is about 30 lines.
