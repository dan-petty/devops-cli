## ADDED Requirements

### Requirement: The base replay of a step runs the pytest of the checkout
The base replay of a behavior group SHALL run the pytest of `<checkout>/.venv/bin/python` by its absolute path. The replay names its interpreter and does not read PATH, the image venv holds no pytest, and the replay runs in the folder of the base tree.

#### Scenario: The base replay of a behavior group
- **WHEN** a step replays the test files of a behavior group on its base commit
- **THEN** the replay starts `<checkout>/.venv/bin/python -m pytest`

#### Scenario: A step in the current folder
- **WHEN** a person runs a step with no `--source`, so the checkout is `.`
- **THEN** the replay starts the absolute path of `.venv/bin/python` of the current folder

## MODIFIED Requirements

### Requirement: The agent and the checks of a Job find the tools of the checkout first
The shell of the agent of a step, the `pre-commit` runs, the scoped checks, the exit checks of a step other than the base replay, the project programs of the implement Job and the tier-1 commands of fix-checks SHALL get a PATH that starts with `<checkout>/node_modules/.bin` and `<checkout>/.venv/bin`, then the PATH of the Job process. The Job process and each child that gets a token SHALL keep the PATH of the image.

#### Scenario: The checks of the implement Job
- **WHEN** the implement Job runs the `pre-commit` stage, the `pre-push` stage and the static scoped check
- **THEN** the PATH of each child starts with `node_modules/.bin` and `.venv/bin` of the worktree

#### Scenario: The shell of the agent
- **WHEN** a step builds the shell of its agent for a checkout
- **THEN** the PATH of the shell starts with `node_modules/.bin` and `.venv/bin` of that checkout
