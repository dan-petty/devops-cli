## Purpose
A roadmap step that runs an agent splits its run into three phases, so the agent never runs next to the App key (#2695, #3702): `prepare` and `publish` hold the App key and run no agent code, and the agent phase holds the model key only. This capability holds the run folder, the patch of the agent phase and the publish of the patch, which fix-checks uses now and stage uses later (#6528).

## ADDED Requirements

### Requirement: Publish reads an output of the agent phase as data
`publish` SHALL read each output of the agent phase only when the root of the run and `out/` are plain folders, the file opens with `O_NOFOLLOW | O_NONBLOCK`, `fstat` shows a regular file and the size is within the limit. Each other case SHALL raise `PhaseOutputError`. An outcome or a summary with a key outside its model SHALL raise it too.

#### Scenario: A link to the environment
- **WHEN** `out/outcome.json` is a link to `/proc/self/environ`
- **THEN** the read raises `PhaseOutputError`

#### Scenario: A FIFO, a large file or a linked folder
- **WHEN** the output is a FIFO, holds more bytes than the limit, or `out/` is a link to another folder
- **THEN** the read raises `PhaseOutputError`

#### Scenario: A key outside the model
- **WHEN** `outcome.json` holds a key that the model does not name
- **THEN** the read raises `PhaseOutputError`

### Requirement: The patch of the agent phase comes from a new git folder
The agent phase SHALL write its patch from a new git folder on the objects of the clone, with its own index and configuration and no global or system configuration: `git add -A` over the tree of the base, then a binary diff from the base. No clean filter, hook or `core.fsmonitor` of the clone SHALL run.

#### Scenario: A commit, a new file and a clean filter
- **WHEN** a fixer committed a file, another file is new, and the clone defines a clean filter for it
- **THEN** the patch holds both files, it applies to the base, and the filter does not run

### Requirement: Publish applies the patch as one commit of the bot
`publish_patch` SHALL fetch the head branch at depth 1 into a fresh clone and refuse a tip other than the lease. It SHALL apply the patch with `git apply --cached` in a new git folder, refuse a new or changed link or gitlink, a change of `.gitmodules` and a workflow file that the plan does not name, write one commit with the bot as author, call the claim check, and push with a lease on the old tip.

#### Scenario: One commit of the bot
- **WHEN** `publish_patch` gets a patch that changes a file
- **THEN** the branch on `origin` has one new commit on the judged head, with the bot as author and committer

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
- **WHEN** another writer moved the branch after the judgment
- **THEN** `publish_patch` raises `GitOperationError`, and the commit of the other writer stays

#### Scenario: A claim before the push
- **WHEN** the claim check raises
- **THEN** nothing is pushed
