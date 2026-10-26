# Proposal

## Why

Issue #2263: the panels "Items by Milestone" and "Active Items by State" of the Project & Engineering Velocity dashboard show 0 open items while 239 issues are open.

`devops_cli_project_items` takes its counts from the REST milestones: `open_issues` and `closed_issues` of each milestone.
Intake puts a new item in the backlog with no milestone, and a person plans milestones.
When no milestone is open, the gauge has no open item to count.
The description of the instrument names the labels milestone, type, priority and state, but the emitter sends only `milestone` and `state`.

## What Changes

- The gauge counts the items of the project board. The roadmap store reads them: each item has the state and the labels of its issue, its milestone, and its board Priority.
- The gauge has the labels `milestone`, `state`, `type` and `priority`. An item with no milestone, no `type/*` label or no Priority has an empty value for that label.
- A label set that had items in the last snapshot and has none in this one is sent once with the value 0. A series that stops arriving keeps its last value in `last_over_time(...[$__range])`, so without the 0 the panels count items that left that label set.
- `collect_project_metrics_report` reads the items through the roadmap store of the job (the Service) or through the board that `.github/roadmap.toml` names (the command). `devops gh metrics` fails when the store cannot read the board, so a failed read never shows as an empty board.
- The milestone loops that fed the gauge from the REST milestone counts are deleted. `MilestoneMetric` stays for the milestone table of `devops gh metrics`.
- The two panels and `docs/TELEMETRY.md` describe what the gauge counts. The panel "Items by Milestone" shows an item with no milestone as `none`.
- The change carries a spec delta: the labels of a gauge and the dashboard panels are observable. It fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-metrics-dashboard`: adds the requirements for what the items gauge counts and for the panels that read it.

## Impact

- Code: `src/devops_cli/github/metrics.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/telemetry/instruments.py`.
- Dashboard: `k8s/monitoring/dashboards/project-metrics.json`.
- Documentation: `docs/TELEMETRY.md`.
- Tests: `tests/test_github_metrics.py`, `tests/test_telemetry_instruments.py`, `tests/conftest.py` (the reset of the sent series).

## Feasibility

- The premise holds. The query `sum by (state) (last_over_time(devops_cli_project_items[7d]))` on the cluster's Prometheus returns `closed` 928 and `open` 0. The series come from the snapshot that was sent by hand: 51 milestones with two series each.
- `GitHubRoadmapStore.items()` returns every issue on the board with `state`, `labels`, `milestone`, `status` and `priority`. A test reads them through `GitHubFake`, the `gh` process edge.
- The tracer flushes gauges with DELTA temporality. A probe with the OpenTelemetry SDK shows that a gauge series that is not set again is not in the next flush. Prometheus keeps the last sample of that series, and `last_over_time(...[$__range])` returns it. The probe is the reason for the 0 value of a label set that has no items.
- Not confirmed: the numbers on the live dashboard after the change. The roadmap Service has 0 replicas, so no snapshot arrives. The same gauge also reaches Prometheus through the scrape of the Service pod and through OTLP. On 2026-10-08, `sum by (job, state)` of the old `devops_cli_project_items_total` returned 8 open items for `kubernetes-pods` and 4 for `roadmap-service`, so a `sum by (state)` adds two sources. This is a different cause, in how the dashboards read a gauge with two sources. It is #2288, and this change does not hide it.

## Existing Tool Considered

The roadmap store (`RoadmapStore.items()`) and `open_roadmap` already read the board and join it with the issues. This change reuses them and adds no library and no new GitHub call path.
The change deletes the two loops that send `PROJECT_ITEMS` from `MilestoneMetric` in `emit_project_metrics_telemetry` and `_record_workflow_and_milestone_metrics`.
