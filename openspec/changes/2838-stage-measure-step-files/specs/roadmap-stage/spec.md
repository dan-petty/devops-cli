## MODIFIED Requirements

### Requirement: The job measures each task group
The job SHALL measure each task group with tiktoken. The measure SHALL be the tokens of the group's instructions, the item, the change folder and the files that the tasks of the group name in code spans, each packed as the implement step packs it: at most `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens. The budget SHALL be `roadmap.stage.step_tokens`, default 40000, and `--step-tokens` SHALL override it for one run.

#### Scenario: A group is measured
- **WHEN** the model gives a group whose task names a file of the repository
- **THEN** the comment on the issue gives the group's measure, and that measure is more than the tokens of the file packed

#### Scenario: A large file counts as the step reads it
- **WHEN** a task of a group names one file that holds more tokens than the budget
- **THEN** the group measure is under the budget, and the job asks the model for no split

#### Scenario: A file that no task names
- **WHEN** the `Reads:` line of a group lists a file that no task of the group names
- **THEN** the file adds no token to the measure, as the step does not read it

## ADDED Requirements

### Requirement: A stop record counts only for the measure that made it
The job SHALL record `stage.file_cap`, the file cap of the measure, with `stage.needs_split`. The job SHALL leave an item out for a recorded split only when `stage.file_cap` is the file cap of now. The job SHALL clear `stage.file_cap` when it stages the item.

#### Scenario: A record of an earlier measure
- **WHEN** the record of an item holds `stage.needs_split` and no `stage.file_cap`, or another one
- **THEN** the job does not leave the item out for the record

#### Scenario: A record of the measure of now
- **WHEN** the record of an item holds `stage.needs_split` and the `stage.file_cap` of now
- **THEN** the plan leaves the item out and says why, and `--item` stages it
