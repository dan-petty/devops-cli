## MODIFIED Requirements

### Requirement: The repair runs as the phases prepare, agent and publish
With `--confirm`, `devops roadmap step fix-checks` SHALL take `--phase prepare|agent|publish|all`, with `all` by default and `--work` for each other phase. `prepare` SHALL judge the round and clone with git and GitHub calls only, and leave no credential in `work/`. The agent phase SHALL make no GitHub call. `publish` SHALL check the claim, publish the patch, and write the record and the comment of the round.

#### Scenario: The three phases on a run folder
- **WHEN** `prepare`, `agent` and `publish` run one after the other on one run folder for a failed check
- **THEN** the agent phase sends no request, and `publish` returns `repaired` with the new head and records the repair

#### Scenario: A round that prepare ends
- **WHEN** the item holds an owner label
- **THEN** `prepare` gives the report `stopped` and writes no inputs, the agent phase writes nothing, and `publish` gives no second report

#### Scenario: A wait or a ready mark that prepare ends
- **WHEN** `prepare` waits on a CI infrastructure failure, or marks a green draft ready, in separate phases
- **THEN** `prepare` gives the report `wait` or `ready`, and `publish` gives no second report, posts no second comment and marks nothing again

#### Scenario: A state that says ended while a step is due
- **WHEN** the state file says that the round ended, and the round has a repair or a ready mark due
- **THEN** `publish` raises `PhaseOutputError` and pushes nothing

#### Scenario: Prepare on a hostile branch
- **WHEN** `prepare` runs on a head branch with a build hook
- **THEN** it starts only git, and gh for the log of the failed run, and its clone holds no token, no credential helper and no extra header

#### Scenario: The workflow files of the plan
- **WHEN** the merged plan of the item names `.github/workflows/ci.yml`
- **THEN** `publish` reads that file from the merged plan on the default branch, and lets the patch change it and no other workflow file

#### Scenario: A phase of a repair with no run folder
- **WHEN** the command runs `--phase agent` or `--phase publish` with `--confirm` and no `--work`
- **THEN** the command exits 1

## ADDED Requirements

### Requirement: A plan Job on the phases plans in prepare only
Without `--confirm`, `--phase prepare` SHALL run the plan round and print its result line, and `--phase agent` and `--phase publish` SHALL exit 0 with nothing to do, so a Job in mode `plan` on the phases runs (#6690).

#### Scenario: A plan Job on the phases
- **WHEN** each container of a Job in mode `plan`, built from a template on the phases, runs its args
- **THEN** each exits 0, and only `prepare` runs the plan round and prints the result `planned`
