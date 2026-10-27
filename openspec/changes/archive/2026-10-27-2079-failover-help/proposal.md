# Proposal

## Why

Issue #2079: the help of `devops ai failover` states that `devops ai gateway failover` reroutes requests. That statement is inaccurate. `devops ai gateway failover` records a failover route for a virtual model in the local route table, and the fallbacks of the gateway configuration move the live traffic.

## What Changes

- Update `HELP.ai.failover` in `src/devops_cli/lang/en/help.py` to state that `devops ai failover` records a fallback route in the constellation flag, `devops ai gateway failover` records a failover route for a virtual model, and the gateway's own fallbacks move the traffic.
- Regenerate the command reference documentation and README with `uv run devops docs generate --sync-readme`.
- Add a test asserting that `devops ai failover --help` contains the updated description.
- The change alters help text and generated documentation only. It changes no command arguments, options, messages, manifests or runtime behavior, so it has no spec delta and sets `skip_specs: true` in `.openspec.yaml`. It fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/lang/en/help.py`
- `README.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/ai.md`
- `tests/test_ai_controller.py`

## Feasibility

- Command help inspection: `src/devops_cli/lang/en/help.py` line 178 records the old string: `"Record a fallback route in the constellation flag; `devops ai gateway failover` reroutes requests."`.
- Upstream configuration inspection: `k8s/llm/gateway/config.yaml` lines 12-25 configure `router_settings.fallbacks` in LiteLLM, which executes the live traffic routing fallback.
- Code inspection: `src/devops_cli/ai/gateway.py` `trigger_failover` persists `failover:*` entries to `gateway_state.json`, which only `status`, `routes`, and `failover` inspect. Nothing dispatches request traffic through that table.
- The premise is confirmed against the codebase.

## Existing Tool Considered

No outside tool applies. The change corrects an internal command help string and regenerates documentation with the repository's built-in generator (`devops docs generate --sync-readme`).
