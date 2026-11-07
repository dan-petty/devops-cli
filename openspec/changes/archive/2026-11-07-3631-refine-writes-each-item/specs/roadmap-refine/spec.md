## ADDED Requirements

### Requirement: A round writes each item when the item is done
The refine round of the Service SHALL write the result of each item as soon as that item is done, before it takes the next item, so a stop of the Service loses at most the item in progress and the next round takes the items that are not written.

#### Scenario: Round of three items stops in the plan of item three
- **WHEN** A refine round of 3 items stops in the plan of item 3.
- **THEN** Items 1 and 2 carry their refine result, item 3 stays New, and the next round takes item 3 first.

### Requirement: Plan without a writer writes nothing
`plan_refine` SHALL write nothing to any item when the caller gives it no writer.

#### Scenario: Plan run with no writer
- **WHEN** `plan_refine` runs on a round of 3 items with no writer.
- **THEN** The store receives no write, and the 3 items stay New.

### Requirement: A failed write does not stop the round
The refine round SHALL log a write that fails for one item, count the item as failed, write the other items, and fail at its end with the number of each item that it could not write.

#### Scenario: Write of item two fails
- **WHEN** The write of the body of item 2 fails in a round of 3 items.
- **THEN** Items 1 and 3 are written, item 2 stays New, and the round raises an error that names item 2.

### Requirement: A round logs its start and its end
The refine round SHALL log one line at its start and one line at its end, and the end line SHALL give the counts of items taken, written and failed.

#### Scenario: Round with one failed write
- **WHEN** A refine round takes 3 items, writes 2 and fails 1.
- **THEN** The log holds one start line with 3 items taken and one end line with taken=3, written=2 and failed=1.
