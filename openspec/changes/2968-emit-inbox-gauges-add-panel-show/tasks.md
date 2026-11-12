# Tasks

## 1. Declare the inbox gauge

Reads: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/inbox_kind.py`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [ ] 1.1 `test_the_inbox_gauge_is_declared_with_the_repo_and_kind_labels` in `tests/telemetry/test_telemetry_instruments.py` fails on the base because `INSTRUMENTS` of `src/devops_cli/telemetry/instruments.py` holds no `devops_cli_roadmap_inbox_items`
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` fails on the base
- [ ] 1.2 In `src/devops_cli/telemetry/instruments.py`, add `ROADMAP_INBOX_ITEMS` beside `ROADMAP_CLAIM_AGE`: the name `devops_cli_roadmap_inbox_items`, the gauge kind, the unit `1`, and a description that names the labels `repo` and `kind` and says that only a run of `devops roadmap inbox` sends it. Add it to `INSTRUMENTS` and `__all__`. The case in `tests/telemetry/test_telemetry_instruments.py` asserts that `INSTRUMENTS` holds the name as a gauge of unit `1`, and that its description names `repo` and `kind`
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes

## 2. Send the gauge from the inbox command

Reads: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/telemetry/instruments.py`, `tests/roadmap/test_roadmap_inbox.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/support/fakes/roadmap_store.py`, `tests/support/fakes/otlp.py`. Changes: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/commands/roadmap.py`, `tests/roadmap/test_roadmap_inbox_gauges.py` (new).

- [ ] 2.1 `test_the_gauge_holds_the_count_of_each_kind_of_the_inbox` in `tests/roadmap/test_roadmap_inbox_gauges.py` fails on the base because no code emits `devops_cli_roadmap_inbox_items`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox_gauges.py` fails on the base
- [ ] 2.2 Add `emit_inbox_gauges(inbox: Inbox, *, repo: str) -> None` to `src/devops_cli/roadmap/inbox.py`. It counts the lines of `inbox.jobs` and `inbox.people` for each member of `InboxKind` and calls `emit(ROADMAP_INBOX_ITEMS, count, {"repo": repo, "kind": kind.value})`. Add it to `__all__`. Call it from `inbox_cmd` in `src/devops_cli/commands/roadmap.py` after `read_inbox` returns and before `render_inbox`. The test seeds `InMemoryRoadmapStore` with two blocked items and one New item that waits on a person, calls `read_inbox` and then `emit_inbox_gauges`, and reads `otlp.points("devops_cli_roadmap_inbox_items")`: 2 for `blocked`, 1 for `refine`, 0 for each other kind, each series with the repository name. The case of `tests/commands/test_all_commands_help_dryrun.py` imports `devops_cli.commands.roadmap` and runs the help of the roadmap app, so this step reads it and keeps it passing; the full gate runs it
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox_gauges.py` passes

## 3. Add the inbox panel to the project dashboard

Reads: `k8s/monitoring/dashboards/project-metrics.json`, `tests/grafana/test_grafana_dashboards.py`, `tests/telemetry/test_telemetry_instruments.py`, `src/devops_cli/telemetry/instruments.py`. Changes: `k8s/monitoring/dashboards/project-metrics.json`, `tests/grafana/test_grafana_dashboards.py`.

- [ ] 3.1 `test_the_inbox_panel_charts_each_kind_beside_the_age_panel` in `tests/grafana/test_grafana_dashboards.py` fails on the base because `k8s/monitoring/dashboards/project-metrics.json` holds no panel "Inbox Items by Kind"
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py` fails on the base
- [ ] 3.2 Add a timeseries panel to `k8s/monitoring/dashboards/project-metrics.json` at `gridPos` h 8, w 12, x 12 and y 34, beside "Oldest Item Age by State", with an id that no panel of the file holds, the title "Inbox Items by Kind", the unit `short`, a description that names `devops_cli_roadmap_inbox_items` and says that only a run of `devops roadmap inbox` sends it, one target with the query `sum by (kind) (last_over_time(devops_cli_roadmap_inbox_items[$__range]))` and the legend `{{kind}}`. Add the case beside `test_repository_dashboards_lint_clean`: it loads `k8s/monitoring/dashboards/project-metrics.json`, finds the panel by title, and asserts its query, its legend, its `gridPos` and that no panel box of the file overlaps it
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py` passes

## 4. Document the gauge, the panel and the digest reason

Reads: `docs/TELEMETRY.md`, `docs/roadmap/inbox.md`, `src/devops_cli/telemetry/instruments.py`, `k8s/monitoring/dashboards/project-metrics.json`. Changes: `docs/TELEMETRY.md`, `docs/roadmap/inbox.md`.

- [ ] 4.1 Run `uv run devops docs generate --sync-readme` so `docs/TELEMETRY.md` holds the row of `devops_cli_roadmap_inbox_items`, with its unit and its labels. Edit `docs/roadmap/inbox.md` to say that the counts of the command are the gauge `devops_cli_roadmap_inbox_items` by `repo` and `kind`, that the panel "Inbox Items by Kind" of the project dashboard shows them, and that the image digest that is not rolled is not read because the inbox reads GitHub only and the Service pod holds no cluster token; name the open item #4832 as the owner of that line
  - Verification: `$ uv run devops ci docs` passes
- [ ] 4.2 Edit `docs/TELEMETRY.md` and `docs/roadmap/inbox.md` to describe the gauge, the panel and the reason the digest line is not built
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 2: A test shows that the gauges equal the counts of the command, with a fake repository.
- Group 3: The panel JSON passes the dashboard checks of the repository.
- Group 4: A test shows the digest line, or the issue records why the line cannot be built.
- Group 4: `uv run devops ci` passes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
