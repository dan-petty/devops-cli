# Proposal: #5495

## Why
An item can stop between two jobs with no failure line: no job is due by its own rule, and no person cause is recorded. The alert `RoadmapServiceItemStuck` currently reads only `blocked` and `ready` with a plan PR. It does not observe items stopped in other phases, and it fires for items worked by a unit or waiting with a recorded person cause. Tracker #5482 derives one phase for each item to drive stuck-item detection. Closes #5495.

## What Changes
- Add the pure function `phase(item)` in `src/devops_cli/roadmap/phase.py`. It derives the pipeline phase from labels, job records, and PR facts.
- Replace labels `{repo, state, plan}` with `{repo, phase}` for `devops_cli_roadmap_item_age_seconds` and `devops_cli_roadmap_oldest_item_number`.
- Add count gauge `devops_cli_roadmap_items{repo, phase}` and stalled items gauge `devops_cli_roadmap_stalled_items{repo, phase}`.
- Emit 0 once when a phase empties.
- Add setting `roadmap.stall.hours` with default 24.
- An item is stalled when phase age exceeds `roadmap.stall.hours`, no unit runs, and no claim or person cause exists.
- Update `RoadmapServiceItemStuck` alert expression to check for stalled items for 1 hour.
- Update dashboard panel "Oldest Item Age by State" to "Oldest Item Age by Phase" using label `phase`.
- Update `devops roadmap explain <n>` to print phase and phase age.

## Capabilities
- `roadmap-service-alerts`: alerts on stalled roadmap items across all active pipeline phases.
- `project-metrics-dashboard`: charts item age by phase and exposes item and stall gauges.
- `roadmap-explain`: displays the phase and phase age of an item.

## Impact
- Telemetry series `devops_cli_roadmap_item_age_seconds` and `devops_cli_roadmap_oldest_item_number` change labels from `(repo, state, plan)` to `(repo, phase)`.
- Dashboard panels and alert rules match the new `{repo, phase}` label set without shims.

## Feasibility
Confirmed against `k8s/devops/monitoring/prometheus-rules-values.yaml`, `src/devops_cli/github/metrics.py`, and `src/devops_cli/roadmap/stores/store.py`. promtool validates the alert rule structure.

## Existing Tool Considered
Prometheus gauges and alert rules carry the measurements. Existing age gauges and alerts update in place. No external tool derives the phases of this pipeline. Build requires about 300,000 tokens and 0.5 day.
