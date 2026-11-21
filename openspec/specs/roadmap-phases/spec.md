# roadmap-phases Specification

## Purpose
A roadmap step that runs an agent splits its run into three phases, so the agent never runs next to the App key (#2695, #3702): `prepare` and `publish` hold the App key and run no agent code, and the agent phase holds the model key only. This capability holds the run folder, the patch of the agent phase and the publish of the patch, which fix-checks uses now and stage uses later (#6528).

## Requirements

### Requirement: Publish reads an output of the agent phase as data
`publish` SHALL read the state file and each output of the agent phase only when the root of the run and the folder of the file are plain folders, the file opens with `O_NOFOLLOW | O_NONBLOCK`, `fstat` shows a regular file and the size is within the limit. Each other case SHALL raise `PhaseOutputError`. An outcome or a summary with a key outside its model SHALL raise it too.

#### Scenario: A link to the environment
- **WHEN** `out/outcome.json` is a link to `/proc/self/environ`
- **THEN** the read raises `PhaseOutputError`

#### Scenario: A FIFO, a large file or a linked folder
- **WHEN** the output is a FIFO, holds more bytes than the limit, or `out/` is a link to another folder
- **THEN** the read raises `PhaseOutputError`

#### Scenario: A key outside the model
- **WHEN** `outcome.json` holds a key that the model does not name
- **THEN** the read raises `PhaseOutputError`

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

### Requirement: Prepare clones the issue branch plainly
`prepare` SHALL make a full clone of the repository on GitHub in the work folder of the run, which is new to the run, before any code of the pull request runs, and switch to the issue branch: the pushed branch, after the check that the App wrote each commit past the default branch, or a new branch at the tip of the default branch. It SHALL record the tip of the default branch and the lease: the tip of the pushed branch, or empty for a new branch.

#### Scenario: A pushed branch
- **WHEN** `origin` holds the branch of the item with a commit of the App
- **THEN** the clone is on that branch, and the lease is its tip

#### Scenario: A new branch
- **WHEN** `origin` holds no branch of the item
- **THEN** the clone is on a new branch at the tip of the default branch, and the lease is empty

#### Scenario: A commit of a person
- **WHEN** the pushed branch holds a commit of a person
- **THEN** `prepare` refuses the branch and names the author

### Requirement: The patch of the agent phase has a fixed format
The agent phase SHALL write each patch with `git diff --binary --full-index --no-color --no-ext-diff --no-textconv --src-prefix=a/ --dst-prefix=b/`, from the base to a commit, or after `git add -A` from the base to every file of the checkout. It SHALL check the exit status of git. No diff setting of the clone or of the home folder SHALL change the patch.

#### Scenario: A commit, a new file and diff settings
- **WHEN** a fixer committed a file, another file is new, and the clone sets `diff.external`, `diff.noprefix` and `color.ui=always`
- **THEN** the patch holds both files, has no color, and applies in a new clone

#### Scenario: A patch up to a commit
- **WHEN** the patch ends at a commit and the checkout holds a later file
- **THEN** the patch holds no later file
