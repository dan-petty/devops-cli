# Proposal: #6450

## Why

Refine, stage and implement count an open tracker as an open dependency (#6450). A tracker is an item with sub-issues or the label `type/epic` (`Item.is_tracker`). No job closes a tracker: it closes after its sub-issues. So an item that waits on its own parent tracker waits with no end, and an item that waits on another tracker waits for that whole plan and for a person.

## What Changes

- `Item` gets the field `parent`, the number of the issue that has the item as a sub-issue. The issue listing of GitHub already gives it, and `IssueRecord.parent` already holds it, so the store sends no new request.
- The new class `ItemTree` in `src/devops_cli/roadmap/stores/store.py` gives the ancestors of an item and the open sub-issues of an issue from the Items of one read.
- The new function `open_blockers` in `src/devops_cli/roadmap/dependencies.py` is the one rule that decides the open blockers of an item:
  - The item itself, its parent tracker and each tracker above it is no blocker.
  - An open tracker gives its open sub-issues in its place. A sub-issue that is a tracker gives its own. The item and its ancestors are never in that list. A tracker with no open sub-issue holds nothing back.
  - Any other open dependency is a blocker, as before. A closed issue holds nothing back.
  - The order is the order of the dependencies, then the order of the sub-issues, with no duplicate.
- Each reader uses the rule: the refine proposal (`_open_dependencies`), the recorded blocked wait of refine (`_open_blockers`), the Dependencies section and the record in the stage job (`open_dependency`, `_recorded_blocker`), the Dependencies section and the plan proposal in the implement job (`open_dependency`, `open_issue_dependencies`), and the edges of `DependencyGraph`. A recorded wait on a parent tracker ends in the next round, and a recorded wait on another tracker names the open sub-issues of that tracker. `devops roadmap explain` gives the same reasons.
- `validate_proposal` keeps each known dependency of the proposal, so the Dependencies part of the refine section still names the tracker. Only the blocker decision changes.
- The hold line of #6521 still holds an item: #6521 has no sub-issue and no `type/epic` label, so it is no tracker.
- The change carries a spec delta, because the next step of refine, the reasons of stage and implement and the output of `devops roadmap explain` change.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-dependency-cycle`: The dependency graph names a cycle for each item, The path of an item is a shortest cycle, One rule decides the open blockers of an item (added), Another tracker holds an item back with its open sub-issues (added)
- `roadmap-refine/waits`: An open dependency outside a cycle blocks the item, The last blocker to close ends the block
- `roadmap-stage/selection`: The stage selection leaves out an item with an open recorded blocker, An open tracker holds back no Ready item (added)
- `roadmap-implement-job/selection`: The implement judge leaves out an open dependency

## Impact

- Code: `src/devops_cli/roadmap/dependencies.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/implement/implement.py`
- Documents: `docs/roadmap/refine.md`, `docs/roadmap/stage.md`
- Tests: `tests/roadmap/test_roadmap_dependencies.py`, `tests/roadmap/refine/test_roadmap_dependency_graph.py`, `tests/roadmap/refine/test_roadmap_refine_blocked.py`, `tests/roadmap/refine/test_roadmap_refine_cycle.py`, `tests/roadmap/stage/test_roadmap_stage_selection.py`, `tests/roadmap/implement/test_roadmap_implement_selection.py`

## Feasibility

- The live records on 2026-11-20: #4671 holds `refine.blocked_by` `4624`, its parent. #4600 holds `4517,4598`, and #4517 is its parent. #5230 holds `5223,5229`, and #5223 is its parent. #4733 holds `4624,4720,4742,4759,4761`, and #4624 and #4742 are trackers. Each record holds `refine.next_step` `blocked`.
- `devops roadmap explain 4671` on origin/main b5c9d1214 gave "Refine job: no. The item waits for #4624 to close." `devops roadmap explain 4909` gave "Stage job: no. The item depends on the open issue #4893.", and #4893 is the parent of #4909.
- One read of the 813 open issues and pull requests on 2026-11-20 gave 803 open items and 44 open trackers. 30 open items have a recorded or a body blocker that is an open tracker: 5 name an ancestor, 25 name another tracker. 129 open items name #6521 in their Dependencies section, and #6521 is an open item that is no tracker.
- `_open_dependencies` and `_open_blockers` (`src/devops_cli/roadmap/refine/refine.py`) and `open_issue_dependencies` (`src/devops_cli/roadmap/dependencies.py`) kept each open issue and did not read `Item.is_tracker`.
- The REST issue listing gives `parent_issue_url` and `sub_issues_summary` for each issue. `_IssuePayload.parent` (`src/devops_cli/roadmap/stores/github_store.py`) maps the URL to the number, `IssueRecord.parent` holds it, and `item_of` copies each field that `Item` declares. So `Item.parent` needs no new request.
- `src/devops_cli/roadmap/dependencies.py` imports `body_dependencies` and `DependencyGraph` from `src/devops_cli/roadmap/refine/refine.py`. So refine imports the rule inside a function, as it does for `premise.definition_lines`.

## Existing Tool Considered

The GitHub sub-issues data (`parent_issue_url` and `sub_issues_summary` of the issue listing) gives the tree, and the store already reads it. No open, maintained tool or library decides the blockers of a roadmap item. The rule costs about 40,000 tokens and 1 hour to build, keep and fix. The change deletes `_is_open` of `src/devops_cli/roadmap/refine/refine.py`.
