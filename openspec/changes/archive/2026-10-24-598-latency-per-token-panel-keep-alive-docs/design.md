# Design

## Context

The Latency row of `k8s/monitoring/dashboards/llm-stack.json` has two panels, each twelve columns wide: "Gateway Call Latency p95 per Deployment" and "Time to First Token p95 per Model". The gateway already exports `litellm_deployment_latency_per_output_token`, with the labels `api_base` and `litellm_model_name` (`tests/fixtures/metrics/litellm.yaml`). See proposal.md for the motivation and the evidence.

## Goals / Non-Goals

**Goals:**

- The dashboard shows the p50 and p95 of the latency per output token for each deployment, beside the time to the first token.
- The panel description says what LiteLLM 1.103.0 measures, so that nobody reads the value as the decode time.
- The Ollama manual and the `acquire_ollama_slot` docstring record the behaviour that the check of #598 found.

**Non-Goals:**

- A time-per-output-token histogram in `src/devops_cli/telemetry/instruments.py`, p50 and p95 in `devops ai cost report --by backend`, `/api/ps` in `devops ai gateway status`, and `keep_alive` on the chat bodies or `OLLAMA_KEEP_ALIVE` on each tier. Feasibility in proposal.md gives the evidence that rejected each of them.
- A change to the behaviour of `acquire_ollama_slot`.

## Decisions

- **Use the gateway's histogram and build no metric.** LiteLLM measures each call at the gateway, for every client, so one panel covers the direct and the pydantic-ai paths. Rejected: a histogram in devops-cli after the semantic convention `gen_ai.server.time_per_output_token`. It would measure only the calls of devops-cli, and it would repeat a metric that the gateway already exports.
- **Group by `api_base` and `litellm_model_name`.** A LiteLLM deployment is one model on one `api_base`, and a tier such as 64gib-standard serves more than one generation model. The latency per token of two models is different, so a group by `api_base` alone mixes them. The query matches `api_base!=""`, as the other deployment panels do.
- **Put three panels of eight columns in the Latency row.** The new panel is then beside the time-to-first-token panel, and no other row moves. Rejected: a new twelve-column panel below the row. It moves every row below it and is not beside the time-to-first-token panel.
- **Say in the description how LiteLLM gets the value.** For a call that is not streamed, it includes the prompt time, the wait in the Ollama queue and any model load. For a streamed call, it divides the time to the first token by the output tokens. Thus a high value can show a model load, which is the eviction cost that #598 asked to measure.

## Risks / Trade-offs

- [A new LiteLLM release can change how it computes the value] → The description names LiteLLM 1.103.0, the version of `k8s/llm/gateway/deployment.yaml`. A version bump reads the source again and changes the description if necessary.
- [The default buckets are coarse below 25 ms: 5 ms, 10 ms, 25 ms] → The description says that a quantile is an estimate between two bucket limits. LiteLLM gives no setting for the buckets of this histogram: `litellm.prometheus_latency_buckets` applies to other latency histograms only.
