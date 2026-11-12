# Proposal: #3642

## Why
Six MCP tools write local state or a file, but `CONST_MCP_EXPOSURE_TABLE` marks them read-only (#3642). A role server and a client choose tools by `readOnlyHint`, so a model can get a write that the flag says it cannot make. The flag cannot change now: the requirement `mcp-read-only-hint-agrees-with-no-external-request` says that each tool of a `no-external-request` command is read-only. The class names external requests only. It does not say that the command writes nothing.

## What Changes
- The requirement `mcp-read-only-hint-agrees-with-no-external-request` says that the `no-external-request` class names external requests only. The tool of such a command is read-only only when the command writes no local state and no file.
- The ratchet test of `tests/invariants/test_dry_run_class_ratchet.py` names the `no-external-request` commands that write local state or a file. It fails when one of them has a read-only tool, and when another `no-external-request` command has a tool that is not read-only.
- The exposure table marks these six tools not read-only: `ai_quiesce`, `ai_resume` and `ai_failover` (they write the constellation snapshot file), `ai_gateway_failover` (`--reset` and `--no-simulate` write the gateway state file), `review_export_feedback` (it appends verdicts to the feedback dataset) and `ai_ingest_library` (it writes the contract of the package to the library contracts directory).
- `docs/MCP_TOOLS.md` shows `false` for the six tools.

The change alters the `readOnlyHint` that the MCP server publishes, which a client observes, so it carries a spec delta.

## Capabilities
- `command-dry-run-class`: MODIFIED `mcp-read-only-hint-agrees-with-no-external-request`.

## Impact
- A client that asks only for read-only tools no longer gets the six tools. No job role of `src/devops_cli/ai/mcp/roles.py` names one of them, so the role servers do not change.
- Each change of a command of the `no-external-request` class that starts or stops a local write also changes the set of local writers of the ratchet test.
- The change fits one pull request.

## Feasibility
Checked on origin/main at e80db62c8:

- `src/devops_cli/config/constants.py` marks `ai failover`, `ai gateway failover`, `ai quiesce`, `ai resume` and `review export-feedback` read-only. A probe through pytest of `CONST_MCP_EXPOSURE_TABLE` against the dry-run class of each command found 145 rows: 39 `no-external-request` rows, all read-only, 104 `request-plan` rows, and 2 rows of commands in `tests/fixtures/dry_run_gaps.json` that have no class.
- A read of each of the 39 commands found six that write local state or a file. `ConstellationManager.quiesce`, `failover` and `resume` (`src/devops_cli/ai/controller/manager.py`) call `_write_snapshot_file`. `GatewayRouter.trigger_failover` with `simulate=False` and `GatewayRouter.reset_failover` (`src/devops_cli/ai/gateway.py`) call `_save_gateway_state`. `devops review export-feedback` appends to the JSONL dataset. `devops ai ingest library` calls `PackageIntrospector.save_to_dir`, which writes a file, also when the MCP tool gives no output directory. The other 33 commands write only to standard output.
- The issue names five tools. `ai_ingest_library` is the sixth member of the same set: the rule that the issue asks for marks it not read-only too.
- The MCP specification defines `readOnlyHint` as "If true, the tool does not modify its environment" (`ToolAnnotations` of the 2025-11-25 schema, in `mcp_types` 2.3.0). A write of a local file modifies the environment.

## Existing Tool Considered
None. The change edits one table, one requirement, one test and one generated document of this repository. No open tool knows which commands of this repository write local state. The written cost to build: about 40k tokens to implement and nothing to keep that the current ratchet does not already cost; about one hour elapsed. The change deletes no internal code.
