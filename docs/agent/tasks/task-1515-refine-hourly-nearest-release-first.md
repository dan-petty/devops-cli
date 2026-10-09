# Task: Refine runs every hour and readies the new items of every planned release, nearest first, before that release starts (#1515)

**Issue**: [#1515](https://github.com/dan-petty/devops-cli/issues/1515)
**Status**: Done
**Milestone**: v0.2.33
**Priority**: priority/p1-high
**Scope**: type/feature, scope/roadmap
**Feasibility**: Checked on #1470's branch (88fab9d, on release/v0.2.33). The due table's `interval` and `first_run_due` already drive close, metrics and intake (`_is_interval_due`), so the refine row needs only those two fields. `select_candidates` read only the next planned release (`_find_next_planned_release`) and capped the backlog with `DEFAULT_ROADMAP_RELEASE_CAP`, and `plan_refine` never read `config.release_cap`. A real refine round that leaves items New, followed by a second round, sends no model request on this branch (the AC5 test below); before #1470 every such item was re-selected and gained another design section, which an hourly cadence would have repeated every hour.

## Description

Refine had no cadence of its own and looked one release ahead. It now has one and walks every open release.

- **Hourly.** The refine row in `DEFAULT_DUE_TABLE` (`src/devops_cli/roadmap/run.py`) gets `interval=timedelta(minutes=DEFAULT_ROADMAP_REFINE_INTERVAL_MINUTES)` (60, in `config/defaults.py` beside the intake and closure intervals) and `first_run_due=True`, and keeps its cross-job trigger: a round in which reprioritize ran, or intake placed a critical fix or a P0 item. A round with nothing to refine makes no model call, because `plan_refine` returns before it builds a client.
- **Nearest place first.** `select_candidates` (`src/devops_cli/roadmap/refine.py`) takes up to `--limit` (default 3) items in this order, each place by priority, and still skips items unchanged since their last refine:
  1. the current release's New items (critical fixes and items a person placed there);
  2. each planned release's New items, nearest release first;
  3. the backlog's P0 and P1 items;
  4. the backlog's other New items, while fewer than the configured `release_cap` items are Ready across the next planned release and the backlog. `plan_refine` passes `config.release_cap`; the default (12) applies without a config.
- **An item refine can't refine takes no place.** `select_candidates` runs `check_person_edits` on the body it already reads, and skips with that reason an item whose section a person edited or whose section's hash differs from the record, before it takes one of the `--limit` places. Before, such an item was selected and then skipped inside `refine_one_item`, which keeps its own check for the `--item` path. A New item holding a section from before #1470 is one: after its first refine on this change it holds its old `[end-marker]` section and a marked one, and every later round would have selected and skipped it, so a few of them at the front of the order would have taken every place each hour.
- **Ready means refined** (the owner's 2026-10-09 finding and decision). Steps 2 and 3 also take Ready items that no refine round has recorded: Ready set by migrate, sync or a person without a design. Refine confirms such an item Ready with a design, or sets it back to New (`apply_refine`) with its open questions in the section and a comment saying so (`refine_back_to_new_comment`: "Status set back to New at {sha}: refine found it not ready (see Key questions, Fit and Suspected block in the proposed design in the issue body)."), beside the comments refine posts when it sets Ready or marks a split. The current release's Ready items are not taken, so refine never sends an item that is being built back to New, and `--item` still refuses a Ready item.
- **The record, not the body, marks an item as refined.** `_is_unrefined_ready` reads the item's `refine.section_hash` mark. A section refine wrote before #1470 ends in `[end-marker]`, so `extract_section_and_outside` finds no section in its body; a body check would re-select every item refine had already readied and append a second design section to it.
- `_find_next_planned_release` is deleted. The help texts of `devops roadmap refine`, its `--limit`, and `devops roadmap run` describe the new order and cadence; `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md` and `README.md` are regenerated, and #744's task file states the new selection.

## Acceptance Criteria

- [x] With no reprioritize run in the round, refine is due 60 min after its last success, not at 59 min, and on a first run; `devops roadmap run --dry-run` prints `Due: refine` (`tests/test_roadmap_run.py::test_refine_is_due_an_hour_after_its_last_success_and_on_a_first_run`).
- The dry run naming the interval as the reason is not built here, following the owner's 2026-10-09 decision on the issue: AC1 is proven through the due tuple, because a per-job reason line would reshape `_Poll.is_due`, the dry-run return and the MCP parse that #412 is changing.
- [x] The cross-job trigger is still tested on its own: the schedules of `test_due_table_scenarios` and `test_order_and_cross_job_triggers` pin refine's last success at 59 min, with the same expected tuples, and a new case with nothing else due gives `()`. `test_idle_records_zero_or_one_store_calls` pins refine at 30 min.
- [x] With the next planned release all Ready and a later planned release holding New P1 items, refine selects the later release's items, highest priority first, up to 3 (`tests/test_roadmap_refine.py::test_a_later_planned_release_is_refined_once_the_next_one_is_ready`).
- [x] A New critical fix in the current release is selected before a planned release's item of the same priority (`test_a_critical_fix_in_the_current_release_goes_before_any_planned_item`).
- [x] A New P1 backlog item is refined before a New P2 one, and P2 and P3 only while fewer than `release_cap = 3`, read from `.github/roadmap.toml` through `plan_refine`, are Ready across the next planned release and the backlog (`test_backlog_p2_and_p3_wait_for_the_configured_release_cap`, with 3 and 1 Ready items).
- [x] Items a real refine round left New are skipped as unchanged on the next round, which selects nothing and sends the scripted gateway no request (`test_a_round_after_refine_left_items_new_skips_them_and_calls_no_model`).
- [x] Ready items with no refine record are taken in a planned release and among the backlog's P0 and P1 items; the current release's, a recorded one and a lower-priority backlog one are not (`test_ready_items_refine_never_saw_are_taken_in_planned_releases_and_backlog_p0_p1`).
- [x] Such an item that refine finds not ready goes back to New with the back-to-New comment, and the next round skips it (`test_a_ready_item_refine_finds_not_ready_goes_back_to_new_and_is_then_skipped`).
- [x] A New backlog P1 whose section's hash differs from the record (an old `[end-marker]` section followed by refine's marked one) is skipped at selection with the person-edit reason, and the New item behind it gets the round's one place (`test_an_item_refine_would_skip_for_a_person_edit_takes_no_place`).
- [x] The existing selection tests (`test_selection_next_release_backlog_priorities_and_cap`, the `_seed_new_items` cases) pass unchanged. The new tests are offline, and each takes under 1 s.
- `uv run devops ci` is the pull request's gate.
- Pending a person: within a day after the Service runs the v0.2.33 image, while v0.2.35 is still a planned release, `gh project item-list 2 --owner dan-petty --limit 1000 --format json --jq '.items[] | select(.milestone.title == "v0.2.35" and ((.status == "New" and (.content.body | contains("<!-- devops-roadmap-refine:end -->") | not)) or (.status == "Ready" and ((."job record" // "") | contains("refine.section_hash") | not)))) | .content.number'` prints nothing: every New item in v0.2.35 holds a refine section, and every Ready one has a refine record. On 2026-10-09 it printed #478, #438, #425, #423, #417, #416, #411 and #410.
- Pending a person: `kubectl -n devops exec deploy/roadmap-service -- cat /home/devops/.data/roadmap/dan-petty/devops-cli/schedule.json` shows a `refine` time less than 2 h old. If it is older, `kubectl -n devops logs deploy/roadmap-service -c service --since=2h | grep 'Refine skipped'` names the item whose model call keeps failing (the first known limit below).
- Pending a person: `kubectl -n devops logs deploy/roadmap-service -c service --since=3h | grep -E "dan-petty/devops-cli: GraphQL|No repository starts a Service round"` prints a spend line for each round and no pause line: the hourly refine rounds do not run the account's GraphQL points out.

## Decisions and deviations

- The issue's person check "the Service's first refine round selects 3 of v0.2.34's New P1 items" cannot happen. The Service deploys after v0.2.33 merges, and v0.2.34's start sends its New items to the backlog first (`(PLANNED, NEW_AT_START) -> TO_BACKLOG`). The first rounds therefore take v0.2.35's New items and its Ready items with no refine record, then the backlog's P0 and P1 items, 3 an hour; the board check above reads v0.2.35.
- Refine posts no comment for a New item it leaves New for open questions or a suspected block: they are in the section. It comments when it sets an item Ready, marks a split, or sets a Ready item back to New; a Ready item that needs a split gets the back-to-New comment, which points at Fit.

## Known limits

- A round in which an item's model call fails records no success, so refine stays due at every 300 s poll until a round has none, and each such round sends the failing item's two model calls again (the round's other items are recorded and then skipped as unchanged). Refine's time in `schedule.json` stays old meanwhile. Intake behaves the same way. Accepted for this change: it changes no retry rule, and a record that makes a failed item wait for a body change is separate work. Moved to #1526.
- An item whose new body would exceed the 65536-character body limit (`CONST_ROADMAP_REFINE_MAX_BODY_CHARS`) gets no record, so every refine round that reaches it, hourly, takes a place and sends its two model calls again. Accepted for this change, for the same reason. Moved to #1526.
- #273, #277, #698 and #438 (all New on 2026-10-09) hold a section refine wrote before #1470, which ends in `[end-marker]`; #273 and #438 hold two. Each gains one marked section on its next refine, and refine then skips it, taking no place, with "the section's hash differs from the one refine last recorded" until a person deletes the old `[end-marker]` section, as #1470 states.
- A round of 3 items keeps the repository's worker busy for about 20-35 min, as refine after reprioritize does today. Accepted, as the issue states.

## Deliverables

- [x] `src/devops_cli/config/defaults.py`: `DEFAULT_ROADMAP_REFINE_INTERVAL_MINUTES = 60`.
- [x] `src/devops_cli/roadmap/run.py`: the refine row's interval and first-run due; the module docstring.
- [x] `src/devops_cli/roadmap/refine.py`: `select_candidates`' order, its `release_cap` keyword and `plan_refine` passing the config's; Ready items with no record; the person-edit skip before an item takes a place; `apply_refine` sending such an item back to New, and `refine_one_item`'s comment for it; the module docstring.
- [x] `src/devops_cli/lang/en/help.py`: the `refine`, `refine_limit` and `run` texts; the regenerated `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md` and `README.md`.
- [x] `src/devops_cli/lang/en/messages.py`: `refine_back_to_new_comment`.
- [x] `docs/agent/tasks/task-744-item-refinement-to-ready.md`: the Selection bullet.
- [x] `tests/test_roadmap_refine.py`, `tests/test_roadmap_run.py`.
- [x] `changelog.d/1515.md`.
