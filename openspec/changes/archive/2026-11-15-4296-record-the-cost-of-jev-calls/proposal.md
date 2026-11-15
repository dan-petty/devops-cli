# Proposal: #4296

## Why

Jev calls reach OpenRouter through the gateway pass-through, and LiteLLM records no spend for a
pass-through with no `cost_per_request`. The code records none either: the Jev calls run no
Agent, so the spend hook of `build_agent` never sees them. The spend ledger, `devops ai cost` and
the metrics miss every Jev call. Closes #4296.

## What Changes

- `record_jev_spend` records one ledger row for each decision answer, at the Jev price of the
  answer tokens. `decide_with_jev` calls it, and the Jev decision of `roadmap intake` calls it
  too.
- The pricing registry holds the Jev price, 0.042 USD per million input tokens and no output
  charge, as a built-in default. The Service ConfigMap sets the same rates.
- A ledger that raises, or an answer with no usage, leaves the Jev answer intact.

## Capabilities

`ai-spend-pricing`: three requirements for the record, the built-in price and the failure path.

## Impact

`devops ai cost` now counts Jev calls. No command, option, gateway config or image changes. The
extra SQLite write happens once for each decision call.

## Feasibility

Premise checked on 2026-11-15 against `origin/main` (ca62d6a9f): `decide_with_jev` calls
`DecisionModel.decide` with no spend record, and the four Jev call sites are `jev_ask`,
`route_with_jev`, `jev_completeness` and `intake_jev`. The new tests pass, and the Jev price
matches `k8s/README.md`.

## Existing Tool Considered

`track_request_spend` already writes the ledger, prices the call and emits the metrics. Nitro
`cost_per_request` on the pass-through gives a fixed cost, no token count, and writes the gateway
ledger that `devops ai cost` does not read. No new tool.
