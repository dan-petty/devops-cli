# Task: A critical fix joins the current release while its release pull request is open (#1294)

**Issue**: [#1294](https://github.com/dan-petty/devops-cli/issues/1294)
**Status**: Done
**Milestone**: v0.2.29
**Priority**: priority/p1-high
**Scope**: type/bug, scope/release, priority/p1-high

> **Superseded in part by #1514.** An admitted fix descopes an item only once it takes the cut release over its limit, `release_cap + release_slots`, not its cap. `test_a_fix_that_takes_a_cut_release_over_its_cap_descopes_its_lowest_ranked_unstarted_item` is now `test_a_fix_that_takes_a_cut_release_over_its_limit_descopes_its_lowest_ranked_unstarted_item`.

## Description

On 2026-10-07 `devops roadmap reprioritize` moved #1290, a P0 fix for a regression v0.2.28 itself introduced, out of cut v0.2.28 with "v0.2.28 is cut, so nothing joins it until its release pull request is closed; a critical fix goes first into the next release". One row did it: `(CUT, FIX_JOINED) -> TO_NEXT`. Intake asks the same table, so it placed such a fix in the next release too. The owner wants the release branch to hold every change before the release pull request merges.

- **A new state for a merged, unpublished release.** `release_state` returned `CUT` both while the release pull request was open and after it merged but before GitHub Release vX.Y.Z was published. `ReleaseState.MERGED` now covers the second window. `INHERITS` is `{CUT: STARTED, MERGED: CUT}`, and intake reads a shipped release as `MERGED` instead of `CUT`.
- **Two rows.** `(CUT, FIX_JOINED)` is now `ADMIT` with `Reason.CUT`, and `(MERGED, FIX_JOINED)` is `TO_NEXT` with the new `Reason.MERGED`. Every other row is unchanged. An item with a pull request in flight still joins either state, and the cap binds both, as it binds a started release.
- **The start of a release cut before it** still pulls nothing in: `_is_cut` is true for `CUT` and `MERGED`.
- **Messages.** `cut`: "{release} is cut, and a critical fix still joins it while its release pull request is open, so the fix merges into the release branch before the release pull request does." `merged`: "the release pull request of {release} has merged, so a critical fix can no longer ship in it and goes first into the next release."
- **Scope.** This item owns the critical-fix path only. A person's join of any other item into a cut release is #1349's: the item adds no move of such a join, and its tests and docs leave that case to #1349.

## Acceptance Criteria

- [x] While a release's pull request is open, a critical fix joins that release and stays in it: `decide(CUT, FIX_JOINED)` is `ADMIT` (`test_a_critical_fix_joins_a_cut_release_until_its_release_pull_request_merges` in `tests/test_roadmap_reprioritize.py`); a fix filed while a draft release pull request is open is admitted with the cut comment and stays when the pull request is closed unmerged (`test_a_fix_filed_while_a_draft_release_pull_request_is_open_joins_and_stays_when_uncut`); a stopped admission finishes after a cut and moves on after a merge (`test_a_fix_whose_release_was_cut_before_the_rerun_is_admitted_until_its_pull_request_merges`); intake places a critical fix in the cut release and in the next one once the release pull request has merged, published or not (`test_a_critical_fix_joins_the_current_release_until_its_release_pull_request_merges` in `tests/test_roadmap_intake.py`).
- [x] Only a critical fix joins a cut release on the jobs' own placement; every other item waits for the next release, except an item a person joins after the cut, which #1349 admits. Intake places a feature and a P0 feature with no milestone in the backlog while the release pull request is open (`test_a_candidate_that_is_not_a_critical_fix_stays_out_of_a_cut_release`), and the start of a release a person cut before it, its pull request open or merged, pulls nothing in (`test_a_release_cut_before_its_start_is_topped_up_with_nothing`). Once the release pull request has merged, a critical fix goes to the next release (`test_a_merged_release_pull_request_locks_the_release_until_it_is_published`).
- [x] `devops pr check-readiness` accepts a pull request into a cut release's branch when the item it closes is in that release. This already held: `_closes_an_item_of_its_release` in `src/devops_cli/commands/pr.py` compares only the closed issue's milestone with the base branch and reads no release pull request (`test_a_pr_into_a_release_branch_is_blocked_unless_it_closes_an_item_of_that_release[its-release]` in `tests/test_pr_cmd.py`). No change was needed.
- [x] The reprioritize messages and `RELEASE_CYCLE.md` ("A Critical Fix While the Release PR Is Open", in section 7) say how a critical fix reaches a cut release. CONTEXT.md's *Cut* entry is rewritten, and its *Critical fix* entry still holds.
- [x] The lifecycle machine: its `cut` invariant says a release cut before its start pulls nothing in, and that no critical fix joins once the release pull request has merged. With the `(MERGED, FIX_JOINED)` row removed, the minimal sequence start, cut, merge unpublished, critical fix filed fails it (`test_the_machine_fails_without_the_merged_release_lock_row`). A fix filed while the release pull request is open joins, and ships where it is if the release pull request merges first (`test_a_fix_filed_while_the_release_pull_request_is_open_joins_and_ships_where_it_is`). The seeded scenarios that relied on the old lock now merge the release pull request first, so they still cover a lock move that a run stops part-way through.
- [x] An admitted fix that takes a cut release over its cap descopes its lowest-ranked unstarted item, as in a started release (`test_a_fix_that_takes_a_cut_release_over_its_cap_descopes_its_lowest_ranked_unstarted_item`).
- [x] Tests run through the in-memory store and the lifecycle machine, with no network. Each new or changed test's call phase is under 1 s; the slowest, the intake case with the release pull request open, took 0.51 s (`--durations`, run serially).
- [x] `changelog.d/1294.md` records the change; `CHANGELOG.md` and `docs/ROADMAP.md` are untouched.
- Pending a person: after the Service runs a release image with this fix, the next time a critical fix is filed while a release pull request is open, run `uv run devops roadmap intake --plan` and `uv run devops roadmap reprioritize --plan`. Both show the fix kept in that release with the "is cut, and a critical fix still joins it" reason, and the reprioritize plan prints "Current release: vX.Y.Z (cut)."
- Pending a person: before merging a release pull request that took a late critical fix, run `uv run devops gh milestones status <version>` and see no open item; then collect the fix's `changelog.d/<issue>.md` into the version's `CHANGELOG.md` section with a `chore/open-vX.Y.Z-collate-<issue>` pull request into `release/vX.Y.Z`. The collate step is superseded by [#1450](https://github.com/dan-petty/devops-cli/issues/1450) (the cut collects): the fix edits the version's section in its own pull request. If the release pull request merged while the fix was still open, set the fix's milestone to the next release and run `uv run devops pr edit <pr> --base release/vNEXT`.
- No check stops a release pull request from merging while its milestone holds an open item, so a fix still open then stays in the shipped release, whose milestone `release.yml` closes: moved to #1425, which also makes check-readiness refuse a pull request into a release branch whose release pull request has merged.

## How this composes with #1349

- **This item owns the critical-fix rows of the table**: `(CUT, FIX_JOINED)` admits, and `(MERGED, FIX_JOINED)` sends the fix on. Intake asks the same rows for a critical-fix candidate with no milestone.
- **#1349 owns a person's join**: after the start, or into a cut release, it is admitted with one comment naming the rule it bypassed, and the cap never picks it to make room. Intake keeps a candidate's own milestone.
- **A critical fix a person files into a cut release** is admitted by this item's row with the cut reason. No rule is bypassed, so #1349 has no rule-break comment to add.
- **A person's join of any other item into a cut release**: this item adds no move of it. Until #1349 lands, the started release's rows that a cut release inherits place it as before; after #1349 it stays.
- **A person's placement is not protected in `MERGED`** (owner decision, 2026-10-08, recorded on #1349). `(MERGED, FIX_JOINED) -> TO_NEXT` applies to every critical fix, one a person placed included, and #1349 skips its override in that state: the release is already in `main`, so the fix can no longer ship in it.
- **Shared lines**: `TRANSITIONS`, `MESSAGES.roadmap.reasons`, the lifecycle machine's `admitted` and `cut` invariants, CONTEXT.md and `RELEASE_CYCLE.md`. Whichever merges second rebases those hunks. The `cut` invariant judges only the start's pull-in and critical fixes, so #1349 changes only `admitted`.

## Decisions and deviations

- **`MERGED` is its own state, not a flag.** A plain flip of the `CUT` row would have admitted fixes into a release already in `main`. `MERGED` inherits `CUT`, so its only own row is the lock, and `decide` still fails closed on an event no state has a row for.
- **The cut's admission keeps its own row and reason.** `(CUT, FIX_JOINED)` admits as `STARTED` does, but with `Reason.CUT`, so the comment tells a person why the fix joined a cut release.
- **The cap binds a cut release.** An admitted fix can descope a cut release's lowest-ranked unstarted item: that item has no change in the release branch, and it would otherwise ship unfinished.
- **A fix still open when the release pull request merges stays in the shipped release.** Moving it would need a new rule for already-admitted items in `MERGED`, beyond the cut rule. `RELEASE_CYCLE.md` gives a person's recovery step: move the fix to the next release and retarget its pull request. #1425 adds the guard.
- **No test pins a person's join of another item into a cut release.** The table test pins only the rows this item owns, and criterion 2's tests are intake's placement and the start's pull-in, which are the jobs' own.
- **The late changelog fragment** is collected the way v0.2.28 collected #1290's (#1293), until #1103 moves the collection to the release merge. The automatic cut does not collect fragments. Superseded by [#1450](https://github.com/dan-petty/devops-cli/issues/1450) (the cut collects).
- **The release pull request's description** still goes stale when a fix lands; #1346 regenerates it.
- **No `is_due` change.** The merge changes no decision about an item already admitted, and a fix filed after it triggers a run by itself.

## Deliverables

- [x] `src/devops_cli/roadmap/reprioritize.py`: `ReleaseState.MERGED`, `Reason.MERGED`, the two rows, `INHERITS`, `release_state`, `_is_cut`, and the docstrings.
- [x] `src/devops_cli/roadmap/intake.py`: a shipped release read as `MERGED`, and the placement docstring.
- [x] `src/devops_cli/lang/en/messages.py`: the `cut` and `merged` reasons.
- [x] Tests: `tests/test_roadmap_reprioritize.py`, `tests/test_roadmap_intake.py`, `tests/test_roadmap_lifecycle_properties.py`.
- [x] Docs: CONTEXT.md (*Cut*), `RELEASE_CYCLE.md` (section 7), `changelog.d/README.md`, `changelog.d/1294.md`.
