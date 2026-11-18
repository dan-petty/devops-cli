## ADDED Requirements

### Requirement: Plan-recheck processes the open plan branches
With the option `--branches`, plan-recheck SHALL read each open draft plan pull request whose base is the default branch, judge the change folder of its head with the same reader, gates and OpenSpec check as the default branch, and call no model.

#### Scenario: Each open plan branch is judged
- **WHEN** a person runs `devops roadmap plan-recheck --branches`
- **THEN** the run reads each open draft plan pull request whose base is the default branch and gives it one result.

#### Scenario: A delivery branch is left out
- **WHEN** an open pull request holds the body of a delivery and no plan line
- **THEN** the run leaves it out and gives it no result.

### Requirement: A branch is rebased only to apply a rewrite
Plan-recheck SHALL rebase an open plan branch onto the default branch only when the mechanical rewrite changes a file of its change folder. A branch whose plan the rewrite does not change SHALL get no rebase and no push.

#### Scenario: Only the base moved
- **WHEN** the default branch moved and the rewrite changes no file of the open plan branch
- **THEN** the run pushes nothing and the head of the branch on `origin` stays the same.

#### Scenario: A rewrite rebases the branch
- **WHEN** the rewrite changes a file of the change folder of the branch
- **THEN** the run rebases the branch onto the default branch in a temporary worktree before it writes the rewrite.

### Requirement: Plan-recheck pushes a rewritten branch once with a lease
Plan-recheck SHALL commit the rewritten files of an open plan branch and push the commit exactly once with `--force-with-lease` on the head that it read. The push SHALL start the checks of the pull request through the push event.

#### Scenario: Exactly one push
- **WHEN** the rewrite changes a file of the change folder of the branch and the plan passes every check
- **THEN** the run pushes exactly one commit and the branch on `origin` holds it.

### Requirement: A conflict leaves the open plan branch unchanged
Plan-recheck MUST abort the rebase and push nothing when the open plan branch conflicts with the default branch. It SHALL record the conflict reason and leave the pull request as it is.

#### Scenario: A conflicting branch
- **WHEN** the rebase of the open plan branch conflicts with the default branch
- **THEN** the run aborts the rebase, pushes nothing and records the conflict reason.

### Requirement: A rewrite that fails a check is not pushed
Plan-recheck MUST validate the rewritten plan of the rebased branch with the plan reader, the gates and the OpenSpec check before it commits. A rewritten plan that fails one SHALL leave the branch unchanged, and the run SHALL report the refusal.

#### Scenario: A refused rewrite
- **WHEN** the rewritten plan of the rebased branch fails a gate
- **THEN** the run commits nothing, pushes nothing and reports the gate.

## MODIFIED Requirements

### Requirement: Plan-recheck writes nothing
The command SHALL write no file, make no commit and push nothing when `--confirm` is absent. With `--confirm` it SHALL write the rewritten files of the folders with the result `rewrite` to the working tree of the checkout that `--source` names, and with `--branches` it SHALL commit and push the rewritten plan branch of each open plan pull request. It SHALL call no model.

#### Scenario: A dry run
- **WHEN** a person runs `devops roadmap plan-recheck --dry-run`
- **THEN** the command prints the reads of a run and makes no request.

#### Scenario: A run without confirm
- **WHEN** a person runs `devops roadmap plan-recheck` on a plan that the rewrite changes
- **THEN** the report shows `rewrite` and the working tree holds no changed file.

#### Scenario: A run with confirm
- **WHEN** a person runs `devops roadmap plan-recheck --confirm --source <checkout>` on a plan that the rewrite changes
- **THEN** the files of the folder in the checkout hold the rewritten text, and `git status` shows them as changed and not committed.
