## MODIFIED Requirements

### Requirement: The validation judges the change against the base specs
The job SHALL run the validation in a scratch directory that also holds the base spec of each capability the change has a delta for. Any issue in the report of OpenSpec SHALL count as a problem and SHALL go back to the model once with its text, even for a valid change, such as a delta that `openspec archive` would refuse. The one exception is the INFO note that a change sets `skip_specs`.

#### Scenario: A MODIFIED requirement that the base spec lacks
- **WHEN** the plan modifies a requirement whose name is not in the base spec of an existing capability
- **THEN** the validation reports the refusal and the model gets it as the problem to correct

#### Scenario: A change that sets skip_specs
- **WHEN** OpenSpec reports only the INFO message that `skip_specs` is set
- **THEN** the validation gives no problem

#### Scenario: Another issue next to the skip_specs message
- **WHEN** OpenSpec reports the `skip_specs` message and a second INFO issue
- **THEN** the validation gives a problem that holds the second issue and not the `skip_specs` message

## ADDED Requirements

### Requirement: The stage prompt names a sample file by a bare name
The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` SHALL tell the planner to write a sample file that a test writes at run time, and that no group creates, as a bare name with no folder.

#### Scenario: The prompt holds the bare-name rule
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- **THEN** the text names `test_sample.py` as a bare name and says that a name with a folder is read as a path of the repository
