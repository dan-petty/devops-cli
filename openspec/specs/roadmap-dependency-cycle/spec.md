# roadmap-dependency-cycle Specification

## Purpose
The dependency graph of the open roadmap items, the cycle that holds an item back, and the reason that refine, stage and implement give for it.

## Requirements

### Requirement: The dependency graph names a cycle for each item
The check SHALL build one graph from the open items that a round lists, with the edges that the job record, the Dependencies section and the quoted titles of each item declare. It SHALL keep only an open item as a node, and it SHALL drop an edge to an issue that the sequence does not hold. `TopologicalSorter` SHALL gate the graph, and the check SHALL give a path back to each item that a dependency leads back to.

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

### Requirement: The shared dependency reason names a dependency cycle
`open_dependency` SHALL give a reason that names the full cycle when a dependency of the item leads back to the item. The reason SHALL name each issue of the cycle and SHALL say that a person removes one edge. An open dependency outside a cycle SHALL give the open-issue reason and SHALL NOT name a cycle. An item whose body and quoted titles name no open issue SHALL get no reason and SHALL build no graph.

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
