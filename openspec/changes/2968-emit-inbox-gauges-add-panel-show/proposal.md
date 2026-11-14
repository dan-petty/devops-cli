# Proposal

## Why

Issue #2968 records that `devops roadmap inbox` leaves two lines of #2915 unbuilt. No metric counts the inbox lines, so no Grafana panel shows the counts, and no issue owns the inbox panel that #2919 expects beside its age panel. The stage failure of an item also waits with no line that names it. This change sends one gauge for each counted kind of the inbox, adds the panel to the product dashboard, lists the stage failure as its own kind with a command that clears it, and records in the docs why the image digest line cannot be built where the Service runs.

## What Changes

- Declare `devops_cli_roadmap_inbox_items` as a gauge of unit `1` in `src/devops_cli/telemetry/instruments.py`, and list it in `INSTRUMENTS` and `__all__`.
- Add the tuple `COUNTED_KINDS` of nine kinds to `src/devops_cli/roadmap/inbox_kind.py`.
- Add `emit_inbox_counts` to `src/devops_cli/roadmap/inbox.py`, and call it from `inbox_cmd` in `src/devops_cli/commands/roadmap.py` after `read_inbox` returns.
- Add the kind `stage_retry` to `InboxKind`, its heading, subject and clear texts, and a line in `read_inbox` for each open item whose job record holds `stage.failed_class`; the clear text runs `devops roadmap stage --item` with `--confirm`.
- Add the panel "Inbox Items by Kind" to `k8s/devops/dashboards/project-metrics.json` at x 12 and y 34, and its case to `tests/grafana/test_grafana_dashboards.py`, the module that also lints the file.
- Regenerate `docs/TELEMETRY.md` with `uv run devops docs generate`, add the class and the gauge to `docs/roadmap/inbox.md`, record there why the image digest line needs the cluster and that #4832 owns it, and update the planned-changes row of `docs/ROADMAP_WORKFLOW.md`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-inbox`: The inbox lists each item whose stage job failed
- `metric-instruments`: The inbox gauge is declared and documented, The inbox command sends the count of each counted kind, The inbox gauge holds one series for each counted kind of each repository
- `project-metrics-dashboard`: The dashboard shows the count of each inbox kind, The dashboard shows the age of the oldest item in each state

## Impact

- Code: `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/commands/roadmap.py`, `k8s/devops/dashboards/project-metrics.json`
- Documents: `docs/TELEMETRY.md`, `docs/roadmap/inbox.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_inbox.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/roadmap/test_roadmap_inbox_gauges.py`, `tests/grafana/test_grafana_dashboards.py`

## Feasibility

