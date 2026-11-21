# roadmap-fix-conflict Specification

## Purpose
How the roadmap step `fix-conflict` settles merge conflicts on topic branches of bot pull requests: admission bounds, tier 1 deterministic resolution, verification, and runner job integration.

## Requirements

### Requirement: The step admits only bot pull requests and enforces bounds
The step `fix-conflict` SHALL judge only bot pull requests. It SHALL refuse pull requests with human authors, human commits after the bot push, or claims and `owner/*` labels by humans or agents. It SHALL verify that the remote head matches the expected head. It SHALL enforce a soft cap of 2 rounds, a hard cap of 4 rounds, and at most one model round per `<base>:<head>`.

#### Scenario: A person pull request is refused
- **WHEN** `fix-conflict` runs on a pull request authored by a human
- **THEN** the step refuses the pull request and makes no changes

#### Scenario: A commit of a person after the bot push is refused
- **WHEN** the branch holds a human commit after the last bot commit
- **THEN** the step refuses the pull request and makes no changes

#### Scenario: An item with an owner label is refused
- **WHEN** the item holds an `owner/human` or `owner/agent` label
- **THEN** the step halts and does not modify the branch

#### Scenario: Caps enforce round limits
- **WHEN** a pull request reaches 4 rounds or exceeds the soft cap without reducing conflicted files
- **THEN** the step halts further attempts

### Requirement: Tier 1 resolves deterministic conflicts with no model call
In a runner Job, in a confirmed round of the step or in the rebase of the implement job, when merge conflicts occur on archive paths (`openspec/specs/**`, `openspec/changes/archive/**`), the step SHALL drop the archive commit, rebase preceding commits onto the default branch, and re-run the finish step from the active change folder. When conflicts occur on generated documentation or `uv.lock`, the step SHALL take the base branch version and regenerate them.

#### Scenario: An archive-only conflict ends with clean push and zero model requests
- **WHEN** a round in a runner Job finds a branch that conflicts only on OpenSpec archive paths
- **THEN** the step drops the archive commit, rebases, re-archives the change, and pushes with zero model requests

#### Scenario: A generated docs conflict is resolved
- **WHEN** a round in a runner Job finds a conflict on generated CLI reference documents
- **THEN** the step checks out the base branch version and runs `devops docs generate`

#### Scenario: A lockfile conflict is resolved
- **WHEN** a round in a runner Job finds a conflict on `uv.lock`
- **THEN** the step checks out the base branch version and runs `uv lock`

### Requirement: A conflict on a release path stops with class conflict
When any conflicted path is a release path, including `CHANGELOG.md`, manifests, or package version definitions, the step SHALL NOT attempt automated resolution and SHALL stop with failure class `conflict`.

#### Scenario: A conflict on a release path stops with class conflict
- **WHEN** a conflict occurs on `CHANGELOG.md` or a release manifest
- **THEN** the step halts with failure class `conflict`

### Requirement: Strict validation and scoped checks run before push
Before any push of a resolved branch, the step SHALL run `openspec validate --specs --strict` and execute the scoped quality checks. If validation or checks fail, the step SHALL NOT push the branch.

#### Scenario: The strict validation runs before each push
- **WHEN** conflicts are resolved on a branch
- **THEN** `openspec validate --specs --strict` runs before `git push`

### Requirement: The runner job calls fix-conflict on rebase conflicts
When a rebase conflict occurs during an implement runner job, the job SHALL invoke `fix-conflict` instead of immediately stopping with action `wait`. When the conflict cannot be resolved, the stop comment SHALL record that a fix round was executed.

#### Scenario: A rebase conflict runs one fix round
- **WHEN** an implement runner job encounters a rebase conflict
- **THEN** the job executes one fix round in place of stopping with action wait

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

### Requirement: The step reaches origin only at the URL that it read after its clone
The step SHALL read the URL of `origin` right after its clone, before tier 1 runs, and SHALL run each fetch and push through `OriginGit` at that URL, with a lease on the judged head for the push. Each local git call of the step SHALL run with `core.hooksPath=/dev/null`. In a runner Job, a git setting of the clone that `OriginGit` does not allow SHALL stop the round before the push.

#### Scenario: A hook or a setting that tier 1 writes changes no push
- **WHEN** tier 1 writes a `pre-push` hook, `remote.origin.pushurl`, `remote.origin.receivepack` or a `url.<base>.insteadOf` rule into the clone
- **THEN** the push goes to the URL that the step read after its clone, and no hook, program or other repository that the clone names runs

