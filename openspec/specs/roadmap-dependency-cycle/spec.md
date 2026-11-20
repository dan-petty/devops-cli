# roadmap-dependency-cycle Specification

## Purpose
The dependency graph of the open roadmap items, the cycle that holds an item back, and the reason that refine, stage and implement give for it.

## Requirements

### Requirement: The dependency graph names a cycle for each item
The check SHALL build one graph from the open items that a round lists, with the edges that the job record, the Dependencies section and the quoted titles of each item declare. It SHALL keep only an open item as a node, and it SHALL drop an edge to an issue that the sequence does not hold. When a caller asks for the cycle of an item, the check SHALL give a path from the item through its dependencies back to the item, or no path when no dependency of the item leads back to it.

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

### Requirement: The path of an item is a shortest cycle
The path that the check gives for an item SHALL be a shortest cycle through the item. A breadth-first search over the edges, in their order, SHALL find the path, and the check SHALL search only for the item that the caller asks for.

#### Scenario: The path is a shortest cycle
- **WHEN** a test builds `DependencyGraph.of` from items A, B, C and D, where A names B and C, B names A, C names D and D names A
- **THEN** the path of A is `#A → #B → #A` and not `#A → #C → #D → #A`, the path of C is `#C → #D → #A → #C`, and the path of D is `#D → #A → #C → #D`

#### Scenario: A self-loop, a lead-in and a closed link
- **WHEN** a test builds `DependencyGraph.of` from item A that names itself, item B that names C, items C and D that name each other, the open item E that names the closed item F, and F that names E
- **THEN** the path of A is `#A → #A`, B gets no path, the path of C is `#C → #D → #C`, and E gets no path

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
`devops roadmap refine` SHALL build the graph once for each round from the open items that the round already reads for the owner-question frames. It SHALL give that graph to the selection and to the refine of each item, and it SHALL read the open items once for the round.

#### Scenario: One graph for each round
- **WHEN** a test runs a refine round over a store that counts the calls of `open_items()`, and the items of the store hold the cycle A to B to A
- **THEN** the store counts one call of `open_items()` and the round gives A and B the step `person`

#### Scenario: A round reads no listing for the graph
- **WHEN** a test runs a refine round over a store that counts the reads of the whole item listing, and the store holds no item that the round refines
- **THEN** the round makes the one read of the whole item listing that the backlog makes, and reads no other listing for the graph

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
