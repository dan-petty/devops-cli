# Proposal

## Why

The inbox lists what waits for a person, but no metric counts its lines and no panel shows them, so the steward panels of #4780 cannot measure their targets and the age panel of #2919 has no neighbour. #2968 asks for the counts as gauges with a panel, and for the image digest that is not rolled, which the open item #4832 owns.

## What Changes

- Declare `devops_cli_roadmap_inbox_items` as a gauge of unit `1` in `src/devops_cli/telemetry/instruments.py`, and add it to `INSTRUMENTS` and `__all__`
- Send one value for each of the 13 kinds of `InboxKind` from `devops roadmap inbox`, by `repo` and `kind`, 0 for a kind with no line, through a new `emit_inbox_gauges` in `src/devops_cli/roadmap/inbox.py` that `inbox_cmd` calls
- Add the timeseries panel "Inbox Items by Kind" to `k8s/monitoring/dashboards/project-metrics.json` at x=12 and y=34, with the query `sum by (kind) (last_over_time(devops_cli_roadmap_inbox_items[$__range]))`
- Replace the clause that the panel "Oldest Item Age by State" leaves the right half of its row free, because the inbox panel fills that half
- Add the panel case to `tests/grafana/test_grafana_dashboards.py`, beside `test_repository_dashboards_lint_clean`, so one command runs the new case and the dashboard lint
- Document the gauge in `docs/TELEMETRY.md`, and the panel and the reason the digest line is not built in `docs/roadmap/inbox.md`
- Build no digest line: the inbox reads GitHub only and the Service pod holds no cluster token, and the open item #4832 owns the line
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `metric-instruments`: The inbox gauge is declared with the repo and kind labels, Each repository sends one inbox value for each kind
- `project-metrics-dashboard`: The project dashboard shows the inbox counts, The dashboard shows the age of the oldest item in each state

## Impact

- Code: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/commands/roadmap.py`, `k8s/monitoring/dashboards/project-metrics.json`
- Documents: `docs/TELEMETRY.md`, `docs/roadmap/inbox.md`
- Tests: `tests/telemetry/test_telemetry_instruments.py`, `tests/roadmap/test_roadmap_inbox_gauges.py`, `tests/grafana/test_grafana_dashboards.py`

## Feasibility

- The probes confirm the cited files word for word: "The path `src/devops_cli/roadmap/inbox.py` is a file of the staging commit." and "The path `src/devops_cli/telemetry/instruments.py` is a file of the staging commit."
- "The path `tests/telemetry/test_telemetry_instruments.py` is a file of the staging commit." and "The path `tests/grafana/test_grafana_dashboards.py` is a file of the staging commit."
- `read_file` of `src/devops_cli/roadmap/inbox_kind.py` showed 13 members at lines 14 to 26, from `src/devops_cli/roadmap/inbox_kind.py:14:PLAN = "plan"` to `PERSON = "person"`, so the command counts 13 classes and the gauge sends 13 series for each repository.
- `read_file` of `src/devops_cli/telemetry/instruments.py` showed `src/devops_cli/telemetry/instruments.py:410:ROADMAP_CLAIM_AGE = Instrument(` and `src/devops_cli/telemetry/instruments.py:402:ROADMAP_OLDEST_ITEM = Instrument(`, two gauges, so a new gauge joins the same list and is sent through `emit`.
- `search_code` for `inbox_cmd` showed `src/devops_cli/commands/roadmap.py:1006:def inbox_cmd(`, and `inbox = read_inbox(` sits inside it, so the command holds the repository name and the inbox of each repository.
- `read_file` of `k8s/monitoring/dashboards/project-metrics.json` showed `k8s/monitoring/dashboards/project-metrics.json:346:"gridPos": { "h": 8, "w": 12, "x": 0, "y": 34 },` and `k8s/monitoring/dashboards/project-metrics.json:349:"title": "Oldest Item Age by State",`, so the free right half of that row takes the inbox panel at x 12 and y 34.
- `read_file` of `tests/grafana/test_grafana_dashboards.py` showed `tests/grafana/test_grafana_dashboards.py:205:def test_repository_dashboards_lint_clean(dashboard_file: Path) -> None:`, which lints each JSON file of `k8s/monitoring/dashboards/`, so the new panel case and the lint case sit in one module and one verify runs both.
- `read_file` of `tests/telemetry/test_telemetry_instruments.py` showed `tests/telemetry/test_telemetry_instruments.py:185:def test_every_dashboard_query_names_a_metric_devops_cli_sends(dashboard: Path) -> None:`, so the new query must name an instrument that group 1 declares; group 1 runs before group 3. Its case at line 1473 asserts that no panel of the project dashboard overlaps another, and the inbox panel at x 12 leaves the age panel at x 0 free, so that case still passes.
- `read_spec` of `project-metrics-dashboard` gave the requirement "The dashboard shows the age of the oldest item in each state", whose text ends "It SHALL leave the right half of its row free.", and its only scenario "The queries of the panel", so the change replaces that text and keeps that scenario.
- The problem of the earlier reply is corrected: `search_code` for `roadmap_app` gave `tests/commands/test_all_commands_help_dryrun.py:17:from devops_cli.commands.roadmap import app as roadmap_app` and `tests/commands/test_all_commands_help_dryrun.py:71:(roadmap_app, ["--help"]),`, so that module is the existing case of the changed command module, and group 2 now reads it.
- The issue already records why the digest line cannot be built, word for word in its refine block: "The Service pod has no Kubernetes token, so the digest read needs a person's choice of credential or host. Refine files that line as a separate issue."
- `read_file` of `docs/roadmap/inbox.md` showed `docs/roadmap/inbox.md:30:The inbox leaves out an image digest that is not rolled yet.` with the read `devops argo cd apps status devops`, and `argo` is NOT_IN_RUNNER, so this change builds no digest line.
- `read_issue` of #4832 answered open, titled "feat(roadmap): list the image digest that is not rolled in the inbox", and says the Service pod has no Kubernetes token, so another item owns the line.
- `read_inbox` takes a `RoadmapStore`: a client of the GitHub API in production, and `InMemoryRoadmapStore` of `tests/support/fakes/roadmap_store.py` in the test, which needs no network.
- `roadmap_store.get_roadmap_store`, reached through `_open_store` in `src/devops_cli/commands/roadmap.py`, needs a client of the GitHub API and, without `--repo`, a checkout of the repository through `find_repo_root`.
- `emit` needs the tracer: it sends over OTLP in production, and the `otlp` fixture of `tests/support/fakes/otlp.py` installs a fake exporter, so the test reaches no network.
- The groups introduce no command and no option. The verifies run `uv run devops ci test` and `uv run devops ci docs`, and the image holds `uv`, `devops` and `pytest`. The failure classes are `test` for a failing case, and `lint` or `types` for the static checks of the gate. The pod runs with `readOnlyRootFilesystem: true` and `runAsNonRoot: true`, and the new test writes nothing outside `tmp_path`.
- The plan relies on no module constant of the staged tree: the gauge unit is the literal `1`, as `ROADMAP_OLDEST_ITEM` holds it, and the label set is the whole of `InboxKind`, whose 13 members bound the series of one repository.

## Existing Tool Considered

weaveworks/grafanalib (Apache-2.0, last activity 2025-12-08) is maintained and builds Grafana panels from Python code, but it covers only the panel JSON: it has no inbox read, no `emit` call, no dashboard lint and no image digest read. The change writes the panel JSON as a file and builds the gauge and the emit call itself: about 20k tokens to build, keep and fix, and about 3 hours of elapsed time. It deletes no internal code.

## Dependencies

None.
