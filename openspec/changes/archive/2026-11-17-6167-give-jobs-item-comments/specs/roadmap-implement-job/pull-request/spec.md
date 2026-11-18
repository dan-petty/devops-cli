## ADDED Requirements

### Requirement: The comment of a run names the comments of the item that the steps read
The comment of a run on the pull request SHALL name, by its page, each comment of the item that the inputs of a step of the run held whole, each once, in the order of the steps. A run whose inputs held no comment SHALL have no such line.

#### Scenario: A comment of the item
- **WHEN** the item has one comment with a known page and the run passes two groups
- **THEN** the comment of the run names the page once, on the line "comments of the item in the step inputs"
