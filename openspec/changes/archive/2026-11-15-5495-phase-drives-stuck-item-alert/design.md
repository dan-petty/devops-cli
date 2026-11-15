# Design

## Decisions
- **Pure `phase(item)` function**: Determine pipeline phase (`new`, `judged`, `ready`, `staged`, `planned`, `in-review`, `ready-for-review`, `merged`) from item labels, `item.job_record`, and pull request facts. Phases whose jobs are not yet built remain inactive.
- **Phase age calculation**: Measure time elapsed since the newest label event, record timestamp, or pull request event that set the phase.
- **Stall rule evaluation**: An item is stalled when its phase age exceeds `roadmap.stall.hours * 3600`, no cluster unit runs for it (identified by `roadmap.devops-cli/item`), it has no claim (`owner/*`), and it has no recorded person cause (`refine.next_step` waiting on person, `owner_question`, `implement.stopped`, `stage.needs_split`, or `blocked_by`).
- **Telemetry gauges**: Update `ROADMAP_ITEM_AGE` and `ROADMAP_OLDEST_ITEM` labels to `(repo, phase)`. Add `ROADMAP_ITEMS` and `ROADMAP_STALLED_ITEMS`. Emit 0 once when a previously present phase becomes empty.
- **Alert rule migration**: Change `RoadmapServiceItemStuck` to evaluate `sum by (repo, phase) (last_over_time(devops_cli_roadmap_stalled_items{job="roadmap-service"}[30m])) > 0` with `for: 1h`.
- **Dashboard update**: Update the dashboard panel in `k8s/devops/dashboards/project-metrics.json` to query `max by (phase) ...` under title "Oldest Item Age by Phase".

## Rejected alternatives
- **Keep separate state and plan labels**: Rejected because pipeline phases unify state and stage facts into one clean progression.
- **Add a second alert rule**: Rejected per issue instructions to replace the expression of `RoadmapServiceItemStuck` with no second stuck-item alert.
