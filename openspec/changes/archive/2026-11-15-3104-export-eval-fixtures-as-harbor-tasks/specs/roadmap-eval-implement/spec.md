## ADDED Requirements

### Requirement: One Harbor task folder for each implement fixture
The exporter SHALL write one Harbor task folder for each fixture under tests/fixtures/roadmap_eval/implement, and each folder SHALL hold an instruction file, an environment Dockerfile, a test script and a task configuration with text in each.

#### Scenario: A fixture becomes a task folder
- **WHEN** The exporter runs on the fixture 2747-env-keys
- **THEN** The output folder holds the four files, and each of the four holds text.

#### Scenario: Every committed fixture gets a folder
- **WHEN** The exporter runs on the 14 fixtures of the committed set
- **THEN** It writes 14 task folders, and each of the four files of each folder holds text.

### Requirement: The instruction holds the issue and the plan
The generated instruction MUST hold the title and the body of the issue of its fixture and the text of the three plan files of that fixture.

#### Scenario: The issue body reaches the instruction
- **WHEN** The exporter writes the task of a fixture whose issue holds a sentence and whose plan holds a proposal, a design and a task list
- **THEN** The instruction holds that sentence and the text of the three plan files.

### Requirement: The task configuration carries the time limit
The generated task configuration MUST carry the time limit that the export command is given, and the documented default when the option is absent.

#### Scenario: A 600 second limit reaches the task configuration
- **WHEN** The exporter runs with a time limit of 600 seconds
- **THEN** The task configuration holds 600 as the time limit of the task.

### Requirement: The test script writes the reward of a trial
The generated test script MUST run the commands of its fixture that name its tests and write the reward of the trial as 1 when they pass and 0 when one fails.

#### Scenario: A passing check writes the reward 1
- **WHEN** The generated test script runs in a task whose test command exits 0
- **THEN** The script writes 1 as the reward, in the file of the task format of the pinned Harbor version.

#### Scenario: A failing check writes the reward 0
- **WHEN** The generated test script runs in a task whose test command exits 1
- **THEN** The script writes 0 as the reward.

### Requirement: An incomplete fixture is refused
The exporter MUST refuse a fixture that lacks a required file or field, and it MUST name the fixture and the field in the error.

#### Scenario: A fixture with no issue text is refused
- **WHEN** The exporter reads a fixture whose issue text is empty
- **THEN** The command exits 1 with an ImplementEvalError of code ROADMAP_EVAL_REFUSED that names the fixture and its issue text.

### Requirement: The trial command passes the trials, the agent and the provider to Harbor
The trial command SHALL pass the trial count, the task folder, the Coder agent, the model and the sandbox provider to the Harbor command line.

#### Scenario: Five trials of one task
- **WHEN** The trial command runs with a trial count of 5, the Coder agent and the Docker provider
- **THEN** The recorded Harbor argv holds the trial count 5, the task folder, the Coder agent and the Docker provider.

### Requirement: The run records the pass rate and the cost
The trial command SHALL write a result file under the data directory with the pass rate, the trial count and the total cost of the trials.

#### Scenario: Four trials, three of them pass
- **WHEN** The trial command reads four trials and three of them hold the reward 1
- **THEN** The result file holds a pass rate of 0.75, a trial count of 4 and the sum of the costs of the four trials.

### Requirement: The Harbor version is pinned
The change MUST pin one Harbor version in pyproject.toml and in uv.lock.

#### Scenario: The dependency files name one Harbor version
- **WHEN** The two dependency files are read
- **THEN** Both files name the same Harbor version.

### Requirement: No test starts Harbor or Docker
Every test of the exporter and of the trial command MUST answer the Harbor command line and the Docker engine through the process seam.

#### Scenario: The trial command runs offline
- **WHEN** The test of the trial command runs with the process fake
- **THEN** No real harbor and no real docker program starts, and the recorded calls hold the argv.

### Requirement: The testing document names both commands
docs/TESTING.md SHALL document the export command and the trial command with its trial count option.

#### Scenario: The testing document names both commands
- **WHEN** docs/TESTING.md is read
- **THEN** It holds the export command and the trial command with its trial count option.
