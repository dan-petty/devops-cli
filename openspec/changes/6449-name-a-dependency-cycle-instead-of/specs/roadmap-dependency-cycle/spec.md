## Purpose
The dependency graph of the open roadmap items, the cycle that holds an item back, and the reason that refine, stage and implement give for it.

## ADDED Requirements

### Requirement: The dependency graph names a cycle for each item
The check SHALL build one graph from the open items of a round, with the edges that the job record, the Dependencies section and the quoted titles of each item declare. `TopologicalSorter` SHALL gate the graph, and the check SHALL give a path back to each item that a dependency leads back to. The check SHALL read the item sequence it is given and SHALL send no store or GitHub request.

#### Scenario: Each item of a cycle gets its own path
- **WHEN** a test builds `DependencyGraph.of` from items A and B, where the record of A names B and the Dependencies section of B names A
- **THEN** the path of A is `#A → #B → #A`, the path of B is `#B → #A → #B`, and an item that no cycle holds has no path

#### Scenario: The graph reads the item sequence alone
- **WHEN** a test builds `DependencyGraph.of` from the items of a store that counts each read, and the items hold the cycle A to B to A
- **THEN** the graph gives the path of A, and the store counts no read

### Requirement: The shared dependency reason names a dependency cycle
`open_dependency` SHALL give a reason that names the full cycle when a dependency of the item leads back to the item, before the reason of the open issue. The reason SHALL name each issue of the cycle and SHALL say that a person removes one edge. An open dependency outside a cycle SHALL give the open-issue reason and SHALL NOT name a cycle.

#### Scenario: The reason of an item in a cycle
- **WHEN** a test calls `open_dependency` for item A of a store where the record of A names B and the Dependencies section of B names A
- **THEN** the reason names `#A → #B → #A` and not only the open issue `#B`

#### Scenario: An open dependency outside a cycle
- **WHEN** a test calls `open_dependency` for item A whose Dependencies section names the open item B and whose B names no open item
- **THEN** the reason names the open issue `#B` and names no cycle
