## MODIFIED Requirements

### Requirement: Publish applies the patch as one commit of the bot
`publish_patch` SHALL fetch the base at depth 1 into a new repository. For each patch it SHALL run `git apply --index`, refuse a new or changed link or gitlink, a change of `.gitmodules` and a workflow file that the plan does not name, and commit as the bot. It SHALL give the new tree to the claim check, push nothing when the lease holds that tree, and else push `HEAD` with `--force-with-lease` on the old tip.

#### Scenario: One commit of the bot
- **WHEN** `publish_patch` gets a patch that changes a file
- **THEN** the branch on `origin` has one new commit on the base, with the bot as author and committer

#### Scenario: An author line in the patch
- **WHEN** the patch starts with a `From:` line of another person
- **THEN** the author of the commit is the bot

#### Scenario: A hostile patch
- **WHEN** the patch adds a link, a gitlink, `.gitmodules`, a path in `.git` or a workflow file that the plan does not name
- **THEN** `publish_patch` raises `PublishRefusedError` and pushes nothing

#### Scenario: A changed link
- **WHEN** the patch points a link of the base at another file, makes a file of the base a link, or makes a link of the base a file
- **THEN** `publish_patch` raises `PublishRefusedError` and pushes nothing

#### Scenario: A workflow file that the plan names
- **WHEN** the patch changes a workflow file that the merged plan names
- **THEN** the commit holds the change

#### Scenario: A branch that moved
- **WHEN** another writer moved the branch after the lease was read
- **THEN** `publish_patch` raises `GitOperationError`, and the commit of the other writer stays

#### Scenario: A claim before the push
- **WHEN** the claim check raises
- **THEN** nothing is pushed

#### Scenario: Two patches on another base
- **WHEN** `publish_patch` gets two patches on a base other than the old tip
- **THEN** the branch on `origin` holds two commits of the bot on the base, in that order

#### Scenario: A new branch that exists
- **WHEN** the lease is empty and `origin` holds the branch
- **THEN** `publish_patch` raises `GitOperationError`, and the branch stays

#### Scenario: A second publish
- **WHEN** the lease holds the new tree already
- **THEN** `publish_patch` gives the lease back and pushes nothing
