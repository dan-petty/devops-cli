## Problem

The roadmap Service logs its round pause and the GraphQL points left after each round (#1400), but Prometheus has no series for either. An alert on a paused Service, or on a GraphQL budget near its floor, therefore needs Loki. A comment of 2026-10-08 folded this into #974; #974 was re-scoped on 2026-10-25 to the project dashboard, so it moves here.

## Proposed remedy

Two gauges, sent where the Service already logs the values:

- `devops_cli_service_paused_until_seconds`: the Unix time that the Service's round pause ends, or 0 when no pause holds.
- `devops_cli_github_graphql_remaining`: the GraphQL points left, from each round's closing budget read.

Both are gauges, so their names do not end in `_total`, and a dashboard reads them with `last_over_time(...[$__range])` (#974).

## Existing Tool Considered

The OTLP gauge path of `src/devops_cli/telemetry/instruments.py` (`InstrumentKind.GAUGE`), which the project metrics use.

## Acceptance criteria

- [ ] A round that pauses sends `devops_cli_service_paused_until_seconds` with the end of the pause, and a round with no pause sends 0; a test reads the captured gauge.
- [ ] Each round's closing budget read sends `devops_cli_github_graphql_remaining`; a test reads the captured gauge.
- [ ] `docs/TELEMETRY.md` lists both gauges.


Source: https://github.com/dan-petty/devops-cli/issues/974

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=bb46660c8d12e28520a25e8171ec300c627df0db -->
## Proposed design

### Problem statement
The roadmap Service logs its round pause end time and its remaining GitHub GraphQL points after each round. It sends neither value to Prometheus. An operator who wants to alert on a paused Service must query Loki. An operator who wants to alert on a low GraphQL budget must also query Loki. This issue adds two gauges so both values are available as Prometheus series.

### Acceptance criteria
- Criterion 1: A round that pauses sends `devops_cli_service_paused_until_seconds` with the Unix time the pause ends. A round with no pause sends 0.
  Verification: A test captures the gauge emission and asserts the value equals the pause end time, or 0 when no pause holds.
- Criterion 2: Each round's closing budget read sends `devops_cli_github_graphql_remaining` with the points left.
  Verification: A test captures the gauge emission and asserts the value equals the remaining GraphQL points.
- Criterion 3: `docs/TELEMETRY.md` lists both gauges in its metric table.
  Verification: The table in `docs/TELEMETRY.md` contains rows for `devops_cli_service_paused_until_seconds` and `devops_cli_github_graphql_remaining`.

### Key questions
- **What is the emission mechanism for the two new gauges?**: The `emit` function in `src/devops_cli/telemetry/instruments.py` handles gauge recording via `tracer.record_gauge`. The Service calls it at the points where it already logs the pause end time and the GraphQL budget, as delivered by #1400. [sources: src/devops_cli/telemetry/instruments.py]
- **Do the two gauges carry any labels?**: No. The issue names no labels for either gauge. Each gauge carries only the attributes the Service context already provides. (proposed)
- **Which test file verifies the gauge emissions?**: `tests/test_telemetry_instruments.py` checks each instrument query, as stated in the module docstring of `src/devops_cli/telemetry/instruments.py`. [sources: src/devops_cli/telemetry/instruments.py]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-record {"Effort": "Medium", "Owner": "Agent", "Priority": "P2-Medium", "Status": "Planned", "Value": "Medium", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "1f2ff968820d6bf7f7dcc057351ddfd2f0c95d9b852ad46fdba513e296fbdc23", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "ready", "refine.section_hash": "7d232e7b5a52a5f87e4e1811e2fe95a3fa63e754e3bdc8fd4224ff8e5c0976ca", "stage.branch": null, "stage.file_cap": null, "stage.groups": null, "stage.needs_split": null, "stage.pr": null, "stage.ready": null, "stage.sha": null} -->
