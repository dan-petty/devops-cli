# Design

## Context

See `proposal.md` for motivation.
Inference backends accept traffic only from inside the cluster gateway pod.
`gateway_bench.py` executes inside an ephemeral container attached to the gateway pod using the standard library alone.
Evaluation and scoring occurs on the CLI side where `pydantic_evals` is available.

## Goals / Non-Goals

**Goals:**
- Capture response text in `gateway_bench.py` when `return_replies` is enabled.
- Execute four standardized capability probes (JSON adherence, tool choice, deep recall, explicit prohibition) in production prompted format.
- Evaluate responses on the CLI side with `pydantic_evals.Dataset` and deterministic evaluators.
- Track `was_repaired` using `response_repair.fix_llm_response`.
- Persist results per deployment in `Mechanism.GATEWAY_TUNE` run records.
- Report measured pass rates or unmeasured status in CLI outputs.

**Non-Goals:**
- Routing configuration changes or removal of parameter-count floors (deferred to Slice 2).
- Client-side floor check on `served_by` (deferred to Slice 3).
- Sending network load during `--estimate` runs.

## Decisions

### 1. In-pod reply capture
`gateway_bench.py` extends `run_level` with an optional `return_replies` parameter.
When enabled, successful request replies are collected and returned.
- *Rejected Alternative*: Always return reply text for every request in all levels.
- *Evidence for Rejection*: Standard capacity sweeps send hundreds of requests. Returning all replies exhausts JSON buffer memory and pipeline pipe limits.

### 2. Prompted probe format
The four probes use production prompt text without native tools or response formats.
- *Rejected Alternative*: Use native API `tools` and `response_format` parameters.
- *Evidence for Rejection*: Upstream reviews do not use native tools. Several backend inference engines reject or drop native tool parameters.

### 3. CLI-side evaluation
Probes are scored on the CLI side using `pydantic_evals`.
The runner inside the pod returns raw reply strings.
- *Rejected Alternative*: Execute `pydantic_evals` inside the gateway pod container.
- *Evidence for Rejection*: The debug pod runs `python:3.14-slim` with standard library only. Installing external packages inside the pod adds latency and requires network access.

## Risks / Trade-offs

- [Prompt length exceeds deployment context window] → Use `deployment_prompt_tokens` to cap probe prompts.
- [Probes add execution time to tune command] → Keep probes concise and execute at temperature 0 with single concurrency.
