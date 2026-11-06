## ADDED Requirements

### Requirement: A rejected or in-use check adds no question
When the recorded check of an item has the verdict `rejected` or `in-use`, refine SHALL add no question, SHALL NOT set the next step `PERSON` because of the check, and SHALL NOT record `refine.alternatives_asked`. The request SHALL hold the verdict, the tool URL, the block and the job's latest comment of that check under the key `alternatives`, as for any check.

#### Scenario: A rejected check
- **WHEN** refine plans a New item whose recorded check has the verdict `rejected` and a tool, and the item otherwise meets every rule of the Ready check
- **THEN** the item has no open question and refine sets it Ready

#### Scenario: An in-use check
- **WHEN** refine plans a New item whose recorded check has the verdict `in-use` and a tool, and the item otherwise meets every rule of the Ready check
- **THEN** the item has no open question and refine sets it Ready

#### Scenario: The request
- **WHEN** refine plans an item whose recorded check has the verdict `rejected`
- **THEN** the proposal request holds `alternatives` with the verdict `rejected`, the tool URL and the text of the job's comment