#### Scenario: A fetch reads no setting of the clone
- **WHEN** the clone holds `remote.origin.uploadpack`
- **THEN** the fetch of the step does not run that program

#### Scenario: A local git call runs no hook of the clone
- **WHEN** the clone holds the hooks `post-checkout`, `pre-rebase`, `post-rewrite`, `pre-commit`, `prepare-commit-msg`, `commit-msg` and `post-commit`
- **THEN** a confirmed round of the step runs none of them

#### Scenario: In a runner Job a refused setting stops the push
- **WHEN** tier 1 writes `remote.origin.pushurl` into the clone in a runner Job
- **THEN** the step raises `GitSettingsError` before the push, and the head branch does not change

### Requirement: The step continues a rebase with no environment override
The step SHALL continue a rebase with `git -c core.editor=true rebase --continue`, and SHALL pass no environment variable to a git call. It SHALL check out the head branch from the remote-tracking ref that its fetch wrote, so the checkout works in its shallow clone.

#### Scenario: A docs and lockfile round completes in a runner Job
- **WHEN** a round in a runner Job finds a conflict on a generated document and `uv.lock` in the shallow clone of the step
- **THEN** it checks out the head branch, continues the rebase, generates both files again and pushes, and no git call of the step sets an environment variable

#### Scenario: A failed generation stops the implement job with class conflict
- **WHEN** `devops docs generate` fails after tier 1 took the default branch for the conflicted document in the rebase of the implement job
- **THEN** `fix_rebase_conflict` returns false and records `stopped`, and the job stops the item with the class `conflict`

### Requirement: A round pushes only a result that holds the default branch and the pull request
A rebase that fails with no conflicted file SHALL stop the round with a reason that names its cause, and SHALL push nothing. Before a push, the step SHALL check that HEAD is the head branch, holds the tip of the default branch and differs from it, and holds each change of the pull request on a path that the default branch did not change and that tier 1 does not generate. The step SHALL never push the tip of the default branch.

#### Scenario: A rebase that stops for another cause
- **WHEN** a confirmed round rebases a branch whose first commit applies with no conflict, and git refuses the commit of that pick
- **THEN** the round stops with a reason that starts `The rebase failed with no conflicted file`, records the stop, and the head branch does not change

#### Scenario: A result that is no head to push
- **WHEN** HEAD is not the head branch, is the tip of the default branch, does not hold it, or lacks a change of the pull request
- **THEN** the check gives a reason that names it, and the step pushes nothing

### Requirement: The clone of the step commits as the bot
Right after its clone, the step SHALL write the identity of the bot (`commit_author`) into the configuration of the clone, as `ensure_checkout` does for the clone of the implement and fix-checks Jobs. The rebase and the commits of tier 1 SHALL not depend on an identity of the host.

#### Scenario: A host with no git identity
- **WHEN** git of the host has no identity and refuses to guess one (`user.useConfigOnly`), and a confirmed round settles a conflict of a generated document and `uv.lock`
- **THEN** the round ends `resolved`, and the committer of the pushed head is the bot

### Requirement: The step fetches the history to the merge base
The step SHALL deepen its shallow clone through `OriginGit`, twice as far each time, until the clone holds the merge base of the head branch and the default branch, holds the whole history, or a deepening adds no commit. When the history holds no merge base then, the step SHALL fail with a reason that names both branches, before the check of the authors.

#### Scenario: A merge base 60 commits behind the default branch
- **WHEN** the head branch forked from a commit of a person, 61 commits below the tip of the default branch, and the clone holds the newest 50 commits
- **THEN** the plan names the conflicted files, and a confirmed round in a runner Job ends `resolved`

#### Scenario: No merge base
- **WHEN** the head branch has a root of its own
- **THEN** the step fails with the reason `The history holds no merge base of origin/main and origin/<head>.`

### Requirement: The plan says what a confirmed round does
Without `--confirm`, the reason of the plan SHALL sort the conflicted paths by the rules of tier 1. It SHALL name a stop when `roadmap.fix_conflict.tier1_mode` is not `on`, when a path is a release path, or when a path is no archive, generated document or lockfile path.

#### Scenario: The plan of a conflict that tier 1 does not settle
- **WHEN** the step runs without `--confirm` on a conflict of a source file
- **THEN** the reason starts `Plan: stop, because tier 1 settles only`
