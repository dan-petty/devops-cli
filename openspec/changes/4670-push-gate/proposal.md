# Proposal

## Why

The owner rule of 2026-11-11 says that each push to GitHub holds the latest `origin/main` and merges cleanly ([docs/SDLC.md](../../../docs/SDLC.md), Branch Governance & Hierarchy). No check enforces it. The pre-push stage runs only lint, format and the workflow rows. In the week of 2026-11-04 to 2026-11-11, 19 force pushes reached a pull request that had a conflict (#4670). The implement Job also pushes a head that does not hold `main`: after a rebase conflict, `_current_tip` pushes the head, and the conflict stop pushes the commits that passed (`push_on_conflict`).

A branch that holds `origin/main` merges into `main` with no conflict, because `main` is then the merge base. So one check, "the pushed commit holds `origin/main`", covers both parts of the rule.

## What Changes

- A new pre-push hook `branch-current` in `.pre-commit-config.yaml`, with `language: system` and a few lines of `sh`. On a `git push` of a branch (`PRE_COMMIT_REMOTE_BRANCH` is `refs/heads/...`), it fetches `main` of `origin` with a limit of 20 s. It refuses the push when `git merge-base --is-ancestor FETCH_HEAD <pushed commit>` fails, and names the fix: `git fetch origin && git rebase origin/main`. A fetch that fails gives its own message. A tag push passes, and pre-commit runs no hook for a delete. A run of the stage that is no `git push`, as the scoped checks of the implement Job, passes. Thus a move of `main` during those checks does not go to the model as a defect of the code. The hook runs first in the stage with `fail_fast: true`, so a refused push does not wait for the other hooks.
- The implement Job pushes nothing after a rebase conflict. `_sync` and `_rebase` lose `push_on_conflict`, and each rebase stop has `push=False`. `_current_tip` no longer catches the conflict. A checkpoint, a `wip:` push and the push of a stop that meet a conflict push nothing, and the conflict goes to the log or to the stop comment. The rebases before each push stay as they are.
- No catch-up check. #4674 deletes `devops pr update`, the main source of catch-up pushes.

## Capabilities

### New Capabilities

- `pre-push-branch-current`: The pre-push hook refuses a branch that does not hold origin/main.

### Modified Capabilities

- `roadmap-implement-job`: Every push holds the default branch, A stopped item is Blocked and the job does not retry it.

## Impact

- Code: `.pre-commit-config.yaml`, `src/devops_cli/roadmap/implement/implement_run.py`
- Tests: `tests/git/test_branch_current_hook.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_push_current.py`, `tests/core/test_roadmap_implement_checks.py`
- Documents: `docs/SDLC.md`, `docs/ROADMAP_WORKFLOW.md`, `CONTRIBUTING.md`, ADR 0014, the skill `devops-pr-ci` and its two copies.
- Each push from a workstation makes one fetch of `main`. A push with no network stops with the fetch message.
- After a conflict, the work of a run that no checkpoint pushed stays only in the Pod. The next Job starts from the branch on `origin` and gets the conflict files (`implement.conflict`).

## Feasibility

- pre-commit 4.6.2, `pre_commit/commands/hook_impl.py`, `_pre_push_ns`: a ref whose local sha is all zeros (a delete) is skipped, and a push of only deletes runs no hook. For a pushed ref, `commands/run.py` sets `PRE_COMMIT_REMOTE_BRANCH` to the remote ref (`refs/heads/<name>` or `refs/tags/<name>`) and `PRE_COMMIT_TO_REF` to the pushed commit. pre-commit checks only the first ref of a push. `clientlib.py` has the per-hook key `fail_fast`.
- The implement Job installs no git hook (`implement_hooks.py`). It runs the stage with `pre-commit run --hook-stage pre-push --from-ref origin/<default> --to-ref HEAD` (`implement_scoped_ci.py`, `scoped_checks`), which sets no `PRE_COMMIT_REMOTE_BRANCH`. So the hook passes in the Job, and the Job keeps its own rebase before each push.
- `implement_run.py` at `origin/main` (e4fc6a9f, 2026-11-12): `_current_tip` catches the `_StopError` of the rebase and returns `self._head()`. `_sync` has `push_on_conflict=True` by default, so the stop of `_push` pushes the commits that passed.
- `git merge-base --is-ancestor A B` exits 0 when `A` is an ancestor of `B`, and 1 when it is not (git-merge-base(1)). `FETCH_HEAD` is a ref of each worktree (git-worktree(1)), so two worktrees that push at the same time do not read the fetch of the other.
- A real `git push` through the installed hook, in a repository with a bare `origin` in a temporary directory (pre-commit 4.6.2, git 2.55): a branch one commit behind `main` was refused with the fix line, and nothing reached `origin`. The same branch after `git rebase origin/main` was pushed. A tag and a delete of the branch were pushed. A push to a second remote while `origin` pointed to a missing repository stopped with the fetch message.

## Existing Tool Considered

pre-commit-hooks `check-merge-conflict` (v5.0.0, already in `.pre-commit-config.yaml`) finds conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) in the files of a commit. It does not read the remote, so it does not see a branch behind `main`: such a branch has no markers. That hook stays. No hook of pre-commit-hooks checks that a branch holds a remote branch. The GitHub ruleset setting "require branches to be up to date before merging" acts at the merge, not at the push, and the owner keeps it off (ADR 0014). So the new hook is git's own check, `merge-base --is-ancestor`, in about 10 lines of shell in the configuration. Cost: about 150,000 tokens and 2 hours to build, near 0 to keep and fix.
