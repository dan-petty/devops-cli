# roadmap-dependency-cycle Specification

## Purpose
The dependency graph of the open roadmap items, the cycle that holds an item back, and the reason that refine, stage and implement give for it.

## Requirements

### Requirement: The dependency graph names a cycle for each item
The check SHALL build one graph from the open items that a round lists. The edges of an item SHALL be its open blockers (the requirement "One rule decides the open blockers of an item") among the issues that its job record, its Dependencies section and its quoted titles declare. Only an open item of the sequence SHALL be a node or a dependency. For an item, the check SHALL give a path through its dependencies back to it, or no path when none leads back.

#### Scenario: Each item of a cycle gets its own path
- **WHEN** a test builds `DependencyGraph.of` from items A and B, where the record of A names B and the Dependencies section of B names A
- **THEN** the path of A is `#A → #B → #A`, the path of B is `#B → #A → #B`, and an item that no cycle holds has no path

#### Scenario: An edge to an issue outside the sequence is dropped
- **WHEN** a test builds `DependencyGraph.of` from items A and B only, where the record of A names the issue #999 that the sequence does not hold and the record of B names A
- **THEN** A and B get no path, and the edge of A names no issue

#### Scenario: A closed dependency gives no edge
- **WHEN** a test builds `DependencyGraph.of` from the open item A and the closed item B, where the record of A names B
- **THEN** B is no node, A gets no path, and the graph holds no edge of A

#### Scenario: Two cycles that share an edge
- **WHEN** a test builds `DependencyGraph.of` from items A, B and C, where A names B, B names A, B names C and C names A
- **THEN** the graph gives a path for A, a path for B and a path for C

#### Scenario: An edge to the parent tracker
- **WHEN** a test builds `DependencyGraph.of` from the tracker T and its sub-issue A, where the record of A names T and the Dependencies section of T names A
- **THEN** neither A nor T gets a path

#### Scenario: An edge to another tracker
- **WHEN** a test builds `DependencyGraph.of` from the items A, T and B, where the record of A names the tracker T, B is the open sub-issue of T, and the record of B names A
- **THEN** the path of A is `#A → #B → #A`

### Requirement: The path of an item is a shortest cycle
The path that the check gives for an item SHALL be a shortest cycle through the item. A breadth-first search over the edges, in their order, SHALL find the path, and the check SHALL search only for the item that the caller asks for.

#### Scenario: The path is a shortest cycle
- **WHEN** a test builds `DependencyGraph.of` from items A, B, C and D, where A names B and C, B names A, C names D and D names A
- **THEN** the path of A is `#A → #B → #A` and not `#A → #C → #D → #A`, the path of C is `#C → #D → #A → #C`, and the path of D is `#D → #A → #C → #D`

#### Scenario: A self-loop, a lead-in and a closed link
- **WHEN** a test builds `DependencyGraph.of` from item A that names itself, item B that names C, items C and D that name each other, the open item E that names the closed item F, and F that names E
- **THEN** A gets no path, because an item is no blocker of itself, B gets no path, the path of C is `#C → #D → #C`, and E gets no path

#### Scenario: A long ring
- **WHEN** a test gives `DependencyGraph` the edges of a ring of 20,000 items, where each item names the next item and the last item names the first
- **THEN** the path of the first item is the whole ring back to the first item

### Requirement: The shared dependency reason names a dependency cycle
`open_dependency` SHALL give a reason that names the full cycle when a dependency of the item leads back to the item. The reason SHALL name each issue of the cycle and SHALL say that a person removes one edge. An open dependency outside a cycle SHALL give the open-issue reason and SHALL NOT name a cycle. An item whose body and quoted titles name no open issue SHALL get no reason.

#### Scenario: The reason of an item in a cycle
- **WHEN** a test calls `open_dependency` for item A of a store where the Dependencies section of A names the open item B and the record of B names A
- **THEN** the reason names `#A → #B → #A` and not only the open issue `#B`

#### Scenario: An open dependency outside a cycle
- **WHEN** a test calls `open_dependency` for item A whose Dependencies section names the open item B and whose B names no open item
- **THEN** the reason names the open issue `#B` and names no cycle

#### Scenario: An item whose body names no open issue
- **WHEN** a test calls `open_dependency` for item A whose body names no open issue and whose record names the open item B
- **THEN** the reason is None and no cycle reason is given

