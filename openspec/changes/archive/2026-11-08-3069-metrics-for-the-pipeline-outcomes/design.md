# Design

## Context

The roadmap Service records pipeline outcomes in GitHub issue marks and comments.
Runner Jobs report their completion back to the Service in `_report` of `implement_submit.py`.
The Service exposes Prometheus metrics via `GLOBAL_METRICS` on `/metrics`.
See proposal.md for motivation and problem background.

## Goals / Non-Goals

**Goals:**
- Instrument runner Job outcomes with bounded metrics for jobs, repair rounds, tokens, and consecutive failure counts.
- Persist consecutive failure state across Service pod restarts.
- Add repository attribution to `devops_cli_roadmap_stage_total`.
- Record step repair rounds in the item job record.

**Non-Goals:**
- Dashboards, GitOps ConfigMap provisioning, and alert rules (deferred to #3655).
- Outcome-by-class counters for kept work (owned by #3650).

## Decisions

### Decision 1: Service `/metrics` transport for pipeline metrics
The Service emits the new metrics from `_report` via `GLOBAL_METRICS` on the `/metrics` endpoint with the `devops_cli_service_` prefix.
- **Rationale**: Matches `devops_cli_service_implement_failures_total` and the Service scrape pattern.
- **Alternative rejected**: Emitting via OTLP with `devops_cli_roadmap_pipeline_`. Rejected because OTLP histograms lack configurable buckets for token distributions, and mixing transports complicates scraping.

### Decision 2: Distinct `item_class` and `class` labels
Use `item_class` for Conventional Commit types (`CONST_BRANCH_TYPES`) and `class` for `FailureClass` values.
- **Rationale**: Keeps both label domains bounded and enables panels/alerts to filter along each dimension independently.
- **Alternative rejected**: Single `class` label. Rejected because it collapses commit types with failure classifications.
- **Alternative rejected**: Issue number in labels. Rejected because unbounded cardinality causes Prometheus memory leaks.

### Decision 3: Kept state record for consecutive failure gauge
Persist consecutive failure counts in a state record file (`service-consecutive-failures.json`) on the Service state volume.
- **Rationale**: Pod restarts must not reset consecutive failure counts to zero, ensuring alerting thresholds (e.g. 3 failures in a row) trigger reliably across rollouts.
- **Alternative rejected**: In-memory gauge only. Rejected because frequent deployments reset counts before alerts fire.

### Decision 4: Step repair rounds in the job record
Record `ImplementRecordKey.REPAIR_ROUNDS` on the item during step execution in `implement_run.py` and read it in `_report`.
- **Rationale**: The runner process observes `StepOutcome.repair_rounds`. Storing the count in `item.job_record` allows the Service to read it upon Job completion.

### Decision 5: Counter zero-priming at Service start
Prime all combinations of configured `repo` and known `item_class` / `result` at zero in `prime_service_counters`.
- **Rationale**: Prevents Prometheus `increase()` from losing the initial occurrence of newly observed label sets.

## Risks / Trade-offs

- [State record file corruption] → Use atomic file writes (`write_json_file(..., atomic=True)`) and fallback handling if unreadable.
- [Missing Conventional Commit type in issue title] → Default `item_class` to `"chore"`, ensuring all emitted series map to primed label sets.
