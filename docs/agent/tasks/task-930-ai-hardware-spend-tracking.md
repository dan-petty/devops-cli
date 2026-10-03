# Task: Local LLM Hardware Spend Tracking & Cluster Gateway Recognition (#930)

**Issue**: [#930](https://github.com/dan-petty/devops-cli/issues/930)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p1-high
**Scope**: scope/ai, scope/telemetry

## Description
The user tracks local LLM usage against their hardware investment ($7,000) to measure investment amortization, daily savings run-rate, and break-even payoff. Prior to this deliverable:
1. `ai.hardware_cost_usd` and `ai.reference_model` were omitted from `devops config show` and not documented in `config.example.yaml`, making the hardware investment setting difficult to discover and inspect.
2. `is_local()` in `src/devops_cli/ai/spend/pricing.py` only evaluated static constants (`CONST_LOCAL_HOSTNAMES`, `CONST_LOCAL_DOMAIN_SUFFIXES`), failing to recognize cluster endpoints and self-hosted LiteLLM gateways matching `k8s.domain`, `cloudflare.domain`, or `ai.gateway_url`. This caused cluster gateway requests (such as 5,600+ requests and ~65M tokens via cluster gateway endpoints) to be misclassified as non-local, omitting over $195 of counterfactual savings and reporting $0 or truncated equivalent spend.
3. OpenTelemetry and Prometheus instrumentation lacked counter metrics for equivalent hosted spend avoided by local model execution (`devops_cli_ai_local_cost_equivalent_usd_total`), and the Grafana AI spend dashboard (`ai-spend.json`) had no panels tracking local hardware savings or payoff against hardware investment.

## Key Changes
1. **Configuration Visibility & Documentation**:
   - Added `opt.AI_REFERENCE_MODEL` and `opt.AI_HARDWARE_COST_USD` rows to `devops config show` in `src/devops_cli/commands/config.py`.
   - Documented `reference_model` and `hardware_cost_usd` under `ai:` in `config.example.yaml`.
   - Updated runtime configuration in `/workspaces/devops-cli/config.yaml` to set `ai.hardware_cost_usd: 7000.0`.
2. **Cluster Domain & Gateway Endpoint Recognition**:
   - Enhanced `is_local()` and helper functions `_is_configured_cluster_host()`, `_is_configured_ai_server_host()`, `_is_single_server_local()`, and `_is_local_gateway_configured()` in `src/devops_cli/ai/spend/pricing.py`.
   - Properly identifies cluster subdomains matching `k8s.domain` or `cloudflare.domain`, self-hosted gateways matching `ai.gateway_url` / `ai.api_base_url`, and multi-server comma-separated endpoint lists.
   - Restored full counterfactual savings aggregation in `src/devops_cli/ai/spend/ledger.py` (`_tally_and_annotate_servers`), accurately tracking 100% of cluster gateway calls against hardware amortization.
3. **OpenTelemetry Telemetry Instruments**:
   - Added `AI_LOCAL_COST_EQUIVALENT_USD_TOTAL` (`devops_cli_ai_local_cost_equivalent_usd_total`) counter instrument in `src/devops_cli/telemetry/instruments.py`.
   - Implemented `_emit_local_cost_equivalent()` in `src/devops_cli/ai/spend/ledger.py` to emit equivalent hosted cloud spend avoided during uncached local requests.
4. **Grafana SRE AI Spend Dashboard**:
   - Updated `k8s/monitoring/dashboards/ai-spend.json`:
     - Added stat panel `Local Cloud Savings in Range` (`sum(increase(devops_cli_ai_local_cost_equivalent_usd_total[$__range])) or vector(0)`).
     - Added row `Local Hardware Savings & Amortization Payoff` with timeseries panels `Local Hardware Savings Rate ($/hour)` and `Local Savings per Hour by Backend Server`.
     - Maintained full compliance with Prometheus `increase()` two-sample and ordering skew descriptions (#792).
     - Passed `devops grafana dashboards lint` with 0 errors and 0 warnings.
5. **Testing & Invariant Verification**:
   - Added `test_is_local_configured_cluster_and_gateway()` in `tests/test_ai_spend_pricing.py`.
   - Added `test_local_ai_calls_emit_equivalent_spend_instrument()` in `tests/test_telemetry_instruments.py`.
   - Updated `test_config_show_includes_allow_private_network_and_active_path()` in `tests/test_config_cmd.py`.
   - All tests in `tests/test_telemetry_instruments.py`, `tests/test_ai_spend_pricing.py`, and `tests/test_config_cmd.py` pass.
6. **CI Pipeline Race Isolation**:
   - Updated `_run_all_checks_async()` in `src/devops_cli/commands/ci.py` to execute `docs_fix` sequentially alongside `format_fix` and `lint_fix` prior to concurrent test and verification tasks, preventing concurrent documentation regeneration from tripping pytest's workspace mutation tripwire during test suite execution.

## Acceptance Criteria
- [x] `ai.hardware_cost_usd` and `ai.reference_model` are displayed by `devops config show` and documented in `config.example.yaml`.
- [x] `/workspaces/devops-cli/config.yaml` has `ai.hardware_cost_usd` set to `7000.0`.
- [x] `is_local()` recognizes cluster subdomains (`k8s.domain`, `cloudflare.domain`) and configured gateway URLs.
- [x] `devops ai cost` reports full local hardware savings (~$285+ USD) and investment payoff progress (4.07% of $7,000).
- [x] `devops_cli_ai_local_cost_equivalent_usd_total` counter instrument is emitted for local AI model executions.
- [x] Grafana AI spend dashboard (`ai-spend.json`) includes local hardware savings and payoff rate panels, passing dashboard linting.
- [x] Unit and telemetry tests pass with 100% success.
- [x] `uv run devops ci` completes with all quality gates passing.
