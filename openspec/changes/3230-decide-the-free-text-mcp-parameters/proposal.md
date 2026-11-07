# Proposal

## Why

The MCP guard of #3222 finds a secret parameter by the words of its name, so a parameter whose name says nothing about a secret passes it. Issue #3230 names two published parameters, `sandbox_deploy.env` and `valkey_set.value`, whose free text a model writes and a person can fill with a secret. SECURITY.md rule 12 says that a tool publishes no parameter that takes a secret value.

## What Changes

- `_PATH_PARAM_RESTRICTIONS` in `src/devops_cli/ai/mcp/generator.py` takes an optional `denied` set, and `_introspect_command_parameters` omits each parameter that it names.
- The `("sandbox", "deploy")` restriction denies `env`, so the tool publishes no `env` parameter.
- The `("valkey", "set")` row leaves `CONST_MCP_EXPOSURE_TABLE` and `_PATH_PARAM_RESTRICTIONS`, so the server publishes no `valkey_set` tool.
- `tests/ai/mcp/test_mcp_exposure_table.py` adds `("valkey", "set")` to `mcp_command_exclusions`, and `test_export_schemas_command` in `tests/commands/test_mcp_tools_and_schema_export.py` verifies `tf_apply.json` instead of `valkey_set.json`.
- `tests/ai/mcp/test_mcp_tool_registry.py` drops `valkey_set` from `floor_expected_false`, and `tests/ai/mcp/test_mcp_argument_refusal.py` tests input validation and log masking with `tf_apply`.
- `CONST_MCP_FREE_TEXT_SINK_PARAMETER_NAMES` and `CONST_MCP_FREE_TEXT_SINK_ALLOWLIST` in `src/devops_cli/config/constants.py` name the free-text sink names and the allowed parameters with a reason.
- `CONST_MCP_FREE_TEXT_SINK_ALLOWLIST` names `("k8s_diff_helm", "values")` with its reason.
- A new guard test in `tests/ai/mcp/test_mcp_tool_secrets.py` fails on an unallowed sink parameter, and on an allow-list entry that matches no parameter.
- `SECURITY.md` rules 11 and 12 state the new guard and list `valkey set` among commands that are not MCP tools.
- `devops docs generate --sync-readme` updates `docs/MCP_TOOLS.md`.
- The change alters what an MCP client observes, so it carries a spec delta and `skip_specs` is false.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `mcp-tool-secrets`: The sandbox deploy tool publishes no env parameter, The server publishes no valkey set tool, A denied parameter leaves the tool schema, A free-text sink parameter needs an allow-list entry, A free-text allow-list entry names a published parameter

## Impact

- Code: `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/config/constants.py`
- Documents: `SECURITY.md`, `docs/MCP_TOOLS.md`
- Tests: `tests/ai/mcp/test_mcp_exposure_table.py`, `tests/commands/test_mcp_tools_and_schema_export.py`, `tests/ai/mcp/test_mcp_tool_secrets.py`, `tests/ai/mcp/test_mcp_tool_registry.py`, `tests/ai/mcp/test_mcp_argument_refusal.py`

## Feasibility

- The probe of `src/devops_cli/ai/mcp/generator.py` reports that `_PATH_PARAM_RESTRICTIONS` is defined at line 29. It holds the `("valkey", "set")` entry whose `allowed` set names `value`.
- The probe of `SECURITY.md` reports that `SECURITY.md` is tracked in git. Rule 11 states the non-MCP valkey commands, and rule 12 states the secret parameter rules.
- A check of all published FastMCP tools finds three parameters matching the free-text sink names `env`, `values`, `value`, `data`: `sandbox_deploy.env`, `valkey_set.value`, and `k8s_diff_helm.values`.
- `sandbox_deploy.env` is omitted through `denied`, and `valkey_set` is removed.
- `k8s_diff_helm.values` accepts paths to values YAML files and stays published with an entry in `CONST_MCP_FREE_TEXT_SINK_ALLOWLIST`.
- `tests/ai/mcp/test_mcp_tool_registry.py` and `tests/ai/mcp/test_mcp_argument_refusal.py` and `tests/ai/mcp/test_mcp_exposure_table.py` and `tests/commands/test_mcp_tools_and_schema_export.py` reference `valkey_set` and are updated to use `tf_apply` and list `valkey set` under exclusions.
- Verification commands: `uv run devops ci test tests/ai/mcp/test_mcp_tool_secrets.py`, `uv run devops ci test tests/ai/mcp/test_mcp_exposure_table.py`, `uv run devops ci test tests/commands/test_mcp_tools_and_schema_export.py`, `uv run devops ci test tests/ai/mcp/test_mcp_tool_registry.py`, `uv run devops ci test tests/ai/mcp/test_mcp_argument_refusal.py`, and `uv run devops ci docs`.

## Existing Tool Considered

No open, maintained tool decides which free-text parameter of a CLI-derived MCP schema can carry a secret. The guard of #3222 in `tests/ai/mcp/test_mcp_tool_secrets.py`, with `CONST_MCP_SECRET_PARAMETER_WORDS` and `CONST_MCP_SECRET_PARAMETER_ALLOWLIST`, covers parameter names only, and this change extends it. Building the guard inside that test costs about 30k tokens and about 2 hours, and it adds one constant pair and one test case to keep.
