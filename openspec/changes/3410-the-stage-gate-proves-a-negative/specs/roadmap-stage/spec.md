## ADDED Requirements

### Requirement: The stage job records the hits of a negative search
The stage job SHALL run the literal of each negative-search verify command on the staged tree with git grep and SHALL record the matching paths before it judges the reply.

#### Scenario: A negative search has staged hits
- **WHEN** The plan gives a negative-search verify command whose literal matches paths of the staged tree.
- **THEN** The job records each matching path under the literal and passes the record to check_proposal.

### Requirement: A negative search with no staged hit is refused
check_proposal MUST refuse a negative-search literal that the recorded evidence gives with no matching path.

#### Scenario: The literal finds nothing before the change
- **WHEN** The recorded evidence for a negative-search literal holds no matching path.
- **THEN** check_proposal returns a problem that says the search already passes before the change and proves nothing.

### Requirement: A negative search that a created module keeps is refused
check_proposal MUST refuse a negative-search literal when a source path that the plan creates has an import path that contains the literal.

#### Scenario: A created module matches the literal
- **WHEN** A group creates a source path under src/devops_cli/ whose import path contains the negative-search literal.
- **THEN** check_proposal returns a problem that says the search can never pass on the produced tree.

### Requirement: A negative search with a surviving hit is accepted
check_proposal MUST accept a negative-search literal when the recorded evidence holds a matching path and no created source path has an import path that contains the literal.

#### Scenario: A staged hit survives the change
- **WHEN** The recorded evidence holds a matching path and no created source path has an import path that contains the literal.
- **THEN** check_proposal returns no problem for that literal.

### Requirement: The stage prompt asks for the hit count of a negative search
The stage prompt MUST ask the planner to call search_code with the literal of each negative-search verify command and to quote the hit count in feasibility.

#### Scenario: The planner reads the prompt
- **WHEN** The stage job plans an item whose plan gives a negative-search verify command.
- **THEN** The prompt tells the planner to call search_code with the literal and to quote the hit count in feasibility.
