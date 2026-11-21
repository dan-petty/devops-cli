## RENAMED Requirements

- FROM: `### Requirement: Strict validation and scoped checks run before push`
- TO: `### Requirement: Strict validation runs before push`

## MODIFIED Requirements

### Requirement: Strict validation runs before push
Before any push of a resolved branch, the step SHALL run `openspec validate --specs --strict`. If validation fails, the step SHALL NOT push the branch. The step runs no other check before the push.

#### Scenario: The strict validation runs before each push
- **WHEN** conflicts are resolved on a branch
- **THEN** `openspec validate --specs --strict` runs before `git push`

### Requirement: Tier 1 resolves deterministic conflicts with no model call
In a runner Job, the step SHALL settle each stop of the rebase onto the default branch. It SHALL take the default branch's side for generated documents and `uv.lock` (`git checkout --ours`, or `git rm` when that side has no file). It SHALL drop only the item's archive commit (`git rebase --skip`), which moves the item's change folder into the archive and holds only OpenSpec paths of the item and generated documents. After the rebase it SHALL make these files and the archive again.

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
When any conflicted path is a release path, including `CHANGELOG.md`, manifests, or package version definitions, the step SHALL NOT attempt automated resolution and SHALL stop with failure class `conflict`. The plan and the round SHALL ask one check (`release_conflict`), so the plan names the same stop.

#### Scenario: A conflict on a release path stops with class conflict
- **WHEN** a conflict occurs on `CHANGELOG.md` or a release manifest
- **THEN** the step halts with failure class `conflict`

#### Scenario: The plan and the round agree on a version line
- **WHEN** the side of the pull request in a conflict of `uv.lock` holds a `version =` line
- **THEN** the plan says `stop on the release path`, and a confirmed round stops and runs no fixer

### Requirement: The runner job calls fix-conflict on rebase conflicts
When a rebase conflict occurs during an implement runner job, the job SHALL invoke `fix-conflict` instead of immediately stopping with action `wait`. When the conflict cannot be resolved, the stop comment SHALL record that a fix round was executed. A round that does not settle the conflict, also on an error such as a timeout, SHALL give the branch back its tip from before the rebase, and the job SHALL then run no second abort.

#### Scenario: A rebase conflict runs one fix round
- **WHEN** an implement runner job encounters a rebase conflict
- **THEN** the job executes one fix round in place of stopping with action wait

#### Scenario: A failed round keeps the commits of the groups
- **WHEN** `openspec validate` fails after tier 1 settled the rebase of an implement runner job
- **THEN** the branch is at its tip from before the rebase

#### Scenario: A timeout in tier 1
- **WHEN** `devops docs generate` runs out of time in the rebase of an implement runner job
- **THEN** the branch is at its tip, the round is recorded as `failed`, and the error goes on to the job

#### Scenario: The stop claims no failed abort
- **WHEN** tier 1 does not settle the rebase of an implement runner job
- **THEN** the stop comment does not say that an abort of the rebase failed

## ADDED Requirements

### Requirement: Tier 1 runs only in a runner Job
Tier 1 runs code of the checkout (`devops docs generate`, `uv lock`), so the step `fix-conflict` SHALL check out the head branch, rebase, run tier 1 and push only with `--confirm`. The command SHALL accept `--confirm` only in a runner Job (`require_runner`), and SHALL clear the dumpable flag of its process and adopt orphans before the step. Without `--confirm` the step SHALL return `planned`, and SHALL run no code of the checkout, push nothing and write no record.

#### Scenario: Without --confirm the step gives its plan
- **WHEN** the step runs without `--confirm` on a bot pull request that conflicts with the default branch
- **THEN** it returns `planned` with the conflicted files, runs no fixer of tier 1, pushes nothing and writes no record

#### Scenario: --confirm outside a runner Job runs no step
- **WHEN** the command runs with `--confirm` outside a runner Job
- **THEN** it stops with the error of the runner check before the step

#### Scenario: A confirmed round hardens its process first
- **WHEN** the command runs with `--confirm` in a runner Job
- **THEN** it calls the runner check, then `deny_environment_reads`, then `adopt_orphans`, and only then the step

### Requirement: The step works in a clone of its run and pushes through OriginGit
The step SHALL clone the repository into a new folder of the run (`ensure_checkout`), read the URL of `origin` before tier 1 runs, switch to the head branch, and push through `OriginGit` to that URL with a lease on the judged head. The step SHALL push only a result that holds a commit past the default branch.

#### Scenario: A setting that tier 1 writes changes no push
- **WHEN** in a runner Job, tier 1 writes a `pre-push` hook, `remote.origin.pushurl`, `remote.origin.receivepack` or a `url.<base>.insteadOf` rule into the clone
- **THEN** the push goes to the URL that the step read after its clone

#### Scenario: No commit past the default branch
- **WHEN** tier 1 takes the default branch for each change of the pull request
- **THEN** the round fails with `The rebase left no commit past origin/main`, and the head branch does not change

#### Scenario: A merge of the default branch is no commit of a person
- **WHEN** the bot merged the default branch into the head branch
- **THEN** the authors of the pull request leave out the clean merge (`person_authors`), and the plan names the conflict

### Requirement: Each round counts and gives back the tip when it does not settle
Each round SHALL add one to the rounds of the record. A round that does not end `resolved`, also on an error, SHALL abort the rebase and reset the branch to its tip from before the rebase, then record. An error of git, such as a `--skip` that does not move the rebase on, is a stop; any other error goes on after that.

#### Scenario: A rebase that stops for another cause
- **WHEN** git refuses the commit of a clean pick, so the rebase stops with no conflicted file
- **THEN** the round stops with a reason that starts `The rebase failed with no conflicted file`, and the head branch does not change

#### Scenario: A git call of the round that fails
- **WHEN** a git call of tier 1 fails
- **THEN** the round stops with the error of git, the rebase is aborted, the stop is recorded, and the head branch does not change

#### Scenario: A skip that git refuses
- **WHEN** `git rebase --skip` fails and the rebase stays on the same commit
- **THEN** the round stops with the error of git, and records the stop

#### Scenario: Each round counts
- **WHEN** a round fails the strict validation, leaves no commit past the default branch, or the remote refuses its push
- **THEN** the rounds of the record rise by one

### Requirement: The plan says what a confirmed round does
Without `--confirm`, the reason of the plan SHALL sort the conflicted paths with the classification that the round uses. It SHALL name a stop when `roadmap.fix_conflict.tier1_mode` is not `on`, when `release_conflict` holds, or when a path is no archive, generated document or lockfile path.

#### Scenario: The plan of a conflict that tier 1 does not settle
- **WHEN** the step runs without `--confirm` on a conflict of a source file
- **THEN** the reason starts `Plan: stop, because tier 1 settles only`

#### Scenario: The plan of an archive and a generated document
- **WHEN** the step runs without `--confirm` on a conflict of a spec and a generated document
- **THEN** the reason starts `Plan: drop the archive commit of the item`, as a confirmed round drops it
