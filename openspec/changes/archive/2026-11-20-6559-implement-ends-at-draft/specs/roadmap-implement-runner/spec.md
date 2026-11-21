## ADDED Requirements

### Requirement: A refused setting at a checkpoint or stop push stops the item at once
A refused setting at the push of a checkpoint SHALL stop the item with the class `git_config` at once, before the job writes a record of the push. A refused setting at the push of a stop SHALL give the stop the class `git_config`.

#### Scenario: A setting before a checkpoint push
- **WHEN** the agent writes `credential.helper` into the configuration of the clone in group 1 of a change of four groups, and group 1 passes
- **THEN** the checkpoint before group 2 stops the item with the class `git_config`, and the job asks the model for nothing more

#### Scenario: A setting that an exit check writes
- **WHEN** an exit check of the step writes `credential.helper` into the configuration of the clone and fails, and no repair round is left
- **THEN** the item stops with the class `git_config`, and the comment names `credential.helper` and holds no value

## REMOVED Requirements

### Requirement: A refused setting at a push stops the item at once
**Reason**: The implement Job makes no work-in-progress commit and no work-in-progress push (#6559).
**Migration**: The requirement "A refused setting at a checkpoint or stop push stops the item at once" holds the rule.
