# Design

## Decisions

- **One rule in `dependencies.py`.** `open_blockers(item, numbers, found, tree)` decides the open blockers for refine, stage, implement and the dependency graph. `found` reads one dependency: the jobs give `store.item`, as before, and the graph gives the open items of its sequence, so the graph sends no request. `dependencies.py` imports from `refine.py`, so `refine.py` imports the rule inside its helper `_blockers`.
- **The tree reads every Item, and only when it must.** `ItemTree` reads the `parent` of each Item from a read that it calls the first time a caller asks for a link. Stage and implement give `store.items()`, which they read for the quoted titles. Refine gives `store.items` too, as a lazy read: the round gives that tree to `DependencyGraph.of`, which keeps it as `DependencyGraph.tree`, and the proposal check and the blocked wait read it there. So refine and stage read the same ancestors, also through a closed parent. The rule reads the tree only when a dependency is an open tracker. `GitHubRoadmapStore` keeps the whole listing after its first read, the Service reads it through the incremental snapshot, and `validate_proposal` already reads it for each refined item.
- **A blocked wait builds no graph while no recorded blocker is open.** The wait computes its blockers first and builds the graph for the cycle check only when a blocker is open, so `devops roadmap explain` and `refine --item` read no open listing for a closed blocker.
- **An ancestor is no blocker, whatever its state.** The rule skips the parent that the item names before it reads the dependency, and a tracker above the parent when the tree holds the link. A parent has a sub-issue, so it is a tracker, and only a tracker can be an ancestor.
- **Another tracker gives its open sub-issues.** The rule follows the sub-issues that are trackers, with a set of the trackers already read, and skips the item and its ancestors. The order is the order of the dependencies, then the number order of the sub-issues. The listing gives no order of the sub-issues of a parent, so the number order is the stable order.
- **A tracker with no open sub-issue holds nothing back.** It has no open work, and no job closes it.
- **The graph applies the same rule.** An edge from an item to its parent tracker made a cycle when the tracker named the item, so refine gave the person step for a cycle that holds nothing back. An edge to another tracker hid a cycle through its sub-issues. `test_an_edge_to_the_parent_tracker_closes_no_cycle` and `test_an_edge_to_another_tracker_leads_through_its_open_sub_issues` show both results. An item that names itself is no blocker of itself, so it gets no self-loop.
- **The reason names the numbers only.** The text of a wait and of a reason names the open sub-issues, and adds no new message. The recorded blockers of a new round are the sub-issues, so a later wait reads them directly.
- **`validate_proposal` keeps the tracker.** The Dependencies part of the refine section names each known dependency of the proposal. The blocker rule removes the tracker when it decides a blocker.

## Rejected alternatives

- **The rule in `store.py`.** The store reads items. It does not decide which open item holds a job back. Only the tree of the read is in the store.
- **Leave out every tracker.** An item that waits on the work of another tracker then waits on nothing.
- **A new read of `issues/<n>/parent` and `issues/<n>/sub_issues` for each item.** The listing already gives the parent of each issue, so these reads add a request for each item and give no new data.
- **The tree from the open items of the round in refine.** A closed parent breaks the chain of ancestors, so a tracker above a closed parent counts as another tracker in refine and as an ancestor in stage. On 2026-11-20 this read lost an ancestor of #4876 (#4679, #4735), #5047 (#4771), #5049 (#4780) and #5922 (#4675, #4735). `test_a_tracker_above_a_closed_parent_holds_nothing_back` fails with that tree.
- **Keep the graph edges as they are.** The two graph tests above fail with the old edges.
