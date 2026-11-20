## ADDED Requirements

### Requirement: A dependency cycle gives a person step that names it
`devops roadmap refine` SHALL give an item the next step `person` when a dependency of the item leads back to the item, before the step that its proposal gives. The detail of the step SHALL name the full cycle, and refine's section SHALL name the cycle in its Suspected block part. The round SHALL record no open issue as a blocker for that item.

#### Scenario: Two items in a cycle
- **WHEN** a refine round reads a store where the record of A names B and the Dependencies section of B names A, and each proposal is complete
- **THEN** the step of A and of B is `person`, each detail names its cycle, no open issue is a blocker of either, and each refine section names the cycle under its Suspected block heading

### Requirement: A cycle keeps an item out of Ready and ends its wait
Refine SHALL NOT set the Status to Ready for an item in a cycle, and a Ready item in a cycle SHALL go back to New. A round SHALL end the recorded wait of an item whose record names the step `blocked` when that item is in a cycle, and `devops roadmap explain` SHALL give the answer that the round gives.

#### Scenario: The Status of an item in a cycle stays New
- **WHEN** a refine round finds item A in a cycle whose proposal passes every form check
- **THEN** the step of A is `person` and the Status of A stays New, so the stage job takes no Ready item that a cycle holds back

#### Scenario: The recorded wait of a blocked item in a cycle ends
- **WHEN** a refine round finds item A whose record holds the step `blocked` on the open item B, and the record of B or its Dependencies section names A
- **THEN** the round refines A and records the step `person` with the cycle

#### Scenario: Explain ends the wait that the round ends
- **WHEN** a person runs `devops roadmap explain` for item A whose record holds the step `blocked` on the open item B, and the record of B or its Dependencies section names A
- **THEN** the refine line of the output says that refine takes the item, and names no wait on the open issue

## MODIFIED Requirements

### Requirement: An open dependency outside a cycle blocks the item
`devops roadmap refine` SHALL give an item the next step `blocked` when its validated proposal names an open issue as a dependency and no dependency of the item leads back to the item. This applies when the proposal has no open question and fits one pull request. It SHALL record the open issues in `refine.blocked_by` and SHALL NOT set the Status to Ready. A Ready item SHALL go back to New. A closed dependency SHALL NOT hold the item back.

#### Scenario: A complete proposal with one open dependency
- **WHEN** a New item has a complete proposal with one open dependency (no open question, no split, no suspected block)
- **THEN** the next step is `blocked` with that issue, the refine record holds its number, and the item stays New

#### Scenario: A Ready item with an open dependency
- **WHEN** the proposal of a Ready item meets the same conditions, and a person runs refine for the item with `--item`
- **THEN** the item goes back to New, with the next step `blocked` and the number of the blocker in its refine record

#### Scenario: A closed dependency
- **WHEN** a New item has a complete proposal with one closed dependency (no open question, no split, no suspected block)
- **THEN** the next step is `ready`, the refine record holds no blocker, and the item is Ready

## RENAMED Requirements

- FROM: `### Requirement: An open dependency that the proposal names blocks the item`
- TO: `### Requirement: An open dependency outside a cycle blocks the item`
