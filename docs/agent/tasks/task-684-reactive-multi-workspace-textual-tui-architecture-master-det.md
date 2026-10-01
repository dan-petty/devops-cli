# Task: Dashboard Keeps Its Place Across Refreshes and Shows a Finding Detail Pane (#684)

**Issue**: [#684](https://github.com/dan-petty/devops-cli/issues/684)
**Status**: Done
**Milestone**: v0.2.24
**Priority**: priority/p1-high
**Scope**: scope/cli

## Description
`devops dashboard` (alias `devops tui`) redrew every table on each refresh with `DataTable.clear()`, which puts the cursor on the first row and scrolls to the top, so every five seconds the operator lost their place on every tab, visible or hidden. Switching tabs never lost anything: hidden panes stay mounted.

Every table row now has a stable key. One pure identity function per table in `src/devops_cli/ui/projections.py`, registered beside `_ROWS` and `DOCKER_RESOURCE_ROWS`, names the record each row shows: pods by namespace and name, containers, images and networks by id, volumes and registries by name, telemetry by kind and name, Valkey by property, review sessions by name and findings by persona, location and full title. `row_keys` numbers repeated identities and encodes each key as JSON, so a repeat (two containers with the empty-id fallback) is two rows instead of a `DuplicateKey` that blanked the panel. `redraw_table` in `src/devops_cli/ui/widgets.py` replaces the four bare `clear()`/`add_rows` sites: it returns the cursor to the same key, or keeps its index on a shorter table when the record is gone, then restores both scroll offsets after the cursor's own scroll into view. The horizontal offset matters on the findings table: beside the detail pane it is narrower than a real finding's location, so Location and Status are read scrolled to the right. A different review session starts the findings table at the top.

The AI Review "Findings" sub-tab now has a scrollable detail pane beside the table (3fr to 2fr). `finding_detail` renders the highlighted finding's full record as plain labelled text: a header of short fields, then a titled section for each long one, with description and fix passed through `format_clean_text_field` as `review findings --details` does. Indentation every line of a text field shares is removed before that, and only the blank lines around a value and its trailing whitespace are trimmed after, so quoted code keeps its alignment. The field list and labels live in `src/devops_cli/config/constants.py`. `recommendation` (the persona's merge verdict), `thinking` and verification bookkeeping are left out on purpose. The pane has markup off and writes every Unicode `Cc` control character other than newline and tab as a visible escape, because finding text is model output that quotes repository content. It follows `RowHighlighted` from `#ai-table` only and looks the record up by row key in the current snapshot, keyed by the same `render_keys` call the table is drawn with. A different finding, or a different session, opens the pane at the top; a refresh that shows the same finding again keeps the reader's offset. `i`, bound on `ReviewPanel` and listed in help, shows and hides it.

The provider no longer keeps only the first 50 findings, so every finding the banner counts is listed.

