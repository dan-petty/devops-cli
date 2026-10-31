# Proposal

## Why
Twenty local AI commands do not declare the `no-external-request` dry-run class. Under `devops --dry-run`, these safe local commands print a generic message and do not execute. Some commands also have echo-only previews that print command arguments without real output (#412, closes #2247).

## What Changes
- Classify 20 local AI commands as `no-external-request`:
  - `ai`, `ai ast graph`, `ai ast parse`, `ai audit-library-usage`, `ai bundle-models`, `ai config`, `ai constellation`, `ai diagram`, `ai failover`, `ai harness offload`, `ai harness run`, `ai harness status`, `ai pack-context`, `ai quiesce`, `ai read`, `ai repomap`, `ai resume`, `ai spec`, `ai test-gen`, and `ai token-count`.
- Remove echo-only previews (`render_dry_run_result`) and explicit `--dry-run` options from `ai ast graph`, `ai ast parse`, `ai audit-library-usage`, `ai diagram`, `ai harness offload`, `ai harness run`, `ai pack-context`, `ai read`, `ai repomap`, `ai spec`, and `ai test-gen` with no shim.
- Ensure state modification commands (`ai quiesce`, `ai failover`, `ai resume`) write nothing when dry run is active.
- Remove all 20 commands from `tests/fixtures/dry_run_gaps.json`.
- Fits in one pull request.

## Capabilities

### Modified Capabilities
- `command-dry-run-class`: Add `no-external-request` specifications for twenty local AI commands.

## Impact
- Affected files: `src/devops_cli/commands/ai.py`, `src/devops_cli/commands/ai_ast.py`, `src/devops_cli/commands/ai_controller.py`, `src/devops_cli/commands/ai_harness.py`, `src/devops_cli/ai/spec/verifier.py`, and `tests/fixtures/dry_run_gaps.json`.
- Removed legacy echo-only previews without backward compatibility shims.

## Feasibility
Confirmed against repository source:
- `src/devops_cli/commands/ai.py`: 11 commands operate on local files, configuration settings, or AST structures. Echo-only previews use `render_dry_run_result`.
- `src/devops_cli/commands/ai_ast.py`: 2 commands parse or graph local code trees using tree-sitter. Echo-only previews use `render_dry_run_result`.
- `src/devops_cli/commands/ai_controller.py`: 4 commands inspect or update local constellation state file. `manager.quiesce`, `manager.failover`, and `manager.resume` skip snapshot file writes when `dry_run=True`.
- `src/devops_cli/commands/ai_harness.py`: 3 commands query or drive local sub-agent slot searches without external requests.
- `src/devops_cli/ai/spec/verifier.py`: `verify_architecture_spec` contains an echo-only preview block.
- All 20 commands are listed in `tests/fixtures/dry_run_gaps.json`.

## Existing Tool Considered
The change uses existing `devops_cli.dry_run.dry_run_class` and `is_dry_run` functions. No new dependencies are needed.
Echo-only previews are removed from the command implementations.
