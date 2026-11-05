## ADDED Requirements

### Requirement: The plan check lists the default tree once for each run
The implement selection SHALL list the files of `origin/<default>` one time for a run, and SHALL give that list to the plan check of every item that the run judges.

#### Scenario: A run over two Planned items
- **WHEN** A run judges two Planned items in one call to `plan_implement`.
- **THEN** The run lists the files of `origin/<default>` one time.

### Requirement: The plan check reads the base specs once for each run
The implement selection SHALL read each base spec file of `origin/<default>` one time for a run, and SHALL find the spec files in the one listing of the default tree.

#### Scenario: Two items need the base specs
- **WHEN** A run judges two items whose plans the check compares with the base specs.
- **THEN** The run reads each base spec file of `origin/<default>` one time.

### Requirement: The plan check lists the branch of each Staged item
The implement selection SHALL list the files of the branch of each Staged item that it judges, because each Staged item has its own branch.

#### Scenario: Two Staged items on two branches
- **WHEN** A run judges two Staged items whose branches differ.
- **THEN** The run lists the files of each of the two branches one time, and lists the default branch one time.

### Requirement: The reads of one run give the same selection as a read for each item
The implement selection SHALL return for each item the target or the left-out reason that a run over that item alone returns.

#### Scenario: Three items in one run
- **WHEN** A run judges a Planned item whose plan passes, a Planned item whose plan holds a placeholder task, and a Staged item whose plan passes.
- **THEN** Each item gets the target or the left-out reason that a run over that item alone gives.

### Requirement: A default tree that git cannot list leaves the items out
The implement selection SHALL leave out each Planned item whose plan check needs the default tree when git cannot list it, with the reason of git, and SHALL end no run.

#### Scenario: Git fails to list the default tree
- **WHEN** A run judges two Planned items and `git ls-tree` of `origin/<default>` fails.
- **THEN** `plan_implement` returns no target, and each item has a left-out reason that says its plan cannot be read from git.
