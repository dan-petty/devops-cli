# roadmap-repair Specification

## Purpose
The repair pass finds the roadmap items that a placeholder reply of a model stalled, and sets them back. It lists them without a write, and with `--confirm` it clears the block that the placeholder made. It leaves each item that a person set.

## Requirements

### Requirement: The pass lists a filler return
`devops roadmap repair` SHALL list each open Item that holds Status New, whose job record holds the same Status and the next step `ready`, and whose newest comment is a comment of the stage job with an evidence text that is a placeholder. Each line SHALL hold the number, the title and the cause `filler return`. The command SHALL write nothing without `--confirm`.

#### Scenario: A filler return
- **WHEN** an Item holds Status New and its newest comment is a stage return with the evidence "Not yet: I need to inspect the repository first."
- **THEN** the list names the Item with the cause `filler return`

#### Scenario: A return that gives evidence
- **WHEN** an Item holds Status New and its newest comment is a stage return whose evidence is a sentence that is not a placeholder
- **THEN** the list does not name the Item

#### Scenario: Nothing to repair
- **WHEN** no Item is stalled
- **THEN** the command prints that nothing is stalled and writes nothing

### Requirement: The pass lists a stub refine block
`devops roadmap repair` SHALL list each open Item that holds Status New, whose job record holds the same Status and the next step `person`, whose newest comment is a comment of refine, and whose refine section has the recorded hash and holds a placeholder as the problem statement or as the existing-tool answer. The cause SHALL be `stub refine block`.

#### Scenario: A stub refine block
- **WHEN** an Item holds Status New with the next step `person`, and its section holds `x` as the problem statement
- **THEN** the list names the Item with the cause `stub refine block`

#### Scenario: A real section
- **WHEN** the section holds a sentence as the problem statement and as the existing-tool answer
- **THEN** the list does not name the Item

### Requirement: The pass leaves an Item that a person set
The pass SHALL NOT list or change an Item whose Status label differs from the Status in the job record, an Item that holds an `owner/*` label of an agent or a person, an Item that a runner Job holds, an Item that is closed, an Item with a comment after the comment of the job, and an Item whose refine section a person edited.

#### Scenario: A person set the Status
- **WHEN** a person set Status New on an Item whose record holds Ready, and the newest comment is a filler return
- **THEN** the list does not name the Item

#### Scenario: A person replied
- **WHEN** a person commented after a filler return
- **THEN** the list does not name the Item

#### Scenario: A person edited the section
- **WHEN** the hash of the refine section differs from the recorded hash
- **THEN** the list does not name the Item

#### Scenario: A person owns the Item
- **WHEN** an Item has the label `owner/human`
- **THEN** the list does not name the Item

### Requirement: Confirm sets a returned Item back
With `--confirm`, the pass SHALL read each listed Item again and skip it when it no longer qualifies. For a filler return it SHALL set the Status Ready. An Item that fails SHALL not stop the others, and the command SHALL exit 1 when one failed.

#### Scenario: A filler return is set back
- **WHEN** the pass runs with `--confirm` on an Item stalled by a filler return
- **THEN** the Item holds Status Ready and its record holds Status Ready

#### Scenario: An Item changed since the read
- **WHEN** a person sets an owner on a listed Item after the list and before the write
- **THEN** the pass writes nothing for it

#### Scenario: A second run
- **WHEN** the pass runs with `--confirm` twice
- **THEN** the second run lists nothing

### Requirement: Confirm clears a stub refine block
With `--confirm`, the pass SHALL write the body of an Item stalled by a stub refine block without the section of refine, then clear the refine marks `refine.body_hash`, `refine.section_hash`, `refine.failed_body_hash`, `refine.next_step`, `refine.blocked_by`, `refine.block_paths`, `refine.needs_split`, `refine.tries`, `refine.failed_check` and `refine.failure`.

#### Scenario: A stub block is cleared
- **WHEN** the pass runs with `--confirm` on an Item stalled by a stub refine block
- **THEN** the body holds no refine section, the refine marks are cleared, and the text outside the section is unchanged

### Requirement: The dry run makes no request
`devops roadmap repair --dry-run` SHALL make no request and SHALL NOT open the store. It SHALL print the requests of the pass with their exact commands: the listing of the open issues, the listing of the comments of each candidate, and the writes of `--confirm`.

#### Scenario: Dry run
- **WHEN** `devops roadmap repair --repo example/roadmap --dry-run` runs
- **THEN** the output states that no request was made, lists the issue listing and the comment listing, and the store was not opened
