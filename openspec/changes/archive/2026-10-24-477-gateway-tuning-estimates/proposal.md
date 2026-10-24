# Proposal

## Why

Issue #477 identifies that the AI gateway tuner measures token cost with synthetic prompt probes.
Measuring deployment capacity requires an active load sweep that loads every cluster backend.
With vLLM backends removed, lifetime counters are no longer available.
Real review traffic recorded in the spend ledger provides an accurate measurement source.
Prior tuning runs record measured capacity and GPU hardware information.

## What Changes

This change updates the AI gateway tuner to read token cost from the spend ledger.
The tuner falls back to synthetic probe requests when no spend data exists for a backend.
This change also adds an `--estimate` option to `devops ai gateway tune`.
The option estimates deployment capacity scaled by GPU memory bandwidth from a prior measured deployment.
The estimate runs without generating load on cluster backends.
Tuning run records persist the `estimate` setting.

This change fits in one pull request.

## Capabilities

### New Capabilities
- `gateway-tuning`: Measure and estimate AI gateway deployment capacity and request cost.

### Modified Capabilities
None.

## Impact

- CLI: Adds the `--estimate` option to `devops ai gateway tune`.
- Tuner: Reads tokens per review request from `SpendLedger`.
- Telemetry: Persists the `estimate` field in `Mechanism.GATEWAY_TUNE` records.
- Documentation: Updates the CLI command reference for `devops ai gateway tune`.

## Feasibility

I confirmed the premise against the real system:
- `SpendLedger.get_lifetime_report().backends` provides backend token metrics from real review traffic.
- `Mechanism.GATEWAY_TUNE` run records store deployment parameters, GPU specifications, and measured capacity.
- Scaling capacity by target and baseline GPU memory bandwidth produces an estimate without cluster traffic.

## Existing Tool Considered

No open tool calculates capacity estimates from our Kubernetes gateway deployments.
Building this feature directly in `devops_cli.ai.gateway_tune` requires approximately 200 lines of code.
It uses existing run records and spend reports.
The implementation deletes no external integrations.
