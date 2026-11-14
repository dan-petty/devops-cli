## ADDED Requirements

### Requirement: A recorded verdict gates Ready
Refine SHALL set `status/ready` on an item only when its job record holds an `alternatives.verdict`, or when the alternatives check is off for the repository, and SHALL leave the item in `status/new` with the comment `Waiting for the alternatives check to run.` when the record holds no verdict and the check is on.

#### Scenario: An item with no verdict stays New
- **WHEN** Refine runs on an item whose job record holds no `alternatives.verdict` while the alternatives check is on for the repository
- **THEN** The item keeps `status/new` and refine writes the comment `Waiting for the alternatives check to run.`

#### Scenario: An item with a recorded verdict becomes Ready
- **WHEN** Refine runs on an item whose `alternatives.verdict` is `none`, `not-applicable`, `rejected` or `in-use` and every other readiness rule passes
- **THEN** Refine sets the item to `status/ready`.

#### Scenario: A repository whose check is off is exempt
- **WHEN** The repository is private, or it has no search provider, and the item holds no `alternatives.verdict`
- **THEN** Refine sets the item to `status/ready` when every other readiness rule passes.

### Requirement: A person's Ready label stays through a round
Refine SHALL leave a `status/ready` label that a person set on an item whose record holds no verdict, and SHALL write no other Status label on that item.

#### Scenario: A person's Ready label survives a round
- **WHEN** A person sets `status/ready` on an item with no `alternatives.verdict` and refine runs on the item
- **THEN** The item keeps `status/ready` and refine writes no other Status label.

### Requirement: The wait for a verdict ends when the check writes one
Refine SHALL keep an item whose gate fails on the wait `alternatives` with no comment read, and SHALL take the item again in the round after the alternatives check records a verdict.

#### Scenario: The recorded verdict ends the wait
- **WHEN** The alternatives check records an `alternatives.verdict` on an item that refine left on the `alternatives` wait
- **THEN** The next refine round takes the item and sets `status/ready` when every other readiness rule passes.

#### Scenario: The report names the wait of the item
- **WHEN** A round leaves an item on the `alternatives` wait and prints its refinement plan
- **THEN** The plan holds the heading of the `alternatives` wait and the line of the item under it.

### Requirement: The workflow document names the gate
The workflow document SHALL name the alternatives-verdict gate in step 2 of its eight steps.

#### Scenario: Step 2 names the gate
- **WHEN** A reader reads step 2 of the eight steps of the workflow document
- **THEN** The step text names the rule that refine sets Ready only with an `alternatives.verdict` or on a repository whose check is off.
