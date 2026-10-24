# Design

## Context

A review has four stage flags (`ReviewStageFlags`): `pre_analysis`, `static_scan`, `group_analysis` and `reporting`. The runner profiles three stages: `pre_analysis`, `payloads` and `report`. The payloads stage (`init_per_file_payloads`) runs the static analyzers, then the Ruff, mypy and C901 complexity evidence, then assembles one payload for each file. Only the analyzers checked the `static_scan` flag.

## Goals / Non-Goals

**Goals:**

- A review with the static scan off starts no analyzer, no evidence tool and no tool canary.
- `--pre-analysis-only` starts no tool after the pre-analysis.

**Non-Goals:**

- Move mypy onto the tool executor. #1978 does that.
- Change the speed work of #2034 in the mypy and osv-scanner adapters.

## Decisions

### 1. The static scan flag gates the evidence

`init_per_file_payloads` calls `_run_review_evidence` in the same branch as `_run_static_scanners`. The evidence is tool output, as the analyzer findings are, and the admission of both uses `_admit_scanner_findings`.

- **Rejected alternative: the runner stops after pre-analysis when no later stage is on.** This change would fix `--pre-analysis-only` only. `--no-static-scan` and `--reporting-only` would still start Ruff and mypy, and `docs/SELF_IMPROVEMENT.md` says that a `--no-static-scan` benchmark runs no scanners. The cause is the evidence call that no flag gates, so the fix is at that call.
- **Rejected alternative: a fifth stage flag for the evidence.** No command or document asks to run the evidence without the analyzers, or the analyzers without the evidence. A new flag adds two options and no consumer.

## Risks / Trade-offs

- [Risk] A review with `--no-static-scan` has no complexity delta table in `review.md`. → This is the purpose of the option: the review holds no tool findings. A review that needs the table runs with the static scan on.
