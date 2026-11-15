## ADDED Requirements

### Requirement: Explain names the follow command of the item
The explain command SHALL print the follow command with the number of the item, and MUST send no request for it.

#### Scenario: The output of an item
- **WHEN** A test renders the explanation of one item.
- **THEN** The output holds the follow command followed by the number of the item.
