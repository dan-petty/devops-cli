# Proposal

## Why

Issue #2968 records that `devops roadmap inbox` leaves two lines of #2915 unbuilt.
No metric counts the inbox lines, so no Grafana panel shows the counts.
No issue owns the inbox panel that #2919 expects beside its age panel.
The stage failure of a Ready item also waits with no line naming it.
The 2026-11-13 owner decision on #2968 (tracker #5482, Phase 5) adds person cause gauges, a daily inflow cap, an alert, and a 7-day live proof.
This change sends the inbox and cause gauges from the Service metrics row and inbox command, adds the bar gauge panel, and documents why image digests require cluster access (#4832).

## What Changes

- Declare `devops_cli_roadmap_inbox_items` as a gauge of unit `1` in `src/devops_cli/telemetry/instruments.py`, with labels `repo` and `kind`.
- Declare person cause instruments for inflow, outflow, and age across typed causes (`premise_reject`, `owner_question`, `supervise_cap`, `watch_cycles`, refine waits, `intake.duplicate_of`).
- Add the tuple `COUNTED_KINDS` of eight active kinds (`blocked`, `refine`, `split`, `alternatives`, `failed`, `stage_retry`, `claim`, `labels`) to `src/devops_cli/roadmap/inbox_kind.py`, leaving `queue` out.
- Add `emit_inbox_counts` to `src/devops_cli/roadmap/inbox.py`.
- Call `emit_inbox_counts` in the Service metrics row (`src/devops_cli/roadmap/run.py:906`, `_run_metrics_adapter`) and in `inbox_cmd` (`src/devops_cli/commands/roadmap.py`), normalizing repositories with `RepoRef(repo).key`.
- Add `stage_retry` to `InboxKind` and list it in `read_inbox` only for Ready items whose job record holds `stage.failed_class`.
- Add the bar gauge panel "Inbox Items by Kind" to `k8s/devops/dashboards/project-metrics.json` at x 12, y 34, satisfying docs/DESIGN.md rule C15.
- Add an alert rule for person cause daily inflow exceeding the daily cap in `k8s/devops/alerts/inbox.yaml`.
- Plan a post-merge comment documenting 7 days of live gauge values.
- Regenerate `docs/TELEMETRY.md` and `docs/commands/roadmap.md` with `uv run devops docs generate`.
- Update `docs/roadmap/inbox.md` and `docs/ROADMAP_WORKFLOW.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-inbox`: The inbox lists each item whose stage job failed
- `metric-instruments`: The inbox gauge is declared and documented, The metrics row and inbox command send the count of each counted kind, The inbox gauge holds one series for each counted kind of each repository, Person cause gauges are declared and emitted
- `project-metrics-dashboard`: The dashboard shows the count of each inbox kind, The dashboard shows the age of the oldest item in each state

## Impact

- Code: `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/commands/roadmap.py`, `k8s/devops/dashboards/project-metrics.json`, `k8s/devops/alerts/inbox.yaml`
- Documents: `docs/TELEMETRY.md`, `docs/roadmap/inbox.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/commands/roadmap.md`
- Tests: `tests/roadmap/test_roadmap_inbox.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/roadmap/test_roadmap_inbox_gauges.py`, `tests/roadmap/test_roadmap_run_metrics.py`, `tests/grafana/test_grafana_dashboards.py`

## Feasibility

- `src/devops_cli/roadmap/inbox.py` and `k8s/devops/dashboards/project-metrics.json` exist.
- `_run_metrics_adapter` runs in `src/devops_cli/roadmap/run.py:906` on every Service metrics round.
- Calling `read_inbox` and `emit_inbox_counts` in the metrics adapter adds one cached issue read per repository.
- `COUNTED_KINDS` holds eight active kinds, yielding 56 series for seven repositories, below the 63 series cap.
- `read_inbox` checks `item.status == ItemStatus.READY` to avoid false counts from historical failures.
- `docs/DESIGN.md` rule C15 requires a bar gauge for breakdowns with more than three entities.
- The bar gauge uses PromQL `sum by (kind) (last_over_time(devops_cli_roadmap_inbox_items[$__range]))`.
- Person cause gauges track inflow, outflow, and age for typed causes.
- The alert rule triggers when person cause daily inflow exceeds the configured cap.
- A 7-day live proof comment will verify gauge telemetry after merging.
- Image digest inspection requires cluster credentials and belongs to #4832.
- Preconditions use fakes in tests with no external network required.

## Existing Tool Considered

weaveworks/grafanalib (Apache-2.0, maintained) builds Grafana JSON from Python. It lacks inbox reads, telemetry emission, and repository lint checks. Writing the bar gauge panel directly into dashboard JSON needs no generator dependencies and costs about 310 lines and 40k tokens.

## Dependencies

None.
