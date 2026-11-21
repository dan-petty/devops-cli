## MODIFIED Requirements

### Requirement: Tier 1 resolves deterministic conflicts with no model call
In a runner Job, the step SHALL settle each stop of the rebase onto the default branch. At a stop on archive paths, it SHALL drop the commit (`git rebase --skip`) only when each path of the commit is an OpenSpec path or a generated document, and SHALL archive the change again after the rebase, in a commit of its own. At a stop on generated documentation or `uv.lock`, it SHALL take the base branch version, continue with `-c core.editor=true`, and regenerate them after the rebase.

#### Scenario: An archive commit that is not the tip
- **WHEN** a confirmed round finds a conflict on archive paths, and a bot commit follows the archive commit
- **THEN** the step drops the archive commit, keeps the later commit, archives the change again on the tip, and pushes with zero model requests

#### Scenario: An archive commit that holds code
- **WHEN** the commit with the conflict on archive paths also holds a path that is no OpenSpec path and no generated document
- **THEN** the round stops, and the head branch does not change

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
When a rebase conflict occurs during an implement runner job, the job SHALL invoke `fix-conflict` instead of immediately stopping with action `wait`. When the conflict cannot be resolved, the stop comment SHALL record that a fix round was executed. A round that does not settle the conflict, or whose check fails after tier 1, SHALL give the branch back its tip from before the rebase.

#### Scenario: A rebase conflict runs one fix round
- **WHEN** an implement runner job encounters a rebase conflict
- **THEN** the job executes one fix round in place of stopping with action wait

#### Scenario: A failed round keeps the commits of the groups
- **WHEN** `openspec validate` fails after tier 1 settled the rebase of an implement runner job
- **THEN** the branch is at its tip from before the rebase

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
The step SHALL clone the repository into a new folder of the run (`ensure_checkout`), read the URL of `origin` before tier 1 runs, switch to the head branch, and push through `OriginGit` to that URL with a lease on the judged head. A rebase that fails with no conflicted file SHALL stop the round. The step SHALL push only a result that holds a commit past the default branch.

#### Scenario: A setting that tier 1 writes changes no push
- **WHEN** tier 1 writes a `pre-push` hook, `remote.origin.pushurl`, `remote.origin.receivepack` or a `url.<base>.insteadOf` rule into the clone
- **THEN** the push goes to the URL that the step read after its clone

#### Scenario: A rebase that stops for another cause
- **WHEN** git refuses the commit of a clean pick, so the rebase stops with no conflicted file
- **THEN** the round stops with a reason that starts `The rebase failed with no conflicted file`, and the head branch does not change

#### Scenario: No commit past the default branch
- **WHEN** tier 1 takes the default branch for each change of the pull request
- **THEN** the round fails with `The rebase left no commit past origin/main`, and the head branch does not change

#### Scenario: A merge of the default branch is no commit of a person
- **WHEN** the bot merged the default branch into the head branch
- **THEN** the authors of the pull request leave out the clean merge (`person_authors`), and the plan names the conflict

### Requirement: The plan says what a confirmed round does
Without `--confirm`, the reason of the plan SHALL sort the conflicted paths by the rules of tier 1. It SHALL name a stop when `roadmap.fix_conflict.tier1_mode` is not `on`, when `release_conflict` holds, or when a path is no archive, generated document or lockfile path.

#### Scenario: The plan of a conflict that tier 1 does not settle
- **WHEN** the step runs without `--confirm` on a conflict of a source file
- **THEN** the reason starts `Plan: stop, because tier 1 settles only`
