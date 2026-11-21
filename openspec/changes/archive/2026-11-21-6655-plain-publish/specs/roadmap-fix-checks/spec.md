## MODIFIED Requirements

### Requirement: The command repairs a failed check in a runner Job
With `--confirm`, `devops roadmap step fix-checks` SHALL refuse to run outside a runner Job. In a runner Job it SHALL give the step a plain clone in the run folder on the head branch, the tier 1 fixers, and the model fix of `ai.tasks.fix_checks`. `publish` SHALL push the patch as one commit of the bot with a lease on the judged head, and return `repaired` with the new head.

#### Scenario: A failed check whose log names a file of the plan ends repaired
- **WHEN** the command runs with `--confirm` on a bot pull request whose `Static Analysis` check failed with a log that names a file of the plan, and the model fix commits a change
- **THEN** the step returns `repaired`, and the head branch on `origin` has one new commit

#### Scenario: The command refuses to repair outside a runner Job
- **WHEN** the command runs with `--confirm` in a process that is not a runner Job
- **THEN** the command exits 1 and reads no pull request

#### Scenario: A push whose lease breaks is refused
- **WHEN** another writer moves the head branch on `origin` after the judgment and before the push
- **THEN** the push fails, the commit of the other writer stays, and the step records no repair

#### Scenario: The checkout refuses another branch or another head
- **WHEN** `origin` holds no head branch of the pull request, or its tip is not the judged head
- **THEN** the checkout raises an error before any fixer runs

### Requirement: Publish builds the target of its push from GitHub
`publish` SHALL check the state of `prepare` against the live pull request: the repository, the pull request, the head branch, the item and the judged head. It SHALL push to the live head branch of the repository on GitHub with a lease on the judged head, as the bot, with the workflow files that it reads from the merged plan. The state file SHALL name no URL. A separate `publish` SHALL take the check from the failed checks of the judged head.

#### Scenario: A fixer that rewrites the state file in one process
- **WHEN** a fixer of `--phase all` writes another branch, author and workflow rule over the state file of its run
- **THEN** `publish` pushes to the head branch of the pull request as the bot, with the workflow files of the merged plan

#### Scenario: A state file with another branch between separate phases
- **WHEN** the state file names a head branch other than the head branch of the pull request
- **THEN** `publish` returns `stopped` and pushes nothing

#### Scenario: A fixer that rewrites the origin of the clone
- **WHEN** a fixer sets `remote.origin.url` of the clone to another repository, with `--phase all` or with separate phases
- **THEN** `publish` fetches from and pushes to the repository on GitHub, and no git call names the other repository

#### Scenario: A clone with another origin
- **WHEN** `prepare` makes its clone
- **THEN** it clones the repository on GitHub into the run folder, and the step reads the origin of no other clone

#### Scenario: A separate publish with another origin
- **WHEN** the state file names a URL
- **THEN** `publish` raises `PhaseOutputError` and pushes nothing

#### Scenario: A check that the state file forges
- **WHEN** the state file names a check that is no failed check of the judged head
- **THEN** `publish` returns `skipped` and pushes nothing

#### Scenario: A hostile name of a check
- **WHEN** the failed check has a name with a newline, a handle and a link
- **THEN** the commit message holds the name on one line, and the comment shows the handle and the link in code spans

#### Scenario: A state file that is not the state of prepare
- **WHEN** the state file is a link to `/proc/self/environ`, holds a key outside its model or text that is not JSON, or names another pull request
- **THEN** `publish` raises `PhaseOutputError`, pushes nothing, and its message holds no text of the file
