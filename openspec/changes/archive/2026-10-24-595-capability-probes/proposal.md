# Proposal

## Why

Issue #595 addresses inaccurate failover decisions that rely on model parameter counts.
Parameter counts do not show real deployment capabilities.
We need measured capability probes for each deployment to record verified model quality.

## What Changes

- Add a capability pass to `devops ai gateway tune`.
- Extend the in-pod runner in `gateway_bench.py` to return model reply text.
- Execute four capability probes: JSON adherence, tool choice, deep recall, and explicit prohibition.
- Send all probe prompts in the production prompted format without native tools or response formats.
- Score probe responses with deterministic evaluators in `pydantic_evals`.
- Record whether `response_repair.fix_llm_response` repaired the response.
- Persist probe results per deployment in the run store.
- Report capability pass results in table and JSON output formats.
- Mark unmeasured deployments clearly when probes do not run.

This change fits one pull request.

## Capabilities

### Modified Capabilities
- `gateway-tuning`: Adds capability probing and pass reporting in gateway tuning.

## Impact

- Extends `src/devops_cli/ai/gateway_bench.py` to capture and return response text.
- Updates `src/devops_cli/ai/gateway_tune.py` and `src/devops_cli/commands/ai_gateway.py`.
- Uses `pydantic_evals` for scoring probe runs.
- Persists probe outcomes in gateway tuning run records.

## Feasibility

The system premise was confirmed with local system checks:
- Verified `pydantic_evals` imports from installed `pydantic-ai` dependencies.
- Confirmed `Dataset`, `Case`, and `evaluate_sync(repeat=N)` execute with deterministic evaluators.
- Confirmed `fix_llm_response` populates the `was_repaired` property.
- Confirmed `gateway_bench.py` executes in the pod using only Python standard library.
- Confirmed run storage persists records through `Mechanism.GATEWAY_TUNE`.

## Existing Tool Considered

We evaluated the installed `pydantic_evals` package against building a custom test harness.
`pydantic_evals` already provides `Dataset`, `Case`, deterministic evaluators, and repeated execution.
Using `pydantic_evals` saves hundreds of lines of evaluation boilerplate code.
No internal code is deleted in this slice because parameter count floors remain until Slice 2.
