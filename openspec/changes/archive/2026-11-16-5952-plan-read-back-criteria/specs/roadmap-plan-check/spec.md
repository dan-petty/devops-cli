## ADDED Requirements

### Requirement: The documents command is no mark of the reader
The command of the documents step (`uv run devops docs generate`) SHALL be no mark of the reader in the work of a group or in its documents work. The reader SHALL cut the step only from the end of a documents task of a group that changes a command, an option or a message.

#### Scenario: A work that names the documents command
- **WHEN** a `behavior` group with a documents task has the work "Add the series to the metric table, and run `uv run devops docs generate` to write `docs/TELEMETRY.md` again"
- **THEN** `read_back_problems` gives no problem for the group

#### Scenario: A documents work that names the documents command
- **WHEN** an `other` group that changes only `docs/TELEMETRY.md` has a documents work that ends with ", and run `uv run devops docs generate`"
- **THEN** the reader gives the documents work with that end

### Requirement: A read-back difference names its first place and both values
`read_back_differences(files, proposal)` SHALL give, for each fact that `read_back_problems` names, the place of its first difference (an entry index, a field name, a character index) and the value of `file_facts` and the read value there. Each value SHALL be its `repr`, masked with `mask_secrets` and cut to 200 characters. A text value SHALL start 40 characters before its first differing character.

#### Scenario: A reason that the line drops
- **WHEN** the second criterion of `file_facts` has the reason `""` and the read criterion has none
- **THEN** the difference has the fact `criteria`, the place `[1].reason`, the written value `''` and the read value `None`

#### Scenario: A secret in a value
- **WHEN** a differing value holds a GitHub token and 1,000 more characters
- **THEN** the value of the difference holds no token and at most 200 characters

### Requirement: The stage job logs each read-back difference
The stage job SHALL log one line for each read-back difference with the item, the fact, the place and the two values, and SHALL put the differences in the details of `RoadmapPlanReadBackError`. The message of the error SHALL name only the facts.

#### Scenario: The Job log of a difference
- **WHEN** the stage job reads back the plan of item 3671 with a difference in `criteria`
- **THEN** the Job log holds `stage plan read-back difference: item=#3671 fact=criteria place=[1].reason written='' read=None`, and the message of the error is `criteria`
