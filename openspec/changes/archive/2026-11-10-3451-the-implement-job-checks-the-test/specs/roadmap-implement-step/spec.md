## ADDED Requirements

### Requirement: A step reads the test form that a task names
The implement step SHALL read the test file and the case count that each task of its group names, and SHALL compare that count with the number of items that a pytest collection reports for the file.

#### Scenario: A task names one parametrized test over six statuses
- **WHEN** a task of the group names a test file and one parametrized test over six statuses
- **THEN** the step reads the path and the count 6 and collects the items of that file.

#### Scenario: A task names no test form
- **WHEN** no task of the group names a parametrized test
- **THEN** the step runs no form check and ticks the tasks of the group when its exit checks pass.

### Requirement: A step refuses a test that does not match the form of its task
The implement step SHALL refuse a test whose collected item count differs from the count that its task names, and SHALL refuse a named parametrized test that the collection reports as one item. The step MUST keep such a task unticked.

#### Scenario: Eleven collected items for six named cases
- **WHEN** the task names six cases and the collection reports eleven items
- **THEN** the step stops the group, keeps its tasks unticked, and names the count 6 and the count 11 in its reason.

#### Scenario: One collected item for a named parametrized test
- **WHEN** the task names a parametrized test and the collection reports one item
- **THEN** the step stops the group and asks for one parametrized item for each case.

#### Scenario: A repair turn follows the first refusal
- **WHEN** the form check refuses the test and a repair round is left
- **THEN** the step runs one repair turn that may change the named test file, and checks the form again.

### Requirement: A step records the form check in its trace
The implement step SHALL record one check event for each test-form check, and the event SHALL name the test file, the named count, the collected count and the result.

#### Scenario: The trace holds the form check
- **WHEN** the step checks a test that a task names
- **THEN** the trace holds a check event with the test file and the named and collected counts.

#### Scenario: A task names no count
- **WHEN** the task names a parametrized test with no case count
- **THEN** the check event names the test file and the collected count and records the result.
