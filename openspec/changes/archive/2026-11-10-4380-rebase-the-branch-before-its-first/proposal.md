# Proposal

## Why

The Service opens pull requests whose branch is behind `main`. Pull request #4378 has one `wip:` commit on a merge-base from 14:05Z. It opened at 14:26Z, and `main` gained three commits (#4374, #4353, #4376) in those 20 minutes. Closes #4380.

The implement job syncs with the default branch at the start of the run (`_start`) and at the final push (`_push`). Four other pushes skip the sync: the first push of a Planned item (`_publish`), the `wip:` push of a step (`_keep`), the checkpoint between groups (`_checkpoint`) and the push of a stop (`stop`). All four go through `_push_passed`. The stage job pushes its plan branch from the staged commit after a run of 20 to 45 minutes, and nothing rebases it. The repository does not require an up to date branch on purpose, so GitHub does not enforce it. The job must do it.

## What Changes

- `_push_passed` of the implement job pushes a commit that holds `origin/<default>`.
- Between steps and at a stop, the checkout is clean, so the job fetches and rebases it as `_sync` does. It records the last `wip:` commit again after the rebase.
- During a step, the job fetches the default branch. If the branch lacks a commit of it, the job rebases a copy of `HEAD` in a detached worktree that goes at once, and pushes the tip of the copy with the lease. The checkout of the step stays as it is, because the keeper of the step holds the shas of its `wip:` commits.
- `_rebase` now takes the checkout to rebase. `_sync` and the copy share it, so a conflict has one path: abort the rebase, and name the files.
- A conflict at one of these pushes goes to the log, and the push goes on with the head so that the work stays on `origin`. The sync of the final push stops the item with the failure class `conflict`, as before.
- The stage job fetches the default branch and rebases the plan commit onto it before the push. A conflict aborts the rebase and fails the item with nothing pushed.
- The stage requirement "A staged branch starts at the staged commit" changes: the parent of the pushed commit is the default branch at the push.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: Every push holds the default branch
- `roadmap-stage`: A staged branch starts at the staged commit

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/stage/stage.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_push_current.py`, `tests/roadmap/implement/test_roadmap_implement_checkpoint.py`, `tests/roadmap/stage/test_roadmap_stage_apply.py`, `tests/support/roadmap_implement.py`
- Specs: `openspec/specs/roadmap-implement-job/spec.md`, `openspec/specs/roadmap-stage/spec.md`

## Feasibility

- The pushes of the job go through `_push_passed` (`src/devops_cli/roadmap/implement/implement_run.py`: `_checkpoint`, `_keep` and `stop` call it) or `_push`, and only `_push` and `_start` call `_sync`. Command output confirms it: `git log` of the branch of #4378 shows one commit, `wip: 1 of 2 tasks of group 1`, and `git merge-base` of it with `origin/main` is 52d5eb0e, three commits before the tip of `main` at the push.
- A step cannot rebase its own checkout. The keeper of the step (`implement_wip.py`) holds `tip` and `base`, and the step compares `HEAD` with `expected_head`. The checkout also holds edits after the `wip:` commit. A rebase in place would break both, so a copy is rebased.
- `git push origin <sha>:refs/heads/<branch>` updates `refs/remotes/origin/<branch>`, run in a temporary repository: the lease of the next push then holds. It does not set the upstream, and nothing in `src/devops_cli/roadmap` reads an upstream.
- The conflict path of `_sync` (abort, files, failure class) stays the only one. The stop that it raises ends the item at the final push.
- The stage plan holds only new files under `openspec/changes/<issue>-<slug>/`, so the rebase conflicts only when the default branch holds a file of the same path.

## Existing Tool Considered

Git covers the need: `git fetch`, `git rebase`, `git worktree add --detach` and `git push --force-with-lease`. `git replay` would rebase with no worktree, but its manual page marks it experimental, and the runner image may hold an older git. The code adds no library. Cost: about 15k tokens to build, 5k to keep and fix, about 3 hours.
