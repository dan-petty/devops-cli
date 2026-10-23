# Task: Dashboard Keeps Its Place Across Refreshes (#684)

**Issue**: [#684](https://github.com/dan-petty/devops-cli/issues/684)
**Scope**: scope/cli

## Description
`devops dashboard` (alias `devops tui`) redrew every table on each refresh with `DataTable.clear()`, which puts the cursor on the first row and scrolls to the top, so every five seconds the operator lost their place on every tab, visible or hidden. Switching tabs never lost anything: hidden panes stay mounted.

Every table row now has a stable key. One pure identity function per table in `src/devops_cli/ui/projections.py`, registered beside `_ROWS` and `DOCKER_RESOURCE_ROWS`, names the record each row shows: pods by namespace and name, containers, images and networks by id, volumes and registries by name, telemetry by kind and name, and Valkey by property. `row_keys` numbers repeated identities and encodes each key as JSON, so a repeat (two containers with the empty-id fallback) is two rows instead of a `DuplicateKey` that blanked the panel. `redraw_table` in `src/devops_cli/ui/widgets.py` replaces the four bare `clear()`/`add_rows` sites: it returns the cursor to the same key, or keeps its index on a shorter table when the record is gone, then restores both scroll offsets after the cursor's own scroll into view. The horizontal offset matters on a table wider than the screen, such as one of long pod names: it is read scrolled to the right.

The provider no longer keeps only the first 50 findings, so the summary holds every finding that its count includes.

Out of scope, as the issue records: new or renamed workspaces (#685-#691), hash routing (`--tab` covers it), push events, filters (#686's `/` search is the first and keeps applying through refreshes with these row keys), and pod, PR and other inspectors.

## Acceptance Criteria
- [x] With 3-row overrides to `patched_fetchers`, a cursor on row 2 of the Kubernetes and Docker containers tables keeps `(cursor_row, highlighted row key)` across `action_refresh_data()` with unchanged data: `test_a_refresh_with_unchanged_data_keeps_the_highlighted_row`, which failed on the previous code with the cursor back on row 0.
- [x] A 50-pod Kubernetes table in `run_test(size=(100, 24))` keeps `(cursor_row, scroll_x, scroll_y)` at `(12, 0, 10)` and at `(2, 0, 20)`, the second with the cursor scrolled out of view, and a 50-pod table with long pod names at `(80, 24)` keeps `(20, 30, 10)`: `test_a_refresh_keeps_the_cursor_and_scroll_of_a_long_table`, whose wide case fails with `scroll_x` back at 0 when `redraw_table` does not restore it. `test_a_table_on_a_hidden_tab_keeps_its_place_through_a_refresh` covers a table refreshed while its tab is hidden.
- [x] When the highlighted record is missing from the next snapshot, the cursor keeps its index, moved back to the last row on a shorter table, and nothing raises, down to an empty table: `test_a_vanished_record_leaves_the_cursor_at_its_index`.
- [x] Two containers with an empty `id` render as two rows with no error banner: `test_containers_without_an_id_are_separate_rows`.
- [x] For every domain and every Docker resource the keys match the row projection in number for the sample snapshots: `test_every_domain_keys_each_row_it_projects`, `test_every_docker_resource_keys_each_row_it_projects`.
- [x] A 60-finding session from `_make_sessions` gives `(len(summary.findings), summary.total_findings) == (60, 60)`, where the previous code gave `(50, 60)`: `test_every_finding_of_a_session_is_listed`.
- [x] Every existing test in `tests/test_ui_reactive.py` and `tests/test_ui_dashboard.py` passes unmodified, covering the widget ids and pod-to-logs selection.
- [x] `uv run devops ci` passes.

## Deliverables
- [x] `src/devops_cli/ui/projections.py`: identity functions, `row_keys`, `render_keys`, `docker_resource_keys`.
- [x] `src/devops_cli/ui/widgets.py`: `redraw_table`.
- [x] `src/devops_cli/ui/data_providers.py`: the 50-finding cap removed.
- [x] `tests/test_ui_reactive.py`: pilot and unit tests for each acceptance criterion.

## Verification
- The new pilot tests passed five consecutive parallel runs.
- `uv run devops ci`: every check passed.
