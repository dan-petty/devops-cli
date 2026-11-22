# roadmap-fix-conflict Specification

## Purpose
How the roadmap step `fix-conflict` settles merge conflicts on topic branches of bot pull requests: admission bounds, tier 1 deterministic resolution, verification, and runner job integration.

## Requirements

### Requirement: The step admits only bot pull requests and enforces bounds
The step `fix-conflict` SHALL judge only bot pull requests. It SHALL refuse pull requests with human authors, or claims and `owner/*` labels by humans or agents, and SHALL verify that the remote head matches the expected head. With `--confirm`, a head branch with a commit past the default branch that the App did not write SHALL fail the round with `failed` (`clone_branch`). It SHALL enforce a soft cap of 2 rounds, a hard cap of 4 rounds, and at most one model round per `<base>:<head>`.

#### Scenario: A person pull request is refused
- **WHEN** `fix-conflict` runs on a pull request authored by a human
- **THEN** the step refuses the pull request and makes no changes

#### Scenario: A commit of a person after the bot push is refused
- **WHEN** `fix-conflict --confirm` runs on a branch that holds a commit past the default branch that the App did not write
- **THEN** `clone_branch` refuses the branch, the round fails with `failed`, and the step makes no changes

#### Scenario: An item with an owner label is refused
- **WHEN** the item holds an `owner/human` or `owner/agent` label
- **THEN** the step halts and does not modify the branch

#### Scenario: Caps enforce round limits
- **WHEN** a pull request reaches 4 rounds or exceeds the soft cap without reducing conflicted files
- **THEN** the step halts further attempts

### Requirement: Tier 1 resolves deterministic conflicts with no model call
In the agent phase, the step SHALL settle each stop of the rebase with the shared rules (`rebase_onto`). It SHALL take the default branch's side for generated documents and `uv.lock` (`git checkout --ours`, or `git rm` when that side has no file) and make them again at that stop. It SHALL drop only the item's archive commit (`git rebase --skip`), which holds only OpenSpec paths of the item and generated documents, and archive the change again after the rebase.

#### Scenario: An archive commit that is not the tip
- **WHEN** a confirmed round finds a conflict on archive paths, and a bot commit follows the archive commit
- **THEN** the step drops the archive commit, keeps the later commit, archives the change again on the tip, and pushes with zero model requests

#### Scenario: An archive commit that holds code
- **WHEN** the commit with the conflict on archive paths also holds a path that is no OpenSpec path and no generated document
- **THEN** the round stops, and the head branch does not change

#### Scenario: A spec commit that is no archive commit
- **WHEN** a commit with only OpenSpec paths conflicts that does not move the change folder, such as a fix of the spec after the archive, or that also archives another item
- **THEN** the round stops, and the head branch does not change

#### Scenario: An archive commit whose generated document conflicts too
- **WHEN** the archive commit and the default branch both change the spec and a generated document
- **THEN** the step takes the default branch for the document, drops the archive commit, and archives the change again

#### Scenario: A generated document that the default branch deleted
- **WHEN** the default branch deleted a generated document that the pull request changed
- **THEN** the step runs `git rm` for it, continues, and the pushed result has no such document

#### Scenario: A generated document that both sides renamed
- **WHEN** the default branch and the pull request rename a generated document to two names
- **THEN** the pushed result holds only the name of the default branch

#### Scenario: A generated docs and lockfile conflict is resolved
- **WHEN** a conflict occurs on generated CLI reference documents and on `uv.lock`
- **THEN** the step takes the base branch version, runs `uv lock` and `devops docs generate`, and no git call of the step sets an environment variable

### Requirement: A conflict on a release path stops with class conflict
When any conflicted path is a release path, the step SHALL NOT attempt automated resolution and SHALL stop with failure class `conflict`. A release path is `CHANGELOG.md`, a file of release-please (`.release-please-manifest.json`, `release-please-config.json`, `.release-please*`), or `pyproject.toml` when its `version =` line conflicts. The `version =` line of a package in `uv.lock` is none. The plan and the round SHALL ask one check (`release_conflict`), so the plan names the same stop.

#### Scenario: A conflict on a release path stops with class conflict
- **WHEN** a conflict occurs on `CHANGELOG.md` or a release manifest
- **THEN** the step halts with failure class `conflict`

#### Scenario: The plan and the round agree on a version line
- **WHEN** the side of the pull request in a conflict of `pyproject.toml` holds its `version =` line
- **THEN** the plan says `stop on the release path`, and a confirmed round stops and runs no fixer

#### Scenario: The version line of a package in uv.lock
- **WHEN** the side of the pull request in a conflict of `uv.lock` holds the `version =` line of a package, and the pull request also adds a file
- **THEN** the plan says that tier 1 takes the default branch, and a confirmed round takes the `uv.lock` of the default branch, runs `uv lock` once, and pushes the branch with the added file as its one change

### Requirement: Strict validation runs before push
Before any push of a resolved branch, the step SHALL run `openspec validate --specs --strict`. If validation fails, the step SHALL NOT push the branch. The step runs no other check before the push.

#### Scenario: The strict validation runs before each push
- **WHEN** conflicts are resolved on a branch
- **THEN** `openspec validate --specs --strict` runs before `git push`

