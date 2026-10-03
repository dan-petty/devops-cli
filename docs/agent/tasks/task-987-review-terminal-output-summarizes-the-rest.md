# Task: Review Terminal Output Lists What Matters and Summarizes the Rest (#987)

**Issue**: [#987](https://github.com/dan-petty/devops-cli/issues/987)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p2-medium
**Scope**: scope/review

## Description
At the end of a review, `generate_consolidated_report` (`ai/review/pipeline.py`) printed everything to the terminal: the findings table, a detail panel for every reportable finding whatever its severity, every scanned dependency, every network reference, and the summary. The owner reported that the output was too large to read, and that LOW findings and the clean dependency and network results buried the findings that matter. `review.md` and `findings.json` already hold everything, so the terminal now shows the findings that matter and one line for each of the rest, pointing at the report. `--full` prints everything as before.

## Key Changes
- **Findings** (`ReviewPipelineOrchestrator._render_console_findings_table`). `_select_console_findings` numbers the reportable findings as `review.md` does, then keeps CRITICAL, HIGH and MEDIUM for the table and CRITICAL and HIGH for detail panels, so a finding shows the same number in both. The rest (LOW and INFO) become one line from `_format_minor_findings_line`: their count by severity and by status (VERIFIED, UNVERIFIED, MITIGATED order, `CONST_REVIEW_STATUS_ORDER`), the path to `review.md`, and the command that lists them, `devops review findings <session> --severity LOW [--severity INFO] --details`. MITIGATED and UNVERIFIED findings follow severity like any other. The thresholds are `CONST_REVIEW_CONSOLE_TABLE_SEVERITIES` and `CONST_REVIEW_CONSOLE_PANEL_SEVERITIES` in `config/constants.py`. The table's row, columns and badges moved to module level (`_format_console_finding_row`, `_CONSOLE_FINDING_COLUMNS`, `_CONSOLE_SEVERITY_BADGES`, `_CONSOLE_STATUS_BADGES`) unchanged.
- **Dependencies** (`_render_console_dependencies_table`). One line from `_format_dependency_console_line`: packages scanned, vulnerable with a count by severity, and not checked when any lookup did not run, pointing at the report's "External Dependencies" section. A "Vulnerable Dependencies" table follows only when a package is vulnerable. A package is vulnerable when its severity, which the audit sets from its worst known vulnerability, is one of `CONST_DEPENDENCY_VULNERABLE_SEVERITIES`.
- **Network references** (`_render_console_network_table`). One line from `_format_network_console_line`: references found, local and external, and flagged by reputation (`reputation.is_malicious`), pointing at the report's "Network References & Endpoints" section. A "Flagged Network References" table follows only when an endpoint is flagged.
- **Section names.** `_REPORT_DEPENDENCIES_SECTION` and `_REPORT_NETWORK_SECTION` now build both the `review.md` headings and the terminal's pointers, so the two cannot drift. The headings' text is unchanged.
- **Closing line.** `Consolidated review completed for session <id> (<n> finding(s) saved to <session dir>; full report: <session dir>/review.md)`.
- **`--full`.** `devops review path|branch|pr --full` (`HELP.review.full_output`) sets `full_output` on `_execute_review_workflow`, which hands it to `ReviewPipelineOrchestrator(full_output=...)`. With it, the three renderers print what they printed before.
- **`devops review findings --severity`** (`HELP.review.severity_filter`). It is repeatable and reads a severity as a review reads it, through the new `severity_named` in `ai/review_schema.py`, so `informational` means INFO. `Finding`'s severity validator now calls `severity_named` too, unchanged in effect, and a spelling it does not name matches no finding rather than becoming MEDIUM. This is the command the LOW line names. It joins #949's status filter in `_listed_findings`, which keeps each finding's number in findings.json (or candidates.json with `--candidates`), the number `devops review verify --index` takes, so `--severity` combines with the status flags and `--candidates`.
- **Escaping.** The dependency and network row formatters escaped nothing, so `uvicorn[standard]` printed as `uvicorn` and a target holding `[/x]` stopped the review with a `MarkupError`. `devops review findings` did the same with titles, locations, personas and verdict reasons in #949's `_finding_row`. Each now goes through `escape_text`, as finding titles and descriptions already did.
- **Docs.** `uv run devops docs generate --sync-readme` regenerated `docs/commands/review.md`, `docs/commands/ai.md` and `docs/CLI_REFERENCE.md`. The knowledge base's `cli_command_reference.md` and `tasks/ai_code_review.md` name `--full` and `--severity`.
- **Overlap with #949 and #948.** #949 (`e4ea2e0`), merged into release/v0.2.25 while this item was in progress, rewrote `list_findings`: stable numbers under any filter, `--candidates`, and row formatting in `_finding_row`. This work was moved onto release/v0.2.25 at `38517a8` and builds on #949's listing rather than replacing it. #948, still open, changes `review.md`'s executive summary and finding order; this item changes only the terminal rendering, and whichever lands second rebases.
- **Tests.** `tests/test_review_console_report.py` is new. `tests/test_review.py` gains the `--full` test and three `devops review findings` tests: `--severity` numbering, `--severity` with `--candidates`, and escaping. `test_generate_consolidated_report_prints_findings_and_review_summary` in `tests/test_review_pipeline.py` now expects the two summary lines in place of the dependency and network tables.

## Acceptance Criteria
- [x] **Findings.** The table lists CRITICAL, HIGH and MEDIUM findings, panels follow for CRITICAL and HIGH, and LOW and INFO findings are one line with counts by status, the path to `review.md` and the exact command. `test_terminal_tables_medium_and_up_details_high_and_up_and_counts_low_on_one_line` renders 1 CRITICAL, 1 HIGH, 2 MEDIUM and 10 LOW findings and finds 4 table rows (CRITICAL, HIGH, MEDIUM, MEDIUM), 2 panels (CRITICAL, HIGH), and one line holding `10 LOW finding(s) (6 VERIFIED, 4 UNVERIFIED)`, the `review.md` path and `devops review findings 20261002-180320 --severity LOW --details`, with no LOW title anywhere. `test_low_and_info_findings_share_the_line_and_the_command_names_both` covers INFO.
- [x] **Dependencies.** `test_clean_dependencies_print_one_summary_line_and_no_rows`: 58 clean dependencies give one line, `58 scanned, 0 vulnerable` pointing at "External Dependencies" in `review.md`, and no row. `test_vulnerable_dependencies_are_counted_by_severity_and_listed_alone`: `6 scanned, 2 vulnerable (1 CRITICAL, 1 HIGH), 1 not checked`, then rows for the two vulnerable packages only, `uvicorn[standard]` printed as written.
- [x] **Network references.** `test_unflagged_network_references_print_one_summary_line`: 531 references, none flagged, give one line, `531 found (252 local, 279 external), 0 flagged by reputation` pointing at "Network References & Endpoints" in `review.md`, and no row. `test_flagged_network_references_are_listed_alone`: only the flagged endpoint is listed, its target printed as written.
- [x] **Full output.** `test_full_output_prints_every_finding_dependency_and_reference`: with `full_output`, 14 table rows, 14 panels, 58 dependency rows and 60 reference rows. It renders 60 references rather than 531 because Rich takes 0.7 to 0.9 s to lay out a 531-row table, which would break the rule that each test runs well under 1 s. The measurement below renders the 531-reference session in full. `test_review_md_and_findings_json_are_the_same_with_or_without_full_output` checks that the saved report does not depend on the flag. `test_review_full_flag_reaches_the_review_workflow` (path, branch and pr, with and without `--full`) and `test_review_workflow_hands_full_output_to_the_orchestrator` check the wiring. Rendered from two saved sessions, `--full` output matches the old output line for line except the closing line.
- [x] **The command copies as is.** The LOW line ends with "list them with:", and the command prints on the next line with soft wrap, so Rich never breaks it at the console width. `test_the_command_that_lists_low_findings_prints_whole_on_a_narrow_terminal` renders at 60 columns and finds the 63-character command whole on one line. With the command appended to the summary line, as before, it failed: the line wrapped and split the command.
- [x] **`review.md` and `findings.json` are unchanged.** Written by the old and new code from session `20261002-180320`, both files are identical apart from `generated_at`.
- [x] **Path.** `test_closing_line_names_the_session_directory_and_review_md`.
- [x] **Tests offline, on a recording console, written first.** Each new test records the shared console with `Console(record=True)` and touches no network, model or scanner. On the unchanged code (HEAD `9c879ae`, run through `-o pythonpath=` against an archived copy of `src/`) the first 18 failed. The console tests failed on their assertions or on `full_output` not existing, the CLI tests on `--severity` and `full_output` not existing, and `test_flagged_network_references_are_listed_alone` with `MarkupError: closing tag '[/{payload}]'`.
- [x] **`devops review findings` on top of #949.** With `list_findings` and `_finding_row` as #949 left them at `38517a8`, `test_review_findings_filters_by_severity_and_keeps_each_number_in_findings_json` and `test_review_findings_severity_lists_candidates_by_their_numbers_in_candidates_json` exited 2 (no `--severity`), and `test_review_findings_prints_untrusted_text_as_written` exited 1 with `MarkupError: closing tag '[/{status_color}]' at position 12 doesn't match any open tag`. With `_listed_findings` and the escaped `_finding_row` they pass: `--severity low --severity informational` over HIGH, LOW, HIGH and INFO findings lists #2 and #4, and `--candidates --invalidated --severity LOW` lists candidates #1 and #4.
- [x] `ruff check` and `ruff format --check` are clean on every touched file, and `mypy --strict` is clean on the six touched `src` modules. `devops scan complexity` adds no function over the cap. The new helpers are at 6 or under (`_listed_findings` 5), `_render_console_findings_table` went from 7 to 5, and `list_findings` stays at 8, as #949 left it.
- [x] `uv run devops docs generate --sync-readme` regenerated the command docs, and `uv run devops docs check` reports every documentation file up to date.
- [x] `uv run pytest -p no:cacheprovider -q -n 6 tests` passes on `38517a8` with this work: 7239 passed, 8 xfailed.
- Pending a person: `uv run devops ci` on the delivering tree, which the orchestrating session runs.
- Not checked when merged: the PR's own remote checks.
- Pending a person: run `uv run devops review branch` on a branch with LOW findings, then `uv run devops review branch --full`. The first should end with the LOW line, one line each for dependencies and network references, the summary table, and a closing line naming `review.md`. The second should print every finding, dependency and reference.

## Measurements
### Terminal output
A scratch script loaded a saved session's `findings.json` and `candidates.json` and ran `generate_consolidated_report` with the session's own consolidated findings, dependencies and references in place of consolidation. It recorded the shared console with `Console(record=True, width=W)` and counted lines. "Before" ran HEAD `9c879ae` from an archived copy of `src/`, and "after" ran the worktree. Session directories sat in a scratch data directory whose path is longer than `.data/reviews/<id>`, which lengthens only the lines that print a path. These figures were taken before the work moved onto `38517a8`; `ai/review/pipeline.py`, `ai/review/runner.py` and `output/` are the same at both commits, so they hold there.

| Session | Width | Before | After | After, `--full` |
| :--- | ---: | ---: | ---: | ---: |
| `20261002-180320`: branch review, 126 findings, 58 dependencies, 162 references | 120 | 3,469 | 1,731 | 3,470 |
| `20261002-180320` | 200 | 2,985 | 1,462 | 2,986 |
| `20261001-224227`: path review, 563 findings, 58 dependencies, 531 references | 120 | 15,708 | 9,043 | 15,709 |
| `20261001-224227` | 200 | 13,534 | 7,564 | 13,535 |

Where the lines go, for `20261002-180320` at 120 columns:

| Section | Before | After |
| :--- | ---: | ---: |
| Findings table | 336 (126 rows) | 283 (104 rows) |
| LOW line | — | 3 |
| Detail panels | 2,822 (126 panels) | 1,424 (47 panels) |
| Dependencies | 60 | 1 |
| Network references | 234 | 2 |
| Review summary table | 14 | 14 |
| Closing line | 2 | 3 |

Both totals include the one "Generating report" line. `--full` adds one line because the closing line now also names `review.md`. CRITICAL and HIGH detail panels make up 1,424 of the 1,731 lines left, and the one CRITICAL finding's panel alone is 300.

### New tests
Run twice with `uv run pytest -p no:cacheprovider -q -n 0 --durations=0 --durations-min=0`. Figures sum setup, call and teardown.

| Test | Run 1 | Run 2 |
| :--- | ---: | ---: |
| `test_review_full_flag_reaches_the_review_workflow` (slowest of 6) | 0.34 s | 0.36 s |
| `test_full_output_prints_every_finding_dependency_and_reference` | 0.31 s | 0.21 s |
| `test_review_findings_filters_by_severity_and_keeps_each_number_in_findings_json` | 0.09 s | 0.09 s |
| `test_review_findings_severity_lists_candidates_by_their_numbers_in_candidates_json` | 0.07 s | 0.07 s |
| `test_review_findings_prints_untrusted_text_as_written` | 0.06 s | 0.06 s |
| `test_terminal_tables_medium_and_up_details_high_and_up_and_counts_low_on_one_line` | 0.16 s | 0.16 s |
| `test_unflagged_network_references_print_one_summary_line` | 0.13 s | 0.12 s |
| `test_review_md_and_findings_json_are_the_same_with_or_without_full_output` | 0.11 s | 0.09 s |
| `test_closing_line_names_the_session_directory_and_review_md` | 0.07 s | 0.04 s |
| `test_flagged_network_references_are_listed_alone` | 0.06 s | 0.04 s |
| `test_clean_dependencies_print_one_summary_line_and_no_rows` | 0.05 s | 0.05 s |
| `test_vulnerable_dependencies_are_counted_by_severity_and_listed_alone` | 0.04 s | 0.04 s |
| `test_low_and_info_findings_share_the_line_and_the_command_names_both` | 0.04 s | 0.03 s |
| `test_review_workflow_hands_full_output_to_the_orchestrator` | 0.01 s | 0.01 s |
