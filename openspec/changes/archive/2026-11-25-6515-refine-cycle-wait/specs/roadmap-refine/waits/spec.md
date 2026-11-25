# roadmap-refine/waits Specification

## MODIFIED Requirements

### Requirement: A dependency cycle gives a person step that names it
`devops roadmap refine` SHALL decide the cycle step from the open blockers of its new proposal against the round's graph, giving `person` when a dependency leads back, naming the cycle in the detail and under Suspected block, and recording no open blocker.

#### Scenario: Two items in a cycle
- **WHEN** a refine round reads a store where the record of A names B and the Dependencies section of B names A, and each proposal keeps its dependency
- **THEN** the step of A and of B is `person`, each detail names its cycle, no open issue is a blocker of either, and each refine section names the cycle under its Suspected block heading

#### Scenario: Reply removes the last edge
- **WHEN** a person reply removes the last edge of a cycle, the model proposal names no dependency, and `uv run pytest tests/roadmap/refine/test_roadmap_refine_cycle.py -k reply_removes_edge` runs
- **THEN** the test asserts that the same round gives the item no `person` cycle step and sets its Status to Ready

### Requirement: A cycle keeps an item out of Ready and ends its wait
Refine SHALL NOT set the Status to Ready for an item in a cycle, and a Ready item in a cycle SHALL go back to New. A round SHALL end the recorded wait of an item whose record holds the step `blocked` when that item is in a cycle, and SHALL end a `person` wait whose recorded cycle no longer exists in the current bodies and records of the open items. `devops roadmap explain` SHALL give the answer that the round gives.

#### Scenario: The Status of an item in a cycle stays New
- **WHEN** a refine round finds item A in a cycle whose proposal passes every form check
- **THEN** the step of A is `person` and the Status of A stays New, so the stage job takes no Ready item that a cycle holds back

#### Scenario: The recorded wait of a blocked item in a cycle ends
- **WHEN** a refine round finds item A whose record holds the step `blocked` on the open item B, and the record of B or its Dependencies section names A
- **THEN** the round refines A and records the step `person` with the cycle

#### Scenario: Explain ends the wait that the round ends
- **WHEN** a person runs `devops roadmap explain` for item A whose record holds the step `blocked` on the open item B, and the record of B or its Dependencies section names A
- **THEN** the refine line of the output says that refine takes the item, and names no wait on the open issue

#### Scenario: Other body removes the edge
- **WHEN** a person removes the edge `#2 → #1` from the body of #2, the next round refines #1, and `uv run pytest tests/roadmap/refine/test_roadmap_refine_cycle.py -k stale_cycle_wait_ends` runs
- **THEN** the test asserts that the round clears the `person` wait of #1 and sets its Status to Ready

## ADDED Requirements

### Requirement: Refine guide names the cycle step
The refine guide SHALL name the dependency cycle step in its list of next steps and state that only an open dependency outside a cycle makes an item wait.

#### Scenario: Guide text check
- **WHEN** `uv run pytest tests/roadmap/refine/test_roadmap_refine_cycle.py -k guide` runs
- **THEN** the test asserts that `docs/roadmap/refine.md` names the cycle step and the rule that only an open dependency outside a cycle makes an item wait