- `probes` confirms the inbox module: "The path `src/devops_cli/roadmap/inbox.py` is a file of the staging commit."
- `probes` confirms the dashboard: "The path `k8s/devops/dashboards/project-metrics.json` is a file of the staging commit."
- `probes` shows that the stage failure key is a record key and no path: "The path `stage.failed_class` is no file of the staging commit. No commit in the history deleted or renamed it." `read_file` of `src/devops_cli/roadmap/stores/store.py` gave `src/devops_cli/roadmap/stores/store.py:270:FAILED_CLASS = "stage.failed_class"`, a member of `StageRecordKey`, so the `stage_retry` kind can be built.
- `read_file` of `src/devops_cli/roadmap/inbox_kind.py` showed 13 members, from `src/devops_cli/roadmap/inbox_kind.py:14:PLAN = "plan"` to `src/devops_cli/roadmap/inbox_kind.py:26:PERSON = "person"`. `STAGE_RETRY` makes 14, `COUNTED_KINDS` holds nine, and the test `test_the_counted_kinds_are_the_nine_item_kinds` decides each of the other five.
- The clearing step of the `stage_retry` line is a command that acts. `read_file` of `src/devops_cli/lang/en/help.py` gave `src/devops_cli/lang/en/help.py:1801:"Stage the one issue this number names, when it is open and Ready, and ignore the filter "` and `read_file` of `src/devops_cli/commands/roadmap.py` gave `src/devops_cli/commands/roadmap.py:455:confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.stage_confirm)] = False,`, and `docs/roadmap/stage.md:119:takes the item at once.` states that `--item` takes the item at once. `devops roadmap explain` only reads, so no line names it as the step that clears a wait.
- `search_code` for `roadmap_inbox_items` found the name in no module of `src/` and in no test module; only the fixtures of the closed plan #4963 name it, so the gauge is new. `read_file` of `src/devops_cli/telemetry/instruments.py` gave `src/devops_cli/telemetry/instruments.py:705:PROJECT_TRAFFIC_VIEWS = Instrument(` with the unit `1`, and `src/devops_cli/telemetry/instruments.py:779:INSTRUMENTS: tuple[Instrument, ...] = (`.
- `read_file` of `src/devops_cli/commands/roadmap.py` showed `src/devops_cli/commands/roadmap.py:1071:inbox = read_inbox(`, `src/devops_cli/commands/roadmap.py:1079:write_stdout(render_inbox(inbox, repo=target, kinds=kinds)` and the dry-run return at `src/devops_cli/commands/roadmap.py:1063:if dry_run or is_dry_run():`, all inside the loop over targets, so the emitter has a call site and a dry run sends nothing.
- `read_file` of `k8s/devops/dashboards/project-metrics.json` showed `k8s/devops/dashboards/project-metrics.json:346:"gridPos": { "h": 8, "w": 12, "x": 0, "y": 34 },` and `k8s/devops/dashboards/project-metrics.json:349:"title": "Oldest Item Age by State",`, and the next row starts at y 42, so the free right half takes the panel at x 12 and y 34.
- The panel group verifies the dashboard lint itself. `read_file` of `tests/grafana/test_grafana_dashboards.py` gave `tests/grafana/test_grafana_dashboards.py:180:def test_repository_dashboards_lint_clean(dashboard_file: Path) -> None:` and `tests/grafana/test_grafana_dashboards.py:35:_PRODUCT_DASHBOARDS = REPO_ROOT`, so the parametrized case lints the product dashboards: one command runs the lint and the new case.
- `read_file` of `docs/roadmap/inbox.md` showed `docs/roadmap/inbox.md:30:The inbox leaves out an image digest that is not rolled yet. To read it, run `devops argo cd apps status devops`.` The page names the read but no reason, so the docs group records the reason there and names #4832. The Runner entry of `CONTEXT.md` says the pod has no Kubernetes token, which is why the read cannot run where the Service runs.
- `read_file` of `tests/roadmap/test_roadmap_inbox.py` showed the imports `StageRecordKey`, `encode_job_record` and `with_record`, so the fake repository can hold a job record with `stage.failed_class`. `search_code` for `test_roadmap_inbox_gauges` found the name in no test module of the commit, so `tests/roadmap/test_roadmap_inbox_gauges.py` is new.
- Precondition of each call: `read_inbox` and `emit_inbox_counts` take a store, and the tests give the `InMemoryRoadmapStore` of `tests/support/fakes/roadmap_store.py`, so no test needs a checkout, a client or a network. `inbox_cmd` calls `_open_store` for a GitHub client, and no test of this plan calls `inbox_cmd`.
- The plan introduces no command and no verify program: each verify is an existing row, `uv run devops ci test` or `uv run devops ci docs`, and the runner image lists `uv`, `devops` and `pytest`. No failure class is new, and the pod settings of the runner stay as they are.
- `search_code` for `docs generate` gave `docs/ROADMAP_WORKFLOW.md:311:Write the generated documents in the docs directory of the checkout`, the row of the command with no option, and `search_code` for `2968` gave `docs/ROADMAP_WORKFLOW.md:513:| #2968 | All | The counts of `devops roadmap inbox` are gauges with a Grafana panel, and the inbox lists an image digest that is not rolled |`, the row that the docs group replaces.
- The rejected plan of #4963 is answered on each of its points: the docs step runs `uv run devops docs generate` with no option, because #5198 removed `--sync-readme`; `COUNTED_KINDS` holds nine kinds, so seven repositories give 63 series and not the 91 of all kinds; `stage.failed_class` is a record key, so the `stage_retry` kind is planned, with `devops roadmap stage --item` as its clearing step and not `devops roadmap explain`, which writes nothing.
- The first checks of the implementation against the real system: `uv run devops ci test tests/roadmap/test_roadmap_inbox.py`, then `uv run devops ci test tests/telemetry/test_telemetry_instruments.py`, then `uv run devops ci test tests/grafana/test_grafana_dashboards.py`, then `uv run devops ci docs`.

## Existing Tool Considered

weaveworks/grafanalib (https://github.com/weaveworks/grafanalib), Apache-2.0, last activity 2025-12-08, is maintained. It builds Grafana panel JSON from Python code, so it can produce the inbox panel. It holds no inbox read, no gauge emission through `emit` and no check against the dashboard lint of this repository. The change writes the gauge, the emitter and the panel itself: about 310 lines, about 40k tokens to build, keep and fix, and about 8 hours of work, plus the upkeep of one instrument and one panel. No internal code is deleted.

## Dependencies

- #5528 also changes `docs/TELEMETRY.md` and `src/devops_cli/telemetry/instruments.py`. This change adds one instrument and one generated row, so whoever merges second regenerates the document.
- #5594 also changes `src/devops_cli/commands/roadmap.py`. This change adds one call in `inbox_cmd`, and the two edits touch different lines of the file.
