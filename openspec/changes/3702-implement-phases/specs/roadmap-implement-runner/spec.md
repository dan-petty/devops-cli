## ADDED Requirements

### Requirement: The implement job runs on three phases
`devops roadmap implement --confirm` SHALL take `--phase prepare|agent|publish|all` and `--work <folder>` (#3702). `prepare` and `publish` SHALL hold the App token and run no code of the pull request; `agent` SHALL hold the model key only. `all`, the default, SHALL run the three phases in one process. Each phase SHALL first make the process unreadable to its children.

#### Scenario: All runs the phases in order
- **WHEN** the runner Job runs `roadmap implement --item 1 --confirm`
- **THEN** `prepare`, then `agent`, then `publish` run in one process, and the item reaches the draft

#### Scenario: The phases in separate calls
- **WHEN** `prepare`, `agent` and `publish` run in three calls on one run folder
- **THEN** the item reaches the draft as it does with `all`

#### Scenario: The agent phase with a GitHub token
- **WHEN** `--phase agent` starts in an environment that holds `GH_TOKEN`
- **THEN** the command refuses before it reads the inputs

### Requirement: A network git call of the implement job runs in a folder that no agent wrote
Each git call of the implement job that reaches `origin` SHALL run in a folder that no agent wrote: the new clone of `prepare` in the run folder, before the agent phase, or the new repository of `publish`. Until #3700 these calls SHALL set `CONST_GIT_ISOLATED_CONFIG_ENV` and get the credential helper of `gh` from `-c` values, and `publish` SHALL end every leftover process first. No call with the token SHALL touch the clone of the agent phase.

#### Scenario: Programs that the home folder of the Job names
- **WHEN** a turn of the agent writes into the git configuration of the home folder a hook folder with a `pre-commit`, `post-commit`, `pre-push` and `reference-transaction` hook and a credential helper, each of which writes the `GH_TOKEN` that it sees, and the job runs a Planned item to its pull request
- **THEN** the branch of the item is on `origin`, and no program wrote the session's token

#### Scenario: A credential helper in the clone
- **WHEN** a turn of the agent adds a credential helper and a `pre-push` hook to the configuration of its clone
- **THEN** `publish` pushes from its own repository, and neither program runs

## REMOVED Requirements

### Requirement: A network git call of the implement job reads no file that the agent can write
**Reason**: The implement job makes no network git call in a clone that an agent wrote: `prepare` clones before the agent phase, and `publish` works in a new repository (#3702).
**Migration**: The requirement "A network git call of the implement job runs in a folder that no agent wrote" replaces it.

### Requirement: A refused setting at a checkpoint or stop push stops the item at once
**Reason**: No run makes a checkpoint, and `publish` pushes from its own repository, which holds no setting of the agent (#3702).
**Migration**: None.
