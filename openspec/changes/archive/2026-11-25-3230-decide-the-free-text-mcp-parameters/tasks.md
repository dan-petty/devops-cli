# Tasks

## 1. Deny a named parameter in a path restriction

Reads: `src/devops_cli/ai/mcp/generator.py`, `tests/ai/mcp/test_mcp_exposure_table.py`. Changes: `src/devops_cli/ai/mcp/generator.py`, `tests/ai/mcp/test_mcp_exposure_table.py`.

- [x] 1.1 In `tests/ai/mcp/test_mcp_exposure_table.py`, add a test that gives a path restriction a `denied` set holding `env` and asserts that the generated schema of the tool has no `env` property
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_exposure_table.py` fails on the base
- [x] 1.2 Read `denied` in `_introspect_command_parameters` of `src/devops_cli/ai/mcp/generator.py` and skip each parameter that it names, before any `allowed` check. Document the key in the comment above `_PATH_PARAM_RESTRICTIONS`
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_exposure_table.py` passes

## 2. Deny env on sandbox deploy, drop valkey set, and update dependent tests

Reads: `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/config/constants.py`, `tests/ai/mcp/test_mcp_exposure_table.py`, `tests/ai/mcp/test_mcp_tool_registry.py`. Changes: `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/stage/stage_run_allowlist.py`, `tests/ai/mcp/test_mcp_exposure_table.py`, `tests/ai/mcp/test_mcp_tool_registry.py`, `tests/commands/test_valkey.py`.

- [x] 2.1 In `tests/ai/mcp/test_mcp_exposure_table.py`, add a test that asserts the schema of `sandbox_deploy` has no `env` property and that the generated tool names hold no `valkey_set`
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_exposure_table.py` fails on the base
- [x] 2.2 Add `("sandbox", "deploy")` to `_PATH_PARAM_RESTRICTIONS` with `denied` holding `env`. Remove `("valkey", "set")` from `CONST_MCP_EXPOSURE_TABLE` in `src/devops_cli/config/constants.py` and from `_PATH_PARAM_RESTRICTIONS`
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_exposure_table.py` passes
- [x] 2.3 Update `test_export_schemas_command` to check `tf_apply.json` in `tests/commands/test_mcp_tools_and_schema_export.py`. Update `ROW_COUNT` in `tests/roadmap/stage/test_stage_run_allowlist.py`, `floor_expected_false` in `tests/ai/mcp/test_mcp_tool_registry.py`, the input contract tests in `tests/ai/mcp/test_mcp_argument_refusal.py` to use `tf_apply` instead of `valkey_set`, `VALKEY_TOOL_PARAMETERS` and `VALKEY_TOOL_CALLS` in `tests/commands/test_valkey.py`, and the tool-listing snapshot. A command that the exposure table does not name is excluded, so no exclusion list needs an entry
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_exposure_table.py tests/commands/test_mcp_tools_and_schema_export.py tests/ai/mcp/test_mcp_tool_registry.py tests/ai/mcp/test_mcp_argument_refusal.py tests/commands/test_valkey.py tests/roadmap/stage/test_stage_run_allowlist.py` passes

## 3. Add the free-text sink guard and allow-list k8s_diff_helm values

Reads: `SECURITY.md`, `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/config/constants.py`, `tests/ai/mcp/test_mcp_tool_secrets.py`. Changes: `src/devops_cli/config/constants.py`, `tests/ai/mcp/test_mcp_tool_secrets.py`.

- [x] 3.1 In `tests/ai/mcp/test_mcp_tool_secrets.py`, add a test that registers a tool publishing a text parameter named `value` with no allow-list entry and asserts that the guard fails and names the tool and the parameter, and a test that asserts a stale entry fails
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_tool_secrets.py` fails on the base
- [x] 3.2 Add `CONST_MCP_FREE_TEXT_SINK_PARAMETER_NAMES` with `env`, `values`, `value` and `data`, and `CONST_MCP_FREE_TEXT_SINK_ALLOWLIST` with `("k8s_diff_helm", "values")` and its reason in `src/devops_cli/config/constants.py`. Add the schema scan to `tests/ai/mcp/test_mcp_tool_secrets.py` beside the guard of #3222
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_tool_secrets.py` passes

## 4. State the guard in the security policy and update documentation

Reads: `SECURITY.md`, `docs/MCP_TOOLS.md`, `src/devops_cli/config/constants.py`. Changes: `SECURITY.md`, `docs/MCP_TOOLS.md`.

- [x] 4.1 Update rule 11 of `SECURITY.md` to state five valkey commands are MCP tools and that `valkey set` is not an MCP tool. Update rule 12 with the free-text sink names, the allow-list with its reason, and the stale-entry check
  - Verification: `$ uv run devops ci docs` passes
- [x] 4.2 Run `uv run devops docs generate` to regenerate `docs/MCP_TOOLS.md` without `valkey_set`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- The sandbox deploy tool publishes no env parameter: group 2
- The server publishes no valkey set tool: group 2
- A denied parameter leaves the tool schema: group 1
- A free-text sink parameter needs an allow-list entry: group 3
- A free-text allow-list entry names a published parameter: group 3

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
