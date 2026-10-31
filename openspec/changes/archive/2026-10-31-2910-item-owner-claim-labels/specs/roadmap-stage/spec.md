# Spec Delta

## ADDED Requirements

### Requirement: The job leaves out an item that an agent or a person claimed
The job SHALL stage no Item that holds `owner/agent` or `owner/human`, `--item` included, and SHALL give the reason "It is claimed by agent." or "It is claimed by human.". An Item that holds `owner/service` SHALL not be left out for its owner.

#### Scenario: A claimed Item
- **WHEN** a Ready Item holds `owner/human` and the filter names it
- **THEN** the plan stages no Item and lists the Item as left out with a reason that contains "claimed by human"

#### Scenario: An agent claimed the named Item
- **WHEN** `--item` names a Ready Item that holds `owner/agent`
- **THEN** the plan lists the Item as left out with a reason that contains "claimed by agent"

#### Scenario: The Service holds the Item
- **WHEN** a Ready Item holds `owner/service`
- **THEN** the job stages it as it does an Item with no owner