### Requirement: Tier 1 runs only in a runner Job
Tier 1 runs code of the checkout (`devops docs generate`, `uv lock`), so the step `fix-conflict` SHALL rebase, run tier 1 and push only with `--confirm`. The command SHALL clear the dumpable flag of its process and adopt orphans first, and then accept `--confirm` only in a runner Job (`require_runner`), or in the agent phase of one (`require_agent_runner`). Without `--confirm` the step SHALL return `planned`, and SHALL run no code of the checkout, push nothing and write no record.

#### Scenario: Without --confirm the step gives its plan
- **WHEN** the step runs without `--confirm` on a bot pull request that conflicts with the default branch
- **THEN** it returns `planned` with the conflicted files, runs no fixer of tier 1, pushes nothing and writes no record

#### Scenario: A plan on a host with no App
- **WHEN** the step runs without `--confirm` on a host with no `service.github_app.slug`
- **THEN** it returns `planned`, as its clone makes no check of the authors, which needs the App

#### Scenario: --confirm outside a runner Job runs no step
- **WHEN** the command runs with `--confirm` outside a runner Job
- **THEN** it stops with the error of the runner check before the step

#### Scenario: A confirmed round hardens its process first
- **WHEN** the command runs with `--confirm` in a runner Job
- **THEN** it calls `deny_environment_reads`, then `adopt_orphans`, then the runner check, and only then the step

### Requirement: The plan says what a confirmed round does
Without `--confirm`, the reason of the plan SHALL sort the conflicted paths with the classification that the round uses. It SHALL name a stop when `roadmap.fix_conflict.tier1_mode` is not `on`, when `release_conflict` holds, or when a path is no archive, generated document or lockfile path.

#### Scenario: The plan of a conflict that tier 1 does not settle
- **WHEN** the step runs without `--confirm` on a conflict of a source file
- **THEN** the reason starts `Plan: stop, because tier 1 settles only`

#### Scenario: The plan of an archive and a generated document
- **WHEN** the step runs without `--confirm` on a conflict of a spec and a generated document
- **THEN** the reason starts `Plan: drop the archive commit of the item`, as a confirmed round drops it

### Requirement: The step runs on the phases prepare, agent and publish
With `--confirm`, the step SHALL take `--phase prepare|agent|publish|all`, with `all` by default and `--work` for each other phase. `prepare` SHALL admit the round, clone the head branch plainly (`clone_branch`), and record `onto` and the judged head. The agent phase SHALL make no GitHub call. `publish` SHALL push the patches as commits of the bot on `onto` from a new repository, with a lease on the judged head, and only a result that holds a commit past the default branch.

#### Scenario: A setting that tier 1 writes changes no push
- **WHEN** in a runner Job, tier 1 writes a `pre-push` hook, `remote.origin.pushurl`, `remote.origin.receivepack`, a `url.<base>.insteadOf` rule, or a `reference-transaction` hook that refuses an update of a remote-tracking ref into the clone
- **THEN** the round ends `resolved`, the push goes to the repository on GitHub, and no program that tier 1 wrote runs

#### Scenario: No commit past the default branch
- **WHEN** tier 1 takes the default branch for each change of the pull request
- **THEN** the round fails with `The rebase left no commit past the tip of the default branch`, and the head branch does not change

#### Scenario: A merge of the default branch is no commit of a person
- **WHEN** the bot merged the default branch into the head branch
- **THEN** the authors of the pull request leave out the clean merge (`person_authors`), and the plan names the conflict

#### Scenario: The three phases on one run folder
- **WHEN** `prepare`, `agent` and `publish` run one after the other on one run folder for an archive conflict
- **THEN** the agent phase makes no GitHub call, and `publish` returns `resolved` with the pushed head and one round

#### Scenario: A phase with no run folder
- **WHEN** the command runs `--phase agent` or `--phase publish` with `--confirm` and no `--work`
- **THEN** the command exits 1

### Requirement: Each round counts and gives back the judged head when it does not settle
`prepare` SHALL add one to the rounds of the record when it gives a round to the agent phase, so a round counts also when the agent phase writes no outcome. `publish` SHALL write the result, a refusal too, and add no round. A round that does not end `resolved`, also on an error, SHALL abort the rebase, reset the clone to the judged head, and push nothing. A failed git call or program of tier 1 is a stop; any other error goes on after the cleanup.

#### Scenario: A git call of the round that fails
- **WHEN** a git call of tier 1 fails
- **THEN** the round stops with the error of git, the stop is recorded, and the head branch does not change

#### Scenario: A skip that git refuses
- **WHEN** `git rebase --skip` fails and the rebase stays on the same commit
- **THEN** the round stops with the error of git, and records the stop

#### Scenario: Each round counts
- **WHEN** a round fails the strict validation, leaves no commit past the default branch, or the remote refuses its push
- **THEN** the rounds of the record rise by one

#### Scenario: A program of tier 1 that fails
- **WHEN** `uv lock`, `devops docs generate` or the archive of tier 1 exits with a status that is not 0
- **THEN** the reason of the stop holds the exit status and the last lines of the output of the program, masked

#### Scenario: A program of tier 1 that runs out of time
- **WHEN** a program of tier 1 runs out of time, so that the agent phase writes no outcome
- **THEN** the error goes on, the rounds of the record rise by one, and the head branch does not change

#### Scenario: A head that moves before the push
- **WHEN** the head of the pull request moves while the agent phase runs
- **THEN** `publish` refuses the push, records the refusal, and the rounds of the record rise by one
