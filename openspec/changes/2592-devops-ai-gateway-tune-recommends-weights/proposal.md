# Proposal

## Why

#2592: devops ai gateway tune recommends routing weights and concurrency, and tells the user to set litellm_params.weight. The gateway uses least-busy routing (k8s/llm/gateway/config.yaml), which reads no weight. No deployment sets weight or max_parallel_requests. The recommendation is not actionable.

## What Changes

- Remove Weight, Recommended, and Max Parallel columns from the tune report table
- Remove the footer instruction to set litellm_params.weight
- Update the module docstring to describe least-busy routing
- Update the tune command help text to describe measurement, not weight recommendation
- Remove ai.gateway_weights and ai.gateway_concurrency from the settings model
- Remove recommend_weights, calculate_hardware_weights, and calculate_hardware_concurrency from gateway_tune.py
- Remove recommended_weight and recommended_concurrency fields from DeploymentTune
- Update docs/CLI_REFERENCE.md and docs/commands/ai.md
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `gateway-tuning`: tune-report-excludes-weight-columns, tune-footer-omits-weight-instruction, tune-docstring-names-least-busy, tune-help-describes-measurement, settings-model-has-no-weight-fields, module-exports-exclude-weight-functions

## Impact

- Code: `src/devops_cli/commands/ai_gateway.py`, `src/devops_cli/ai/gateway_tune.py`, `config/settings.py`
- Documents: `docs/CLI_REFERENCE.md`, `docs/commands/ai.md`

## Feasibility

- k8s/llm/gateway/config.yaml confirms routing_strategy: least-busy and no deployment sets weight or max_parallel_requests
- src/devops_cli/commands/ai_gateway.py shows the table with Weight, Recommended, Max Parallel columns and the footer referencing litellm_params.weight
- src/devops_cli/ai/gateway_tune.py shows recommend_weights, calculate_hardware_weights, calculate_hardware_concurrency and the simple-shuffle docstring
- The issue confirms ai.gateway_weights is read only in tune_cmd in ai_gateway.py
- First checks: uv run devops ai gateway tune --help to verify help text; grep -r gateway_weights src/ to find all references; grep -r recommend_weights src/ to find all callers; uv run devops ci test tests/test_gateway_tune.py to run existing tests

## Existing Tool Considered

LiteLLM least-busy routing strategy covers the gateway's routing need. It picks the deployment with the fewest in-flight requests and reads no weight. The CLI command reports per-deployment measurements; no external tool covers that reporting. The change removes dead code. Nothing new is built.
