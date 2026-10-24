# Design

## Context

`track_request_spend` in `src/devops_cli/ai/spend/ledger.py` prices each call and sends its metrics. A local call also sent its savings in USD, priced at the reference models of the process. The workstation sets `ai.reference_model: gpt-4o`, and the cluster ConfigMap sets none, so the Service used the default `gpt-4o-mini`. See proposal.md for the evidence.

## Goals / Non-Goals

**Goals:**

- Every process is priced at one reference on the dashboard, and the reference prices cannot drift from genai-prices.
- A model or a reference model with no price gives a warning and a record, not a silent $0.

**Non-Goals:**

- A hosted gateway call is priced at the deployment model that the gateway names, not at the route name (#2031). With this change, such a call logs the warning and records the source `unknown`.

## Decisions

- **Prometheus prices the local tokens at query time.** devops-cli sends `local` on the token counter, and a recording rule holds the price of each operation and token type. Rejected: keep the price in each process and add a `reference_model` label to the savings counter, with `ai.reference_model` set in the cluster ConfigMap. The dashboard then still adds savings of two references when one process has another setting, and a changed reference does not change the savings already sent.
- **A `local` label, not a second token counter.** Rejected: `devops_cli_ai_local_tokens_total`. It sends each local token twice, and the token panels stay as they are with a label.
- **A recording rule, not a dashboard constant.** Rejected: Grafana constant variables. Only that dashboard can read them, and a test cannot compare them with genai-prices as easily as a rule in the Helm values.
- **The default reference models price the dashboard.** The rule holds the prices of `DEFAULT_AI_REFERENCE_MODEL` (`gpt-4o-mini`, set by #1158) and `DEFAULT_AI_REFERENCE_EMBEDDING_MODEL` under `DEFAULT_AI_REFERENCE_PROVIDER`. Rejected: `gpt-4o`, the setting of one workstation and not the project default. `ai.reference_model` and `ai.reference_embedding_model` now price only the local ledger that `devops ai cost` reports.
- **The rule has a `reference_model` label, and the queries take `max by (operation, type)` of it.** The label shows which model a price belongs to. When a person changes a reference, a range query can find the series of the old label and of the new label for one operation and type. `max by` keeps the join one-to-one.
- **A price is written as USD per million tokens, `vector(<price> / 1e6)`.** genai-prices lists prices per million tokens, so a person can compare the rule with genai-prices by eye.
- **An unpriced value is None.** `ReferencePricing.cost` is None when a kind of token in the tokens has a reference model with no price. Embedding tokens keep their price when only the chat reference has none. Rejected: 0 with a flag, because a reader of the JSON output or a scrape takes 0 as a price.
- **One warning for each model in a process.** The pricing registry keeps the models that it warned about. A process keeps one registry, so a `/metrics` scrape or a long review warns once.

## Risks / Trade-offs

- [The savings panels count only tokens with the `local` label] → The panels count from the time each process runs this change. The old counter stays in the TSDB until the 30-day retention removes it, and no query reads it.
- [genai-prices changes a default reference price] → The rule test fails on the next run, and the author changes the rule.
