# Design

## Decisions

- **Emit inbox gauges in the Service metrics row and in `inbox_cmd`.**:
  The metrics row in `_run_metrics_adapter` (`src/devops_cli/roadmap/run.py:906`) sends gauges during regular Service cycles.
  `inbox_cmd` also sends them on demand.
  `repo` is normalized to `RepoRef(repo).key` following ADR 0022.
- **Count the eight active kinds and omit `queue`.**:
  `COUNTED_KINDS` holds 8 kinds: `blocked`, `refine`, `split`, `alternatives`, `failed`, `stage_retry`, `claim`, and `labels`.
  `queue` is excluded.
  8 kinds across 7 repositories produce 56 series, safely below the 63 series cap.
  Issue #3077 will add `owner` as the ninth kind (63 series).
- **Scope `stage_retry` strictly to Ready items.**:
  Only items with Status `Ready` and `stage.failed_class` get a `stage_retry` line.
  Items in `New` or `Blocked` retain historical `stage.failed_class` marks without triggering false retry lines.
- **Format the panel as a bar gauge per DESIGN.md rule C15.**:
  DESIGN.md rule C15 requires a bar gauge or sorted table for breakdowns of more than 3 entities.
  The panel uses type `bargauge` with unit `short` and query `sum by (kind) (last_over_time(devops_cli_roadmap_inbox_items[$__range]))`.
- **Implement person cause telemetry, daily cap alert, and live proof per 2026-11-13 owner decision.**:
  Emit inflow, outflow, and age for typed person causes (`premise_reject`, `owner_question`, `supervise_cap`, `watch_cycles`, refine waits, `intake.duplicate_of`).
  Configure an alert rule when daily inflow exceeds the cap.
  A post-merge comment provides 7 days of live proof values.
- **Hand-write panel JSON in `k8s/devops/dashboards/project-metrics.json` at x 12, y 34.**:
  The dashboard lint checks JSON files directly without needing external generator dependencies.
- **Regenerate documentation with `uv run devops docs generate`.**:
  Update `docs/TELEMETRY.md`, `docs/commands/roadmap.md`, and document why image digests require cluster access (#4832).

## Rejected alternatives

- **Use a timeseries line chart for inbox kinds.**:
  Rejected. `docs/DESIGN.md` rule C15 forbids line charts for breakdowns of more than three entities.
- **Send gauges only from the manual CLI command.**:
  Rejected. Dashboard panels and live proof require automated telemetry from the Service metrics row.
- **Include `queue` in `COUNTED_KINDS`.**:
  Rejected. Including `queue` would exceed the 63 series cap when #3077 adds `owner`.
- **Check all open items for `stage.failed_class`.**:
  Rejected. Items returning to New or Blocked retain failure classes, causing false retry counts.
- **Adopt weaveworks/grafanalib.**:
  Rejected. It adds generator overhead and dependencies for a single panel.
- **Implement cluster image digest checks here.**:
  Rejected. Service pods lack cluster credentials; #4832 owns this feature.

## Security

The panel JSON crosses into the monitoring stack and contains no secrets, hosts, or private addresses.
The dashboard lint validates JSON structure and PromQL safety.
Telemetry emission uses standard OTLP conduits without privileged escalation.