### Requirement: The round builds one graph from the listing it already reads
`devops roadmap refine` SHALL build the graph once for each round from the open items that the round already reads for the owner-question frames. It SHALL give that graph to the selection and to the refine of each item, and it SHALL read the open items once for the round. The graph SHALL read the whole item listing for the parent links only when an open item names an open tracker. A blocked wait SHALL build no graph of its own while no recorded blocker is open.

#### Scenario: One graph for each round
- **WHEN** a test runs a refine round over a store that counts the calls of `open_items()`, and the items of the store hold the cycle A to B to A
- **THEN** the store counts one call of `open_items()` and the round gives A and B the step `person`

#### Scenario: A round reads no listing for the graph
- **WHEN** a test runs a refine round over a store that counts the reads of the whole item listing, the store holds no item that the round refines, and no open item names an open tracker
- **THEN** the round makes the one read of the whole item listing that the backlog makes, and reads no other listing for the graph

#### Scenario: A wait whose blocker closed builds no graph
- **WHEN** `refine_left_out` judges an item whose record holds the step `blocked` on an issue that closed, over a store that counts the calls of `open_items()`
- **THEN** it gives no wait, and the store counts one call of `open_items()`, for the frames

### Requirement: Stage and implement build one graph for each selection
The stage and the implement selections SHALL each build the dependency graph at most once, when the first judged item has an open dependency, and each later item SHALL get its reason from that graph. A selection in which no judged item has an open dependency SHALL build no graph. The caller SHALL give the graph to `open_dependency` as the keyword `graph`, a function that `open_dependency` calls only when a dependency of the item is open.

#### Scenario: One graph for a stage selection
- **WHEN** a test counts the calls of `DependencyGraph.of` while the stage selection judges three items that each depend on one open issue
- **THEN** the count is one, and each of the three items gets the open-issue reason

#### Scenario: One graph for an implement selection
- **WHEN** a test counts the calls of `DependencyGraph.of` while the implement selection judges two Staged items that each depend on one open issue
- **THEN** the count is one, and each of the two items gets the open-issue reason

#### Scenario: No graph without an open dependency
- **WHEN** a test counts the calls of `DependencyGraph.of` while the stage selection judges two items whose Dependencies sections name only a closed issue
- **THEN** the count is zero, and the selection takes both items

### Requirement: One rule decides the open blockers of an item
`open_blockers` SHALL decide the open blockers among the dependencies of an item for refine, stage, implement and the dependency graph. The item itself, its parent tracker and each tracker above the parent SHALL be no blocker. An open dependency that is no tracker SHALL be a blocker, and a closed issue SHALL hold nothing back. The rule SHALL read the parent links of every Item, closed ones too, from the issue listing, and only when a dependency is an open tracker.

#### Scenario: The parent tracker of an item
- **WHEN** a test calls `open_dependency` for an item whose Dependencies section names its open parent tracker
- **THEN** the reason is None

#### Scenario: A tracker above the parent
- **WHEN** a test calls `open_dependency` for an item whose Dependencies section names the open tracker above its parent
- **THEN** the reason is None

#### Scenario: An open hold issue that is no tracker
- **WHEN** the Dependencies section of an item that is a sub-issue of a tracker holds the hold line `- #<hold> (hold: ... of #<plan>)`, the hold issue has no sub-issue and no `type/epic` label, and the plan is a tracker
- **THEN** the reason names `#<hold>` only

### Requirement: Another tracker holds an item back with its open sub-issues
An open tracker that is no ancestor of the item SHALL give its open sub-issues in its place, and a sub-issue that is a tracker SHALL give its own. The item and its ancestors SHALL never be in that list. A tracker with no open sub-issue SHALL hold nothing back. The blockers SHALL come in the order of the dependencies, then in the number order of the sub-issues, each once.

#### Scenario: Another tracker
- **WHEN** a test calls `open_dependency` for an item whose Dependencies section names another open tracker with the open sub-issues B and C and one closed sub-issue
- **THEN** the reason names `#B, #C` and not the tracker

#### Scenario: A tracker with no open sub-issue
- **WHEN** the Dependencies section names an open tracker whose one sub-issue is closed, and an open item with the label `type/epic` and no sub-issue
- **THEN** `open_dependency` gives no reason

#### Scenario: A nested tracker
- **WHEN** the Dependencies section names the open tracker T and the open tracker S, where T holds S and the plain item C, and S holds the item B
- **THEN** the reason names `#B, #C`, each once

#### Scenario: The item among the sub-issues of a tracker
- **WHEN** the listing holds the item as a sub-issue of the tracker T beside the open item B, the read of the item gives no parent, and the Dependencies section names T and the item itself
- **THEN** the reason names `#B` only
