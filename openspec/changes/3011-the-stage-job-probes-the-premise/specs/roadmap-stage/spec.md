## ADDED Requirements

### Requirement: The job probes the premise at the staging commit
Before the model call, the stage job SHALL probe each path and each identifier that the issue cites at the staging commit, and SHALL put the probe text in the model input under the key `probes`. The job SHALL take the cited items from the same extraction as the context of the model. A missing path SHALL be probed for the commit that deleted or renamed it, and an identifier with no definition for the commit that last added or removed its text.

#### Scenario: Probe output is in the model input
- **WHEN** the job plans an issue that cites a file of the staging commit and a function that the commit defines
- **THEN** the model input holds `probes` with a line that says the file is present and a line that names the definition of the function

#### Scenario: A removed identifier names its removal commit
- **WHEN** the issue cites `validate_url`, which a commit removed from the history before the staging commit
- **THEN** `probes` says that the identifier has no definition and names that commit

#### Scenario: A removed path names its removal commit
- **WHEN** the issue cites a path that a commit deleted
- **THEN** `probes` says that the path is missing and names the commit that deleted it

#### Scenario: A thing that never existed
- **WHEN** the issue cites a path that no commit ever held
- **THEN** `probes` says that the path is missing and that no commit in the history deleted or renamed it

#### Scenario: A backtick text that is no path and no identifier
- **WHEN** the issue holds the backtick texts `git log -S x`, `owner/repo` and the number 0.41
- **THEN** `probes` holds no line for any of them

### Requirement: The probes are bounded and read-only
The probes of one item SHALL run at most 10 git commands. When the issue cites more items than the bound allows, the probe SHALL stop at the bound and list the items it did not probe. Every probe command SHALL be `git cat-file`, `git grep` or `git log`, and no probe SHALL change the checkout.

#### Scenario: The bound stops the probes
- **WHEN** the issue cites 12 paths that the commit holds
- **THEN** the probe runs 10 commands and `probes` lists 2 paths as not probed

#### Scenario: Only reading commands
- **WHEN** the probe runs for an issue that cites a missing path, a missing identifier and a present path
- **THEN** every command it ran is `cat-file`, `grep` or `log`, and `git status --porcelain` of the checkout is empty

### Requirement: A false premise returns the item
When the model reply sets `premise_failed` with evidence, the stage job SHALL comment the evidence on the issue and set its Status to New, as `devops roadmap return` does, and SHALL make no branch and no pull request for the item. The job SHALL ask for no plan from such a reply.

#### Scenario: Replay of #2971
- **WHEN** the job plans an issue that cites `validate_url`, which a commit removed, and the model replies with `premise_failed` and the evidence
- **THEN** the issue gets the evidence as a comment and the Status New, and the repository gets no branch and no pull request

#### Scenario: A plan with a true premise
- **WHEN** the model reply sets no `premise_failed`
- **THEN** the job stages the change as before

#### Scenario: A reply with no plan and no premise_failed
- **WHEN** the model reply sets no `premise_failed` and holds no groups
- **THEN** the reply fails the schema and goes back to the model once

### Requirement: The prompt asks feasibility to quote the probes
The prompt of the stage job SHALL tell the model that `probes` holds the result of read-only commands at the staging commit, SHALL ask `feasibility` to quote the lines of `probes` that confirm the premise, and SHALL tell the model to set `premise_failed` only when the probes or the inputs show that the premise of the issue is false.

#### Scenario: The prompt names the probes
- **WHEN** the stage prompt loads
- **THEN** it names `probes` and `premise_failed`, and asks `feasibility` to quote the probes

## MODIFIED Requirements

### Requirement: Each item of a stage round counts once by its result
A stage round, whether the Service or the command runs it, SHALL add 1 to `devops_cli_roadmap_stage_total` for each item it handled, with the label `result`: `staged` for an item written as a branch and a draft, `needs_split` for an item stopped on a group over the budget, `returned` for an item returned to New on a false premise, `failed` for an item that failed in the plan or in the writes, and `skipped` for an item the job left out with a reason. An item SHALL count under one result.

#### Scenario: Four results in one round
- **WHEN** a round stages one item, stops one on the budget, fails one in the model call, and leaves one out for an open dependency
- **THEN** the counter has one point each for `staged`, `needs_split`, `failed` and `skipped`

#### Scenario: A returned item
- **WHEN** a round returns one item to New on a false premise, besides the four items above
- **THEN** the counter also has one point for `returned`, and each item counts under one result

#### Scenario: A plan with no write
- **WHEN** `devops roadmap stage --plan` runs
- **THEN** the counter has no point
