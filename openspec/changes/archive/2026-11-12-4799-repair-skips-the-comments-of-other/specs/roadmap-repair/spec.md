## MODIFIED Requirements

### Requirement: The pass lists a filler return
`devops roadmap repair` SHALL list each open Item that holds Status New, whose job record holds the same Status and the next step `ready`, and whose newest stage comment is a return with an evidence text that is a placeholder, with no comment of a person after it. Each line SHALL hold the number, the title and the cause `filler return`. The command SHALL write nothing without `--confirm`.

#### Scenario: A filler return
- **WHEN** an Item holds Status New and its newest comment is a stage return with the evidence "Not yet: I need to inspect the repository first."
- **THEN** the list names the Item with the cause `filler return`

#### Scenario: A comment of another job after the return
- **WHEN** the alternatives check comments after a filler return
- **THEN** the list names the Item with the cause `filler return`

#### Scenario: A return that gives evidence
- **WHEN** an Item holds Status New and its newest comment is a stage return whose evidence is a sentence that is not a placeholder
- **THEN** the list does not name the Item

#### Scenario: Nothing to repair
- **WHEN** no Item is stalled
- **THEN** the command prints that nothing is stalled and writes nothing

### Requirement: The pass lists a stub refine block
`devops roadmap repair` SHALL list each open Item that holds Status New, whose job record holds the same Status and the next step `person`, whose newest refine comment has no comment of a person after it, and whose refine section has the recorded hash and holds a placeholder as the problem statement or as the existing-tool answer. A comment that holds the marker of a roadmap job SHALL NOT be a reply. The cause SHALL be `stub refine block`.

#### Scenario: A stub refine block
- **WHEN** an Item holds Status New with the next step `person`, and its section holds `x` as the problem statement
- **THEN** the list names the Item with the cause `stub refine block`

#### Scenario: A stub text that the census found
- **WHEN** the section holds `pending` as the problem statement and as the existing-tool answer
- **THEN** the list names the Item with the cause `stub refine block`

#### Scenario: A comment of another job after the question
- **WHEN** the alternatives check, the intake reason or a retitle comments after the question of refine, with the login of the owner
- **THEN** the list names the Item with the cause `stub refine block`

#### Scenario: A real section
- **WHEN** the section holds a sentence as the problem statement and as the existing-tool answer
- **THEN** the list does not name the Item

### Requirement: The pass leaves an Item that a person set
The pass SHALL NOT list or change an Item whose Status label differs from the Status in the job record, an Item that holds an `owner/*` label of an agent or a person, an Item that a runner Job holds, an Item that is closed, an Item with a comment of a person after the newest comment of the job, and an Item whose refine section a person edited.

#### Scenario: A person set the Status
- **WHEN** a person set Status New on an Item whose record holds Ready, and the newest comment is a filler return
- **THEN** the list does not name the Item

#### Scenario: A person replied
- **WHEN** a person commented after a filler return
- **THEN** the list does not name the Item

#### Scenario: A person replied before a comment of another job
- **WHEN** a person replied to the question of refine and the alternatives check commented after the reply
- **THEN** the list does not name the Item

#### Scenario: A person edited the section
- **WHEN** the hash of the refine section differs from the recorded hash
- **THEN** the list does not name the Item

#### Scenario: A person owns the Item
- **WHEN** an Item has the label `owner/human`
- **THEN** the list does not name the Item
