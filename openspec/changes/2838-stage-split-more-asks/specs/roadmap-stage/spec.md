## MODIFIED Requirements

### Requirement: The job measures each task group
The job SHALL measure each task group with tiktoken. The measure SHALL be the tokens of the group's instructions, the item, the change folder and the group's named files, each file packed as the implement step packs it: at most `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens. The budget SHALL be `roadmap.stage.step_tokens`, default 40000, and `--step-tokens` SHALL override it for one run.

#### Scenario: A group is measured
- **WHEN** the model gives a group that names a file of the repository
- **THEN** the comment on the issue gives the group's measure, and that measure is more than the tokens of the file packed

#### Scenario: A large file counts as the step reads it
- **WHEN** a group names a file of 60000 tokens and the budget is 40000
- **THEN** the group measure is under the budget, and the job asks the model for no split
