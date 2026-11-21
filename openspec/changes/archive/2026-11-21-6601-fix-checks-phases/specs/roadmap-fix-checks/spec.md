## ADDED Requirements

### Requirement: The repair runs as the phases prepare, agent and publish
With `--confirm`, `devops roadmap step fix-checks` SHALL take `--phase prepare|agent|publish|all`, with `all` by default and `--work` for each other phase. `prepare` SHALL judge the round and clone with git and GitHub calls only, and leave no credential in `work/`. The agent phase SHALL make no GitHub call. `publish` SHALL check the claim, publish the patch, and write the record and the comment of the round.

#### Scenario: The three phases on a run folder
- **WHEN** `prepare`, `agent` and `publish` run one after the other on one run folder for a failed check
- **THEN** the agent phase sends no request, and `publish` returns `repaired` with the new head and records the repair

#### Scenario: A round that prepare ends
- **WHEN** the item holds an owner label
- **THEN** `prepare` writes the report and no inputs, the agent phase writes nothing, and `publish` returns `stopped`

#### Scenario: Prepare on a hostile branch
- **WHEN** `prepare` runs on a head branch with a build hook
- **THEN** it starts only git, and gh for the log of the failed run, and its clone holds no token, no credential helper and no extra header

#### Scenario: The workflow files of the plan
- **WHEN** the merged plan of the item names `.github/workflows/ci.yml`
- **THEN** the state file of `prepare` names that file

#### Scenario: A phase with no run folder
- **WHEN** the command runs `--phase agent` with no `--confirm`, or `--phase publish` with no `--work`
- **THEN** the command exits 1

### Requirement: Publish checks the claim before the push
`publish` SHALL run `check_preconditions` on the pull request and the item as GitHub holds them at its start and again right before the push. A round that the check stops SHALL push nothing and write no record.

#### Scenario: A claim after the agent phase
- **WHEN** an owner label appears on the pull request after the agent phase, before `publish` starts or before its push
- **THEN** `publish` returns `stopped` with the reason, pushes nothing and writes no record

### Requirement: Publish takes only the enums of the outcome
`publish` SHALL take the result and the tier of `outcome.json` from the enums of the step only: `repaired` with a tier, or `failed` or `stopped` with none. Each other outcome SHALL raise `PhaseOutputError` and push nothing. The reason of the agent SHALL reach the report masked and on one line.

#### Scenario: An outcome outside the enums
- **WHEN** `outcome.json` names the result `ready`, names `repaired` with no tier, or holds a key outside the model
- **THEN** `publish` raises `PhaseOutputError` and pushes nothing

## MODIFIED Requirements

### Requirement: The command repairs a failed check in a runner Job
With `--confirm`, `devops roadmap step fix-checks` SHALL refuse to run outside a runner Job. In a runner Job it SHALL give the step a worktree on the head branch of the pull request in the run folder, the tier 1 fixers, and the model fix on the task `ai.tasks.fix_checks`. `publish` SHALL push the patch of the fixers as one commit of the bot to the head branch with a lease on the judged head, and SHALL return `repaired` with the new head.

#### Scenario: A failed check whose log names a file of the plan ends repaired
- **WHEN** the command runs with `--confirm` on a bot pull request whose `Static Analysis` check failed with a log that names a file of the plan, and the model fix commits a change
- **THEN** the step returns `repaired`, and the head branch on `origin` has one new commit

#### Scenario: The command refuses to repair outside a runner Job
- **WHEN** the command runs with `--confirm` in a process that is not a runner Job
- **THEN** the command exits 1 and reads no pull request

#### Scenario: A push whose lease breaks is refused
- **WHEN** another writer moves the head branch on `origin` after the judgment and before the push
- **THEN** the push fails, the commit of the other writer stays, the step records no repair, and the worktree goes

#### Scenario: The checkout refuses another branch or another head
- **WHEN** the branch of the item is not the head branch of the pull request, or its tip is not the judged head
- **THEN** the checkout raises an error before any fixer runs, and its worktree and local branch go

### Requirement: A comment names the files of a pushed repair
After the push of a repair, the step SHALL upsert its marked comment for the check. The comment SHALL name each file of the commit of tier 1, or each failed file outside the plan that the model fix could change, with its reason, masked and in a fenced block.

#### Scenario: Tier 1 names the files that it wrote
- **WHEN** tier 1 writes `docs/MCP_TOOLS.md` and a snapshot again and pushes the repair
- **THEN** the comment of the step names both files

#### Scenario: Tier 2 names the files that the change causes
- **WHEN** the model fix repairs a caller outside the plan and the step pushes the repair
- **THEN** the comment of the step names the file and the changed name that it uses

### Requirement: The Job makes its process unreadable before the repair
With `--confirm` in a runner Job, each phase of `devops roadmap step fix-checks` SHALL clear the dumpable flag of its own process and adopt the orphans of a step first, before the runner check and before it reads a file of the run. A kernel that refuses either call SHALL stop the command before the step.

#### Scenario: A confirmed round hardens its process first
- **WHEN** the command runs with `--confirm` in a runner Job, with each value of `--phase`
- **THEN** it calls `deny_environment_reads`, then `adopt_orphans`, then the runner check, and only then the phase
