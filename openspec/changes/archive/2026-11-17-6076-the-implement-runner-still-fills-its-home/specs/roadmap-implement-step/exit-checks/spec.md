## ADDED Requirements

### Requirement: The end of a step removes the by-products of its agent
When a step ends, done, stopped or with an error, it SHALL remove the directory `mutants/` of the checkout and SHALL empty `.data/agent/scratch/`, after the reset of a step that is not done and after the disk use line of a runner Job. git ignores both, so neither the commit nor the reset of the step removes them.

#### Scenario: A step that ends done
- **WHEN** the model writes `.data/agent/scratch/probe_mutation.py` and `mutants/src/sample.py`, and every exit check passes
- **THEN** the step ends done, the checkout has no `mutants/`, and `.data/agent/scratch/` is an empty directory

#### Scenario: A step that stops
- **WHEN** the model writes the same files, and the verification of its task fails
- **THEN** the step stops, the checkout has no `mutants/`, and `.data/agent/scratch/` is an empty directory

#### Scenario: The line names the by-products
- **WHEN** a step ends in a runner Job with files in `mutants/` and `.data/agent/scratch/`
- **THEN** du reads them before the step removes them, and the line names `worktree/mutants`

## MODIFIED Requirements

### Requirement: A step removes the stray files of the agent
Before the exit checks stage the checkout, and again after the extra turn, the step SHALL unstage and delete each stray file and SHALL give it to no tool. A stray file is an untracked or added file that git does not ignore, a nested git repository, or a file that the group does not allow.

#### Scenario: A scratch file in the root
- **WHEN** the model writes `tmp_test_x.py` with an unused import in the checkout root, writes the files of the group, ticks the tasks, and ends its run
- **THEN** the step reports done, the file is not in the tree or in the commit, no tool got its name, and `removed` lists `tmp_test_x.py`

#### Scenario: A new test file in the directory of the group
- **WHEN** the model writes `tests/test_sample_more.py` next to the named `tests/test_sample.py`
- **THEN** the step keeps the file, and the commit holds it

#### Scenario: A file of the project directories that the plan does not list
- **WHEN** the model writes `tests/data.json`, `tests/conftest.py` and `src/helper.py`, which the group does not name
- **THEN** the step keeps the files, ends done, and the commit holds them

#### Scenario: A nested git repository
- **WHEN** the model runs `git init sub` and writes `sub/a.txt`
- **THEN** the step removes `sub/` with its files, lists `sub/` in `removed`, and ends done

#### Scenario: A fix step
- **WHEN** a fix step runs and the model writes a new file outside `src/`, `tests/`, `docs/` and `openspec/`
- **THEN** the step deletes the file

#### Scenario: A fix step with a new test file
- **WHEN** a fix step runs and the model writes a new file under `tests/` that the plan names
- **THEN** the step keeps the file and stages it

#### Scenario: A staged stray file
- **WHEN** the agent stages a new file outside `src/`, `tests/`, `docs/` and `openspec/` with `git add`
- **THEN** the step unstages the file and deletes it, in a group step and in a fix step

#### Scenario: A staged rename into a stray name
- **WHEN** the agent renames `src/other.py` to `tmp_test_x.py` with `git mv`
- **THEN** the step unstages and deletes `tmp_test_x.py`, and puts back `src/other.py`, so that the commit and the work in progress keep the file

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
- **THEN** the step does not list it as a stray file, and the commit holds no such file

#### Scenario: The paths that a group allows
- **WHEN** the group names a path in a code span, and the model writes files under its change folder, under `src/`, `tests/`, `docs/` or `openspec/`, and at the named path
- **THEN** the step keeps those files, and it names each removed file in the Job log, in `StepOutcome.removed` and in the extra turn
