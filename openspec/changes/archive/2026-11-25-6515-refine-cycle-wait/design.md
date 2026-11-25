# Design

## Decisions
- **Evaluate cycle from proposal blockers**: Add `DependencyGraph.with_edges(number, blockers)` returning a shallow copy with `edges[number] = blockers`. In `refine_one_item`, when `blockers` is non-empty, compute `cycle = held.with_edges(item.number, blockers).cycle_of(item.number)` so removed or newly introduced dependencies take effect in the same round. In `plan_refine`, after refining a non-skipped item, update `graph` with its new open blockers so later candidates refined in the same round also see the updated edges.
- **Clear stale cycle `person` waits**: Extract the recorded cycle tuple from the `### Suspected block` part of `item.body`'s refine section using the `MESSAGES.roadmap.dependency_cycle` template (`_recorded_cycle`). When `_recorded_step(item)` is `NextStep.PERSON` and `_recorded_cycle(item.body)` returns a cycle path, check that every consecutive edge `(u, v)` along that recorded cycle path still exists in `held.edges` of open items. If any edge or node is gone, `_still_waiting` returns `None` before waiting for comments or replies.
- **Rules version bump**: Advance `CONST_ROADMAP_REFINE_RULES_SINCE` in `src/devops_cli/config/constants.py` and document the new timestamp in `docs/roadmap/refine.md` so items left in a stale cycle wait under earlier rules receive one new look.

## Rejected alternatives
- **Use pre-round `DependencyGraph` for refined items**: Keeps old job-record and old-body edges active on the round where a reply or body change removes them, forcing a person to reply twice.
- **Rebuild `DependencyGraph` from store for every item**: Adds redundant `open_items()` reads per item in a round, violating the single-read budget per round.
- **Check only `held.cycle_of(item.number) is None` on `person` waits**: Leaves a stale recorded cycle message in place when an old cycle broke and a different cycle formed.
