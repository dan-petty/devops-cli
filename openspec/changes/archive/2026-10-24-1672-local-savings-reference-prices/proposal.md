# Proposal

## Why

Issue #1672: each process priced its local tokens at its own `ai.reference_model`, and the savings counter had no reference label. The AI spend dashboard thus added workstation savings at gpt-4o prices to roadmap-service savings at gpt-4o-mini prices. A reference model that genai-prices does not know, such as the typo `gpt-4o-mni`, made the savings of every local request $0 with no warning. A hosted model that genai-prices does not know was recorded at $0, and nothing recorded that its price was unknown.

## What Changes

- devops-cli sends no local savings in USD. `devops_cli_ai_tokens_total` gets the label `local`, `true` when a local model ran the tokens. The counter `devops_cli_ai_local_cost_equivalent_usd_total` and `_emit_local_cost_equivalent` are removed.
- The Prometheus recording rule `devops_cli:ai_reference_price_usd_per_token` in `k8s/monitoring/prometheus-values.yaml` holds one price in USD per token for each operation (chat, embeddings) and token type (prompt, completion). Each price is genai-prices' price of the default reference model of the operation: `gpt-4o-mini` for chat and `text-embedding-3-small` for embeddings, under the provider `openai`. A test compares each price with genai-prices' bundled snapshot.
- The eight savings queries of `k8s/monitoring/dashboards/ai-spend.json` multiply the local tokens by the rule on operation and token type. Thus every process is priced at one reference, and a changed price applies to the whole range of a stat panel.
- When neither genai-prices nor a price override prices a reference model, the pricing registry logs one warning that names the model and the setting or option that chose it. The savings of the tokens that this reference prices are unpriced, not $0: `devops ai cost` shows `unpriced`, its JSON output has `null`, `devops ai cost roi` says that the pay-off is not calculated, and the ledger exposition leaves out the savings gauges. `devops config show` checks both reference models in the same way. It is a warning, not a load error.
- Each spend-ledger row stores its pricing source in the new column `pricing_source`: `genai_prices:<provider>`, `local`, the source of a price override, or `unknown`. A hosted model with no price logs one warning for each model in a process. `PricingRegistry.calculate_request_cost` returns `RequestCost(cost_usd, pricing_source)`.
- The genai-prices lookups catch only `LookupError` (a model or provider that genai-prices does not know) and `ValueError` (a price that is not valid), not every exception.
- The help of `--reference-model` names the setting, not the literal `gpt-4o-mini`. A test keeps the default reference model literal in `src/devops_cli/config/defaults.py` only. `src/devops_cli/ai/spend/models.py` already reads `DEFAULT_AI_REFERENCE_MODEL`.
- A metric label, a dashboard, a manifest and command output change, so the change has a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `ai-spend-pricing`: how devops-cli prices AI spend and local savings, and what it does when a model has no price.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/spend/ledger.py`, `pricing.py`, `models.py` and `prometheus.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/commands/ai_cost.py`, `src/devops_cli/commands/config.py`, `src/devops_cli/ai/agents/embeddings.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py` and the telemetry part of `src/devops_cli/docs/generator.py`.
- Manifests: `k8s/monitoring/prometheus-values.yaml` and `k8s/monitoring/dashboards/ai-spend.json`.
- Documents: `docs/TELEMETRY.md`, `k8s/README.md`, `config.example.yaml`, and the generated command references.
- Tests: `tests/test_k8s_monitoring_dashboards.py`, `tests/test_telemetry_instruments.py`, `tests/test_ai_spend_pricing.py`, `tests/test_ai_spend_ledger.py`, `tests/test_ai_spend_prometheus.py`, `tests/test_config_cmd.py` and `tests/test_ai_agent_capabilities.py`. The swallowed-failures ceiling of `src/devops_cli/ai/spend/pricing.py` in `tests/fixtures/swallowed_failures_ceilings.json` falls from 15 to 7.
- Tokens that processes sent before this change have no `local` label, so the savings panels count only the tokens of processes that run this change.

## Feasibility

- genai-prices 0.1.9, installed source: `DataSnapshot.find_provider_model` raises `LookupError` for a model that it does not know, and `_provider_lookup_error` builds a `LookupError` for a provider that it does not know. genai-prices logs nothing and gives no warning, so devops-cli logs the warning.
- An offline probe of the bundled snapshot gave `LookupError` for `gpt-4o-mni`, `gpt-9-preview` and `devops-chat`, $0.15 and $0.60 per million tokens for `gpt-4o-mini`, $2.50 and $10.00 for `gpt-4o`, and $0.02 and $0 for `text-embedding-3-small`.
- The live Prometheus, read-only through Grafana on 2026-10-24: over 30 days, savings divided by tokens was 2.9e-6 USD for the chat tokens of job `devops-cli` and 2.2e-7 USD for job `roadmap-service`. The two references are mixed, as the issue says. The token series have the labels `operation` and `type`.
- The prometheus chart 29.35.0 loads `/etc/config/recording_rules.yml` (`rule_files` of the live `prometheus-server` ConfigMap). Its `recording_rules.yml` was `{}`, and the evaluation interval is 1m.
- The live server evaluated `vector(0.6 / 1e6)` and the join `sum by (operation, type) (increase(devops_cli_ai_tokens_total[7d])) * on (operation, type) group_left max by (operation, type) (...)` with no error.
- The refined issue names #1673 as a dependency. #1673 is an Argo CD item. The embedding item, #1623, already added `ai.reference_embedding_model` and the `operation` label.
- On the base commit, the new tests failed: the tokens had no `local` label, the two processes sent different savings points, the recording rule did not exist, the savings queries read the removed counter, the ledger had no `pricing_source` column, `RequestCost` did not exist, `devops config show` logged no warning, and `src/devops_cli/commands/ai_cost.py` held the `gpt-4o-mini` literal.

## Existing Tool Considered

Prometheus recording rules and PromQL price the tokens at query time. genai-prices stays the source of every price, and the standard library `logging` module gives the warnings. Nothing is built. The change deletes the counter `AI_LOCAL_COST_EQUIVALENT_USD_TOTAL`, `_emit_local_cost_equivalent`, `_resolve_reference_model`, `PricingRegistry._check_override_cost` (a copy of `_get_override_pricing`) and `PricingRegistry._calc_exact_genai_cost`, which `_genai_prices_cost` replaces.
