# Task: Every Open P0 and P1 Item Sits in an Open Release (#882)

**Issue**: [#882](https://github.com/dan-petty/devops-cli/issues/882)
**Scope**: scope/roadmap
**Feasibility**: Confirmed against board state and runtime transitions in `reprioritize.py`. Backlog P0 and P1 placement rules operate on open planned releases without requiring remote API calls.

## Description
By the board's Priority field, open P0 and P1 items without milestones were previously left in the backlog indefinitely. `devops roadmap reprioritize` now ensures that every open P0 and P1 item that no person took out of a release sits in an open release.

- **Helper** (`roadmap/reprioritize.py`): `nearest_planned_release(run, plan, base_version, limit)` returns the nearest open planned release after `base_version` holding fewer than `limit` open items.
- **Backlog Priority Sweep** (`_sweep_backlog_priority`): In every run, after `_plan_rules` and `_plan_start`, sweeps backlog P0/P1 items in `_Ranks.first` order into the nearest open planned release holding fewer than `release_cap + release_slots` (16) items, recording the move with `Reason.PRIORITY` and event `PRIORITY_IN_BACKLOG`.
- **Displacement**: A P0 meeting a full release (16 items) displaces its lowest-ranked unimplemented P3 item (no linked PR; Status New or Ready), moving the P3 to the next release with room or to the backlog. A P1 meeting a full release displaces nothing and goes to the next release with room.
- **Horizon expansion**: When every planned release holds 16 items, the run creates the next patch release via `_create_release` and places the item there.
- **Start transitions**: At release start, New and Blocked P0/P1 items go `TO_NEXT` with `Event.PRIORITY_NEW_AT_START` and `Event.PRIORITY_BLOCKED_AT_START`, rather than dropping to the backlog.
- **Person removals stand**: An item a person took out of a release stays in the backlog, with its `Left` mark recorded at start.
- **Scope note**: Step 4 (intake placement changes) moved to follow-up issue #1534 per owner decision.

## Acceptance Criteria
- [x] **Backlog P1 placement**: A backlog P1 goes to the nearest planned release holding fewer than 16 items, with the `priority` reason comment. A P2 stays in the backlog.
- [x] **Backlog P0 displacement**: A backlog P0 meeting a release that holds 16 displaces its lowest-ranked unimplemented P3 to the next release with room; a P1 meeting 16 goes to the next release instead, displacing nothing; a P3 with a linked pull request is never displaced.
- [x] **New patch release creation**: With every planned release at 16 and no unimplemented P3 to displace, the run creates the next patch release and places the item there.
- [x] **Start transitions for P0/P1**: At a start, a New P1 goes to the next planned release, a New P2 still goes to the backlog, and a New critical fix still stays.
- [x] **Person removals stand**: A P1 that a person took out of a release stays in the backlog, and the plan lists it.
- [x] **Idempotency**: A second run with no change writes nothing.
- [x] **Lifecycle invariant**: The lifecycle machine (`tests/test_roadmap_lifecycle_properties.py`) gains invariant `"priority_releases"` asserting that after a finished run, every open P0/P1 item that no person took out of a release sits in an open release. The invariant count test is updated to 19.
- [x] **Tests offline and fast**: Targeted tests in `tests/test_roadmap_reprioritize.py` and `tests/test_roadmap_lifecycle_properties.py` pass.
- Intake placement of new P0/P1 items as they arrive: deferred to #1534.
