## ADDED Requirements

### Requirement: A step removes the stray files of the agent
Before the exit checks stage the checkout, and again after the extra turn, the step SHALL delete each stray file and SHALL give it to no tool. A stray file is an untracked file, not ignored by git, that the group does not allow. The group allows a path that it names in a code span, a file under its change folder, and a new test file in the directory of a test file that it names. The step SHALL write the names to the Job log and to `StepOutcome.removed`, and SHALL name them in the extra turn.

#### Scenario: A scratch file in the root
- **WHEN** the model writes `tmp_test_x.py` with an unused import in the checkout root, writes the files of the group, ticks the tasks, and ends its run
- **THEN** the step reports done, the file is not in the tree or in the commit, no tool got its name, and `removed` lists `tmp_test_x.py`

#### Scenario: A new test file in the directory of the group
- **WHEN** the model writes `tests/test_sample_more.py` next to the named `tests/test_sample.py`
- **THEN** the step keeps the file, and the commit holds it

#### Scenario: A fix step
- **WHEN** a fix step runs and the model writes a new file
- **THEN** the step does not delete the file

#### Scenario: A file in a directory that the group does not name
- **WHEN** the model writes `scripts/probe.py`, which the group does not name
- **THEN** the step deletes the file

#### Scenario: The agent is told
- **WHEN** a scratch file was removed and `ruff check` fails on a file of the group
- **THEN** the message of the extra turn names the removed file and says that the group does not name it

#### Scenario: A stray file in the extra turn
- **WHEN** the model writes a scratch file in the extra turn
- **THEN** the step deletes it, and does not stop for a file that it had not changed

#### Scenario: An ignored file
- **WHEN** the model writes a file under `.data/agent/scratch/`
- **THEN** the step does not list it, deletes nothing, and the commit holds no such file
