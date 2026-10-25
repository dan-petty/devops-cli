# Design

## Context

#1672 moved the price of local tokens from each process to Prometheus: devops-cli sends `devops_cli_ai_tokens_total{local="true"}`, and the AI spend dashboard multiplies the tokens by a reference price. Its intent stays: one reference for every process, and a test that compares each committed price with genai-prices. This change moves the prices from a recording rule to the dashboard, prices the series from before the labels, and makes gpt-4o the reference. See proposal.md for the evidence.

## Goals / Non-Goals

**Goals:**

- The savings panels show the local savings of any range in the retention window of Prometheus (30 d).
- The dashboard, `DEFAULT_AI_REFERENCE_MODEL` and `devops ai cost` price at one model, and git holds one copy of each price.

**Non-Goals:**

- The spend counter `devops_cli_ai_spend_usd_total` and the panels that read it do not change.
- The query of each savings panel keeps its window, its function and its grouping.

## Decisions

- **One reference model, gpt-4o.** The owner sets `ai.reference_model: gpt-4o`, and `devops ai cost` prices at it, so `DEFAULT_AI_REFERENCE_MODEL` becomes `gpt-4o`. #1672 rejected gpt-4o because it was the setting of one workstation. The owner chose it as the project default for #2194. `text-embedding-3-small` stays the embedding reference.
- **A hidden Grafana constant holds the prices.** The constant `reference_price_usd_per_token` holds a PromQL vector of one price for each operation and token type, and each savings query multiplies by `${reference_price_usd_per_token:raw}`. The raw format puts the value in unchanged, so the Prometheus data source does not escape its quotes (Grafana documentation, "Variable syntax"). A test reads the constant and compares each price with genai-prices. Rejected options:
  - Keep the recording rule. It has samples only from its first evaluation (2026-10-24T05:21:33Z), so each range that ended before that showed $0. A gap in rule evaluation also gives $0 at each point of the gap.
  - Backfill the rule with `promtool tsdb create-blocks-from rules`. A person runs it by hand on the server for each price change and each new range, and Argo CD cannot apply it.
  - Read the rule at a fixed time with the `@` modifier. The sample at that time leaves the retention window after 30 days, and PromQL has no `@ now()`.
  - Read the rule with `last_over_time(...[30d])`. It looks back in time, so a range that ended before the first sample still has no price.
  - Keep the rule and add the price as a constant after `or`. Then git holds two copies of each price, which can differ.
  - Write the price vector in each of the eight queries. Then git holds eight copies of each price.
  - One constant for each price, with the vector built in each query. Each query then holds about 450 more characters of the same `label_replace` calls, and the vector is still written eight times.
- **The savings queries count the series from before the labels.** A series without `local` is local when its provider is `gateway` and its server is not `cache`. Before #1672 the gateway served only local models: each model of `k8s/llm/gateway/config.yaml`, and of each earlier version of the gateway configuration in the retention window, is an Ollama or vLLM model at an in-cluster Service, and `store_model_in_db: false` stops other models. The response cache is no model (#816), and since #1672 a reply of the cache has `local="false"`. Chat is every operation other than `embeddings`, as in the panel "Response Cache Hit Share", because the counters did not record embedding requests before #1623. Rejected: set `operation="chat"` with `label_replace` on each series. A series from before #1623 and one from after it can then have the same labels, and PromQL refuses that output ("vector cannot contain metrics with the same labelset"). The queries add the chat tokens by token type first, and then set `operation="chat"` on the sums.
- **The mapping goes when its series leave the retention window.** The last sample without `local` was at about 2026-10-24T00:28Z. Prometheus keeps 30 d, so after about 2026-11-23 no range holds such a series. Prometheus deletes whole blocks, so check that `count(last_over_time(devops_cli_ai_tokens_total{local=""}[30d]))` is empty before the mapping is removed. A process that runs a devops-cli from before #1672 sends such series again; on 2026-10-24 none did, and `roadmap-service` has 0 replicas.
- **The test replays recorded answers of Prometheus.** `tests/fixtures/recorded_queries/ai_spend_local_savings.yaml` holds the query of the panel "Local Cloud Savings in Range", two ranges, the answer of the live Prometheus for each range, and the token series that it read. The test checks that the record is of the query of the panel, and that each answer is the total of the recorded series at the dashboard prices. The first range ends before the first sample of the rule, and its series have no `local` and no `operation`. The second range holds series with and without each label. Rejected: `promtool test rules` with synthetic series. No test, CI job or `tools.lock` entry uses promtool, and a stock GitHub runner does not have it. Rejected: a PromQL evaluator in Python. No maintained Python package evaluates PromQL, and the cost to write and keep one is far more than this item.
- **The guard of the default literal reads the context of the literal.** `test_only_the_defaults_name_the_default_reference_model` found the default by substring, but `gpt-4o` is also in `gpt-4o-mini`, in `openai/gpt-4o`, and in settings that are no reference. The test now finds a string that holds the whole model name, and whose string, call, keyword, assignment or parameter list mentions a reference. A test of the check shows that it finds the help text that #1672 removed.

## Risks / Trade-offs

- [A person changes a price in the dashboard and does not record again] → The replay test fails, because the recorded answer is at the old price.
- [genai-prices changes a reference price] → The price test fails on the next run. The author changes the constant and records the answers again, in a range inside the retention window.
- [A record over the old series cannot be made after about 2026-11-23] → That is also the time to remove the mapping, and the test of the record holds only while the mapping is in the queries.
