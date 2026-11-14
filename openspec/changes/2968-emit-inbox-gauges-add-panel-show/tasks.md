# Tasks

## 1. List each open Ready item whose stage job failed

Kind: behavior. Reads: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_inbox.py`. Changes: `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_inbox.py`.

- [ ] 1.1 `test_a_stage_job_that_failed_has_one_line_naming_its_class` in `tests/roadmap/test_roadmap_inbox.py`: the fake repository holds an open Ready item whose job record holds `stage.failed_class` with value `limit_reached`, returning one line of class `stage_retry` naming `limit_reached`. `test_a_new_item_with_an_old_stage_failure_class_gives_no_line` asserts that a New item with historical failure class produces no retry line. `test_a_stage_job_that_has_no_class_has_no_line` asserts that an item with no failure class produces no line
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox.py` fails on the base
- [ ] 1.2 Add `STAGE_RETRY = "stage_retry"` to `InboxKind` after `FAILED`. Add heading, subject, and clear messages to `inbox_headings`, `inbox_subjects`, and `inbox_clears` of `MESSAGES.roadmap`. Add `_stage_retry_lines(items, repo, now)` filtering for `item.status == ItemStatus.READY` and reading `StageRecordKey.FAILED_CLASS`, splicing into `read_inbox` after `_failed_lines`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox.py` passes

## 2. Declare the inbox gauge and person cause instruments in the instrument list

Kind: behavior. Reads: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [ ] 2.1 `test_the_inbox_gauge_is_a_declared_instrument` in `tests/telemetry/test_telemetry_instruments.py`: `INSTRUMENTS` holds `devops_cli_roadmap_inbox_items` with kind Gauge and unit `1`. `test_person_cause_instruments_are_declared` asserts declaration of person cause inflow, outflow, and age instruments
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` fails on the base
- [ ] 2.2 Add `ROADMAP_INBOX_ITEMS` to `src/devops_cli/telemetry/instruments.py` beside `ROADMAP_CLAIM_AGE`. Add person cause instruments `ROADMAP_PERSON_CAUSE_INFLOW`, `ROADMAP_PERSON_CAUSE_OUTFLOW`, and `ROADMAP_PERSON_CAUSE_AGE`. Add all names to `INSTRUMENTS` and `__all__`
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes

## 3. Send the count of each counted kind from the metrics row and inbox command

Kind: behavior. Reads: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/commands/roadmap.py`, `tests/support/fakes/otlp.py`, `tests/support/fakes/roadmap_store.py`. Changes: `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/roadmap.py`, `tests/roadmap/test_roadmap_inbox_gauges.py` (new), `tests/roadmap/test_roadmap_run_metrics.py`.

- [ ] 3.1 `test_the_counted_kinds_are_the_eight_active_kinds` verifies `COUNTED_KINDS` holds `blocked`, `refine`, `split`, `alternatives`, `failed`, `stage_retry`, `claim`, and `labels`. `test_the_gauge_shows_the_count_of_each_counted_kind` calls `read_inbox` on a fake repository and asserts emitted points. `test_the_gauge_holds_at_most_56_series` tests seven repositories. `test_metrics_adapter_emits_inbox_counts` verifies `_run_metrics_adapter` emits gauges
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox_gauges.py tests/roadmap/test_roadmap_run_metrics.py` fails on the base
- [ ] 3.2 Add `COUNTED_KINDS: tuple[InboxKind, ...]` to `src/devops_cli/roadmap/inbox_kind.py`. Add `emit_inbox_counts(inbox: Inbox, *, repo: str) -> None` in `src/devops_cli/roadmap/inbox.py`, using `RepoRef(repo).key`. Call `emit_inbox_counts` in `_run_metrics_adapter` in `src/devops_cli/roadmap/run.py` and in `inbox_cmd` in `src/devops_cli/commands/roadmap.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox_gauges.py tests/roadmap/test_roadmap_run_metrics.py` passes

## 4. Add the inbox panel to the product dashboard and configure alerts

Kind: manifest. Reads: `k8s/devops/dashboards/project-metrics.json`, `tests/grafana/test_grafana_dashboards.py`. Changes: `k8s/devops/dashboards/project-metrics.json`, `k8s/devops/alerts/inbox.yaml` (new), `tests/grafana/test_grafana_dashboards.py`.

- [ ] 4.1 `test_the_inbox_panel_charts_each_counted_kind` in `tests/grafana/test_grafana_dashboards.py`: asserts panel titled "Inbox Items by Kind", type `bargauge`, unit `short`, query `sum by (kind) (last_over_time(devops_cli_roadmap_inbox_items[$__range]))`, and grid position at x 12, y 34
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py` fails on the base
- [ ] 4.2 Add the bar gauge panel "Inbox Items by Kind" to `k8s/devops/dashboards/project-metrics.json` at x 12, y 34, w 12 and h 8, following docs/DESIGN.md rule C15. Add alert rule for person cause daily inflow exceeding the cap in `k8s/devops/alerts/inbox.yaml`
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py` passes

## 5. Regenerate the telemetry document and update documentation

Kind: other. Reads: `docs/TELEMETRY.md`, `docs/roadmap/inbox.md`, `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/telemetry/instruments.py`. Changes: `docs/TELEMETRY.md`, `docs/commands/roadmap.md`, `docs/roadmap/inbox.md`, `docs/ROADMAP_WORKFLOW.md`.

- [ ] 5.1 Run `uv run devops docs generate` to update `docs/TELEMETRY.md` and `docs/commands/roadmap.md`. Update `docs/roadmap/inbox.md` to describe the `stage_retry` class, the inbox gauge, and cluster requirements for image digests (#4832). Update `docs/ROADMAP_WORKFLOW.md` and document the 7-day post-merge live proof
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Verify that `docs/TELEMETRY.md` and `docs/commands/roadmap.md` are synchronized, and that `docs/roadmap/inbox.md` documents gauges and the image digest rationale
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: A test shows that the gauges equal the counts of the command, with a fake repository.
- Group 4: The panel JSON passes the dashboard checks of the repository.
- Group 5: A test shows the digest line, or the issue records why the line cannot be built.
- Group 5: `uv run devops ci` passes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