Out of scope, as the issue records: new or renamed workspaces (#685-#691), hash routing (`--tab` covers it), push events, filters (#686's `/` search is the first and keeps applying through refreshes with these row keys), and pod, PR and other inspectors.

## Acceptance Criteria
- [x] With 3-row overrides to `patched_fetchers`, a cursor on row 2 of the Kubernetes, Docker containers and findings tables keeps `(cursor_row, highlighted row key)` across `action_refresh_data()` with unchanged data: `test_a_refresh_with_unchanged_data_keeps_the_highlighted_row`, which failed on the previous code with the cursor back on row 0.
- [x] A 50-pod Kubernetes table in `run_test(size=(100, 24))` keeps `(cursor_row, scroll_x, scroll_y)` at `(12, 0, 10)` and at `(2, 0, 20)`, the second with the cursor scrolled out of view, and a 50-finding table with long locations at `(80, 24)` keeps `(20, 30, 10)`: `test_a_refresh_keeps_the_cursor_and_scroll_of_a_long_table`, whose findings case failed with `scroll_x` back at 0 before `redraw_table` restored it. `test_a_table_on_a_hidden_tab_keeps_its_place_through_a_refresh` covers a table refreshed while its tab is hidden.
- [x] When the highlighted record is missing from the next snapshot, the cursor keeps its index, moved back to the last row on a shorter table, and nothing raises, down to an empty table: `test_a_vanished_record_leaves_the_cursor_at_its_index`.
- [x] Two findings with the same persona, location and title render as two rows and a cursor on the second stays there across a refresh; two containers with an empty `id` render as two rows with no error banner: `test_repeated_findings_are_separate_rows_that_keep_the_cursor`, `test_containers_without_an_id_are_separate_rows`.
- [x] Moving the cursor to row 20 and applying a findings snapshot with a different `session_name` gives `(cursor_row, scroll_y) == (0, 0)`: `test_a_different_review_session_returns_the_findings_to_the_top`.
- [x] For every domain and every Docker resource the keys match the row projection in number for the sample snapshots: `test_every_domain_keys_each_row_it_projects`, `test_every_docker_resource_keys_each_row_it_projects`, plus `test_review_sessions_are_keyed_row_for_row`.
- [x] Highlighting a finding shows its full title, description, fix and mitigating mechanism and no `thinking` or `recommendation` text: `test_highlighting_a_finding_shows_its_full_text`, `test_finding_detail_leaves_out_the_verdict_and_the_scratchpad`.
- [x] Moving the cursor updates the pane, a refresh with unchanged data leaves its text unchanged, and a findings table emptied by the next snapshot of the same session reads `No finding selected.` in place of the finding it showed: `test_the_detail_pane_follows_the_cursor_and_holds_through_a_refresh`, `test_the_detail_pane_reads_no_finding_selected_without_findings`, which fails when `_show_finding(None)` leaves the pane alone. Moving to another finding returns a scrolled pane to the top while a refresh keeps its offset: `test_another_finding_is_detailed_from_the_top`. `test_a_session_highlight_leaves_the_detail_pane_alone` covers the sessions table being ignored.
- [x] `finding_detail` keeps `confidence_score=0.0` and `citation_line=0` and omits fields that are `None`, `""` or `[]`: `test_finding_detail_keeps_zero_values_and_omits_empty_fields`. `test_finding_detail_lists_the_header_then_each_section_in_order` pins the whole layout, and `test_finding_detail_keeps_quoted_code_aligned` the indentation of quoted code.
- [x] A description of `a \x1b[31mred\x1b[0m [bold]x[/]` renders without `MarkupError`, keeping `[bold]x[/]` and the four characters `\x1b` and no ESC character: `test_model_written_markup_and_escapes_render_literally_in_the_pane`, `test_finding_detail_writes_control_characters_as_visible_escapes`.
- [x] With the findings table focused, `i` hides the pane and shows it again; `i` on the Kubernetes tab changes nothing; the help text lists `i`: `test_i_toggles_the_detail_pane_from_the_findings_table`, `test_i_does_nothing_outside_ai_review`, `test_the_help_screen_lists_the_detail_toggle`.
- [x] A 60-finding session from `_make_sessions` gives `(len(summary.findings), summary.total_findings) == (60, 60)`, where the previous code gave `(50, 60)`: `test_every_finding_of_a_session_is_listed`.
- [x] Every existing test in `tests/test_ui_reactive.py` and `tests/test_ui_dashboard.py` passes unmodified, covering the widget ids, pod-to-logs selection and session selection.
- [x] `uv run devops ci` passes.

## Deliverables
- [x] `src/devops_cli/ui/projections.py`: identity functions, `row_keys`, `render_keys`, `docker_resource_keys`, `review_session_keys`, `finding_records`, `finding_detail`.
- [x] `src/devops_cli/ui/widgets.py`: `redraw_table`, and the review panel's detail pane, row-highlight handling and `i` binding.
- [x] `src/devops_cli/ui/dashboard.py`: help screen line for `i`.
- [x] `src/devops_cli/ui/data_providers.py`: the 50-finding cap removed.
- [x] `src/devops_cli/config/constants.py`: detail pane fields, labels, fallback and control-character rule.
- [x] `tests/test_ui_reactive.py`: pilot and unit tests for each acceptance criterion.

## Verification
- `uv run pytest tests/test_ui_reactive.py tests/test_ui_dashboard.py`: 230 passed. 18 of the new tests failed before the widget and provider changes; the rest pin projection behaviour. The review's three behaviour cases (horizontal scroll, detail pane offset, quoted-code indentation) failed before their fixes.
- The new pilot tests passed five consecutive parallel runs.
- `uv run devops ci`: every check passed.
