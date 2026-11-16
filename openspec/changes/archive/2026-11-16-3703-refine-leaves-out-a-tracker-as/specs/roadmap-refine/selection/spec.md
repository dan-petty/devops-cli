## ADDED Requirements

### Requirement: Refine leaves out a tracker
The refine job SHALL leave out an open item whose sub-issues count is above zero or that holds the label `type/epic`, whether a round selects it or `--item` names it. It SHALL make no model call, write no body, no mark, no Status and no comment for the item. Its reason SHALL be the text of `refine_left_tracker`, and `devops roadmap explain` SHALL print that text.

#### Scenario: A round leaves out an item with sub-issues
- **WHEN** a refine round selects an open New item with two sub-issues
- **THEN** the item waits with the tracker text of refine, and the round makes no model call and writes no body, no mark, no Status and no comment for it

#### Scenario: A round leaves out an item with the epic label
- **WHEN** a refine round selects an open New item with the label type/epic and no sub-issues
- **THEN** the item waits with the tracker text of refine, and the round makes no model call and writes no body, no mark, no Status and no comment for it

#### Scenario: A named tracker is left out
- **WHEN** `devops roadmap refine --item` names an open New item with one sub-issue
- **THEN** the round takes no item, makes no model call, and lists the item as waiting with the tracker text of refine

#### Scenario: Explain gives the tracker reason
- **WHEN** `devops roadmap explain` reads an open New item with two sub-issues and no refine record
- **THEN** the refine verdict is false with the tracker text, and the command writes nothing

#### Scenario: A plain item still refines
- **WHEN** a refine round selects an open New item with no sub-issues and no epic label
- **THEN** the round makes one model call, writes the item and posts one comment

## MODIFIED Requirements

### Requirement: Refine tells the author of an item that the jobs do not trust one time
A round that leaves out an item that the jobs do not trust, that has no sub-issues and holds no `type/epic` label, and that finds no comment that holds `CONST_ROADMAP_REFINE_OUTSIDE_MARKER` on it, SHALL write one comment that names the author, the association and `devops roadmap refine --item <number>`. A round that finds the marker SHALL write no comment. A round SHALL write no comment for a tracker, because its sub-issues deliver it. The comment SHALL not count as a reply to the model.

#### Scenario: Another bot opens an item
- **WHEN** `dependabot[bot]` opened a New item and two rounds run
- **THEN** the first round writes one comment that holds the marker and "Its author is dependabot[bot], and its association with the repository is CONTRIBUTOR.", the second round writes none, and neither round calls a model for the item

#### Scenario: An outside account opens an item
- **WHEN** an account with the association NONE opened a New item and two rounds run
- **THEN** the item has one comment that holds the marker after the second round

#### Scenario: Another bot opens a tracker
- **WHEN** `dependabot[bot]` opened a New item with two sub-issues and two rounds run
- **THEN** neither round writes a comment on the item and neither round calls a model for it
