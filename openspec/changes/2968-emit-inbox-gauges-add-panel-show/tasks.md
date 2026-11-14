# Tasks

## 1. List each open item whose stage job failed

Kind: behavior. Reads: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_inbox.py`. Changes: `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_inbox.py`.

- [ ] 1.1 `test_a_stage_job_that_failed_has_one_line_naming_its_class` in `tests/roadmap/test_roadmap_inbox.py`: the fake repository holds an open item whose job record holds `stage.failed_class` with the value `limit_reached`, and `read_inbox` returns one line of the class `stage_retry` whose subject names `limit_reached` and whose clearing step names `devops roadmap stage --item` with the number of the item. `test_a_stage_job_that_has_no_class_has_no_line` asserts that an item with no `stage.failed_class` gives no such line
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox.py` fails on the base
- [ ] 1.2 Add `STAGE_RETRY = "stage_retry"` to `InboxKind` after `FAILED`. Add the heading "Items whose stage job failed", the subject "{title}: the stage job failed with the class {failure_class}" and the clear text "Fix the cause, then run `devops roadmap stage --item {number} --repo {repo} --confirm` to take the item at once" to `inbox_headings`, `inbox_subjects` and `inbox_clears` of `MESSAGES.roadmap`. Add `_stage_retry_lines(items, repo, now)`, which reads `StageRecordKey.FAILED_CLASS` from the job record of each open item, and splice it into `read_inbox` after `_failed_lines`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox.py` passes

## 2. Declare the inbox gauge in the instrument list

Kind: behavior. Reads: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/telemetry/test_consolidation_serialization.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [ ] 2.1 `test_the_inbox_gauge_is_a_declared_instrument` in `tests/telemetry/test_telemetry_instruments.py`: `INSTRUMENTS` holds `devops_cli_roadmap_inbox_items` with kind Gauge, unit `1` and a description that names `repo` and `kind`
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` fails on the base
- [ ] 2.2 Add `ROADMAP_INBOX_ITEMS` to `src/devops_cli/telemetry/instruments.py` beside `ROADMAP_CLAIM_AGE`, as a gauge of unit `1` with the description "Inbox lines that wait for a person, by repository and kind. Only a run of `devops roadmap inbox` sends it". Add the name to `INSTRUMENTS` and to `__all__`. The new case in `tests/telemetry/test_telemetry_instruments.py` sits beside the cases of the other roadmap gauges
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes

## 3. Send the count of each counted kind from the inbox command

Kind: behavior. Reads: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/commands/roadmap.py`, `tests/support/fakes/otlp.py`, `tests/support/fakes/roadmap_store.py`, `tests/commands/test_all_commands_help_dryrun.py`. Changes: `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/commands/roadmap.py`, `tests/roadmap/test_roadmap_inbox_gauges.py` (new).

- [ ] 3.1 `test_the_counted_kinds_are_the_nine_item_kinds` decides every member of `InboxKind`: `COUNTED_KINDS` holds `blocked`, `refine`, `split`, `alternatives`, `failed`, `stage_retry`, `claim`, `labels` and `queue`, and the other five are the pull request kinds. `test_the_gauge_shows_the_count_of_each_counted_kind` calls `read_inbox` on a fake repository with two `blocked` lines and one `refine` line, calls `emit_inbox_counts`, and reads `otlp.points("devops_cli_roadmap_inbox_items")`: 2 for `blocked`, 1 for `refine`, 0 for each other counted kind, and the repository name in `repo`. `test_the_gauge_holds_at_most_63_series` calls `emit_inbox_counts` for seven repository names and asserts 63 points
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox_gauges.py` fails on the base
- [ ] 3.2 Add `COUNTED_KINDS: tuple[InboxKind, ...]` to `src/devops_cli/roadmap/inbox_kind.py`. Add `emit_inbox_counts(inbox: Inbox, *, repo: str) -> None` to `src/devops_cli/roadmap/inbox.py`: it counts the lines of `inbox.jobs` and `inbox.people` for each kind of `COUNTED_KINDS` and calls `emit(ROADMAP_INBOX_ITEMS, count, {"repo": repo, "kind": kind.value})`, and it sends 0 for a kind with no line. Add it to `__all__` of `inbox.py`. Call it in `inbox_cmd` after `read_inbox` returns and before `render_inbox`. The step runs `tests/commands/test_all_commands_help_dryrun.py` and keeps it passing, because `inbox_cmd` changes
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox_gauges.py` passes

## 4. Add the inbox panel to the product dashboard

Kind: manifest. Reads: `k8s/devops/dashboards/project-metrics.json`, `tests/grafana/test_grafana_dashboards.py`. Changes: `k8s/devops/dashboards/project-metrics.json`, `tests/grafana/test_grafana_dashboards.py`.

- [ ] 4.1 `test_the_inbox_panel_charts_each_counted_kind` in `tests/grafana/test_grafana_dashboards.py`: it reads `k8s/devops/dashboards/project-metrics.json`, finds the one panel titled "Inbox Items by Kind", and asserts its query, its legend, its unit, its `gridPos` and that no panel of the dashboard overlaps another. The same module holds `test_repository_dashboards_lint_clean`, which lints the file
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py` fails on the base
- [ ] 4.2 Add the timeseries panel "Inbox Items by Kind" with an id that no panel of the file holds, the datasource `prometheus`, the unit `short`, a description that names `devops_cli_roadmap_inbox_items` and says that only a run of `devops roadmap inbox` sends it, and one target with the query `sum by (kind) (last_over_time(devops_cli_roadmap_inbox_items[$__range]))` and the legend `{{kind}}`. Place it at x 12, y 34, w 12 and h 8, the right half of the row of "Oldest Item Age by State". Add the case beside `test_repository_dashboards_lint_clean`, so the group's one command runs the new case and the lint
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py` passes

## 5. Regenerate the telemetry document and update the inbox page

Kind: other. Reads: `docs/TELEMETRY.md`, `docs/roadmap/inbox.md`, `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/telemetry/instruments.py`. Changes: `docs/TELEMETRY.md`, `docs/roadmap/inbox.md`, `docs/ROADMAP_WORKFLOW.md`.

- [ ] 5.1 Run `uv run devops docs generate` with no option, so `docs/TELEMETRY.md` holds the row of `devops_cli_roadmap_inbox_items` with kind Gauge and unit `1`. Add the class `stage_retry` to the list of classes of `docs/roadmap/inbox.md`, say that the counts of the command are the gauge `devops_cli_roadmap_inbox_items` by `repo` and `kind` and that the panel "Inbox Items by Kind" shows them, and extend the paragraph on the image digest: the line is not built because `devops argo cd apps status devops` needs a client of the cluster and the Service pod holds no cluster token, and #4832 owns it. Replace the row of #2968 in the planned-changes table of `docs/ROADMAP_WORKFLOW.md` with a row for the image digest line of #4832, which the inbox still leaves out
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Regenerate `docs/TELEMETRY.md` with `uv run devops docs generate`, add the class, the gauge and the digest reason to `docs/roadmap/inbox.md`, and change the row of `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: A test shows that the gauges equal the counts of the command, with a fake repository.
- Group 4: The panel JSON passes the dashboard checks of the repository.
- Group 5: A test shows the digest line, or the issue records why the line cannot be built.
- Group 5: `uv run devops ci` passes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
