# Spec Delta

## ADDED Requirements

### Requirement: The job leaves out an item that an agent or a person claimed
The job SHALL take no Item that holds `owner/agent` or `owner/human`, `--item` included, and the plan SHALL give the reason "It is claimed by agent." or "It is claimed by human.". An Item that holds `owner/service` SHALL not be left out for its owner.

#### Scenario: A claimed Staged Item
- **WHEN** a Staged Item that the filter names holds `owner/human`
- **THEN** the plan selects no Item and lists the Item as left out with a reason that contains "claimed by human"

#### Scenario: An agent claimed the named Item
- **WHEN** `--item` names an Item that holds `owner/agent`
- **THEN** the plan lists it as left out with a reason that contains "claimed by agent"

#### Scenario: The Service holds the Item
- **WHEN** a Staged Item holds `owner/service`
- **THEN** the plan selects it
