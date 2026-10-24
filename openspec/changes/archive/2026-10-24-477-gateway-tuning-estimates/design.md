# Design

## Context

The `devops ai gateway tune` command evaluates AI gateway deployments for concurrency capacity and token cost.
Previously, the command generated synthetic probe requests to measure token cost.
It also executed load sweeps across all backends to find the saturation threshold.
Issue #477 requests reading token cost from real traffic in the spend ledger.
It also requests estimating capacity for changed deployments from prior measurements without sending network load.

## Goals / Non-Goals

**Goals:**
- Extract token cost per request from `SpendLedger` by matching backend identifiers or API base URLs.
- Fall back to synthetic cost probe requests only when spend data is absent for a backend.
- Provide a `--estimate` option on `devops ai gateway tune` that calculates capacity using GPU bandwidth scaling.
- Record the `estimate` flag in `Mechanism.GATEWAY_TUNE` run records.

**Non-Goals:**
- Mutating gateway configuration files or Kubernetes manifests during estimation.
- Replacing the active load sweep when `--estimate` is not passed.

## Decisions

- **Cost data retrieval**: Read backend token metrics from `SpendLedger.get_lifetime_report().backends`.
  - *Rejected alternative*: Querying gateway Prometheus metrics directly during tuning.
  - *Evidence for rejection*: The spend ledger already records and attributes token counts per request to the serving backend.
- **Capacity scaling method**: Scale measured capacity by the ratio of target GPU memory bandwidth to baseline GPU memory bandwidth.
  - *Rejected alternative*: Simulating token generation throughput via a synthetic simulator.
  - *Evidence for rejection*: Memory bandwidth scaling reliably predicts memory-bound LLM decode throughput without model simulation overhead.
- **Run persistence**: Save `estimate: bool` in `Mechanism.GATEWAY_TUNE` run payload.
  - *Rejected alternative*: Omitting estimated runs from persistent run storage.
  - *Evidence for rejection*: Persistent records allow auditing past estimates and comparing predicted capacity with future measurements.

## Risks / Trade-offs

- [No matching measured deployment] → Raise `GatewayTuneError` with a clear explanation when no prior run matches the target model and engine.
- [Missing spend data] → Automatically fall back to synthetic probe measurement when a deployment has no traffic recorded in the spend ledger.
