## ADDED Requirements

### Requirement: One rule decides the open blockers of an item
`open_blockers` SHALL decide the open blockers among the dependencies of an item for refine, stage, implement and the dependency graph. The item itself, its parent tracker and each tracker above the parent SHALL be no blocker. An open dependency that is no tracker SHALL be a blocker, and a closed issue SHALL hold nothing back. The rule SHALL read the parent links from a read that the job already makes, and it SHALL send no request for them.

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

## MODIFIED Requirements

### Requirement: The dependency graph names a cycle for each item
The check SHALL build one graph from the open items that a round lists. The edges of an item SHALL be the blockers that the rule of the requirement "One rule decides the open blockers of an item" gives for the issues that its job record, its Dependencies section and its quoted titles declare, with only the open items of the sequence as dependencies. It SHALL keep only an open item as a node, and it SHALL drop an edge to an issue that the sequence does not hold. When a caller asks for the cycle of an item, the check SHALL give a path from the item through its dependencies back to the item, or no path when no dependency of the item leads back to it.

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
