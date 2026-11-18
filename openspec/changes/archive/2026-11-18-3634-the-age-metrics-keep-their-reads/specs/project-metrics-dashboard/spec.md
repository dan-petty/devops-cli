## ADDED Requirements

### Requirement: The row keeps the label times of each open Item
The metrics row SHALL write to the record file of its repository the `updated_at` and the label times of each open Item: the times it read in the round and the entry that the file holds for an open Item the round did not read. It SHALL remove from that file the entry of each Item that the open item list of the round does not hold.

#### Scenario: A round writes what it read
- **WHEN** a round reads the label events of an open Item and the round completes
- **THEN** the record file of the repository holds that Item's updated_at and its label times under its issue number

#### Scenario: A deferred Item keeps its entry
- **WHEN** a round leaves an open Item unread because it reached the cap
- **THEN** the file that the round writes still holds that Item's earlier entry at its older updated_at

#### Scenario: A closed Item leaves the record
- **WHEN** an Item in the record file is not in the open item list of the round
- **THEN** the file that the round writes holds no entry for that Item

### Requirement: The row reads the label events of at most 20 Items in one round
The metrics row SHALL read the label changes of at most 20 Items in one round. It SHALL read the Items in the order of their entry, oldest first: an Item that the record file does not hold first, then an Item whose `updated_at` moved, the oldest `updated_at` in its entry first. An Item that the round does not read keeps the label times of its entry, or waits for a later round when it has no entry. So Items that move in each round do not keep another Item out of the reads.

#### Scenario: More changed Items than the cap
- **WHEN** more open Items hold an updated_at other than the one the file holds than the cap in one round
- **THEN** the round reads the label events of exactly 20 Items and the rest wait for later rounds

#### Scenario: The oldest entry comes first
- **WHEN** a round starts with an Item that the file does not hold and two moved Items whose entries hold different updated_at values
- **THEN** the round reads the Item with no entry first, then the moved Item with the older updated_at, then the other moved Item

#### Scenario: Items that move in each round do not keep an Item out
- **WHEN** 21 Items that the file holds move before each round, and one more Item has no entry
- **THEN** two rounds read the label events of all 22 Items

### Requirement: A failed write of the record keeps the round
When the record file of the metrics row cannot be written, the row SHALL log one error that names the file and SHALL send the ages and the other metrics of the round. The next round SHALL write the file again.

#### Scenario: The write fails
- **WHEN** the record file of the row cannot be written
- **THEN** the round sends its ages and logs one error that names the file, and the next round writes the file again

## MODIFIED Requirements

### Requirement: The label events of an Item are read when its updated_at moves
The metrics row SHALL read the label changes of an open Item when the record file of its repository holds no entry for the Item at its current `updated_at`. It SHALL send no request to the events of an Item whose entry holds that value, also in a process that did not write the file.

#### Scenario: Two rounds with no change
- **WHEN** two rounds run over the same Items and labels
- **THEN** the second round sends no request to the events of an issue

#### Scenario: A Status that changed
- **WHEN** a person changes the Status label of one Item between two rounds
- **THEN** the second round reads the events of that issue only, and the age counts from the new event

#### Scenario: A new process with a kept record
- **WHEN** a new process reads the record file and lists an open Item at the updated_at the file holds
- **THEN** the process sends no request to the events of that issue

## RENAMED Requirements

- FROM: `### Requirement: The label events of an Item are read when its labels change`
- TO: `### Requirement: The label events of an Item are read when its updated_at moves`
