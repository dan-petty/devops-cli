## ADDED Requirements

### Requirement: The inbox lists each item whose stage job failed
`read_inbox` SHALL return one `stage_retry` line for each open item whose job record holds `stage.failed_class`. The subject of the line SHALL name the failure class, and its clearing step SHALL name `devops roadmap stage --item` with the number of the item and the repository, which takes the item at once.

#### Scenario: An item with a stage failure class
- **WHEN** A fake repository holds an open item whose job record holds `stage.failed_class` with the value `limit_reached`
- **THEN** The inbox holds one line of the class `stage_retry`, whose subject names `limit_reached` and whose clearing step names `devops roadmap stage --item` with the number of the item

#### Scenario: An item with no stage failure class
- **WHEN** A fake repository holds an open item whose job record holds no `stage.failed_class`
- **THEN** The inbox holds no line of the class `stage_retry`
