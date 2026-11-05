# Proposal

## Why

Issue #3054: a step of the implement job that stops resets the checkout, and the minutes of work in the group go with it. The step prompt says "all your work is lost". The next Job starts from the last green group and does the work again. On #2175 the agent had done all five deletions, and the item still stopped; a second Job did the same work again.

The step needs a unit of progress that survives a stop: a task that the agent ticked and whose verification passes. The job must push that progress to `origin`, so a pod that dies keeps it, and the next attempt must start from it.

## What Changes

- A new module `src/devops_cli/roadmap/implement_wip.py` holds `WipKeeper`. Before each model request, when the tool calls of the last reply have returned, it reads the `tasks.md` if the file changed. It does so in the first turn only: an extra turn may change some files only. When the agent ticked a task of the group, the keeper runs the verification commands of that task from the text before the run. When they pass, it commits the checkout as `wip: <done> of <total> tasks of group <n>, <title> (#<issue>)`. The commit holds the `tasks.md` as the job owns it: the text before the run with the ticks that the job verified. Stray files stay out of the commit.
- `run_step` gets the parameter `on_wip`, called after each `wip:` commit. A stop resets the checkout to the last `wip:` commit, not to the start of the step. The exit checks judge all the work since the last commit that is no `wip:` commit: the step puts the `wip:` commits back into the index before the checks run. A step that ends done folds them into its own commit, so a finished group is one commit.
- The implement job pushes each `wip:` commit that leaves a task unticked (the existing push with a lease, or the publish of a Planned item). The commit that ticks the last task waits for the push of the stop or of the end, because the exit checks follow at once and a claim of the item (#2910) must still find nothing pushed and records `implement.wip` (group, tasks done, tasks of the group, last commit) in the job record. The job removes the record when the group passes.
- A stop comment says how many `wip:` commits the job kept, on which branch, and the last commit.
- The step prompt says which work the job keeps. A task that is already ticked when a step starts is done and checked.
- The change carries spec deltas in `roadmap-implement-step` and `roadmap-implement-job`, because the commits, the record and the comment are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: a stopped step resets to its last `wip:` commit, and a done step folds the `wip:` commits into its commit
- `roadmap-implement-job`: the job pushes and records each `wip:` commit, and the stop comment names the kept work

## Impact

- Code: `src/devops_cli/roadmap/implement_wip.py` (new), `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`
- Tests: `tests/roadmap/test_roadmap_implement_wip.py` (new), `tests/roadmap/test_roadmap_implement_wip_job.py` (new), and the tests of the step that count verification runs
- Documents: `docs/ROADMAP_WORKFLOW.md`
- Left as they are, on purpose: the first push of a branch. The job fetches and rebases onto the default branch at the start of the run (`_start`), before any step, and again before the push of a finished item (`_push`). A `wip:` push comes between the two, from a worktree that has just been rebased. A rebase in the middle of a step would need a clean tree; it would also move the commits that the agent works on.
- A `wip:` commit holds the whole checkout at the time of the tick, not only the files of the ticked task. The exit checks and the scoped checks of the push judge it again, so a half-done edit of the next task can be in a `wip:` commit, and no unchecked work reaches a ready pull request.
- A hard kill of the pod loses the work after the last tick, which is the unit of progress that the issue asks for.

## Dependencies

- #3098 (partial implementations) builds on this change. #3053 (bounded repair rounds) works in the same area and is not part of this change.

## Feasibility

Checked on `origin/main` 4485be23, on 2026-11-04.

1. The gap is real. `git grep -n "wip" -- src/devops_cli/roadmap` printed nothing before this change. `_reset` in `implement_step.py` reset the checkout to the start of the step on every stop, and the prompt `roadmap_implement_step.md` said five times that a stop loses all the work.
2. The job already pushes the commits that passed when it stops (`_push_passed` in `implement_run.py`), and a retry takes the branch from `origin` (`recorded_branch`, `add_worktree`). So a commit that a step leaves on the branch survives a stop and a pod restart. Only a unit of progress inside a step was missing.
3. A tick is visible while the agent works. `ToolCallLog._execute` wraps each tool call of the agent in the job process, so a hook after a call runs with the agent paused. The tick is a write to `tasks.md`, and the job already owns that file: it reads the verification commands from the text before the run (`_restore_tasks`). The keeper uses the same rule.
4. The first-push rule holds. `_start` runs `git fetch` and `git rebase` onto the default branch before the first step. A Planned item gets its branch at the fetched default branch (`add_worktree`). `git grep -n "rebase" -- src/devops_cli/roadmap/implement_run.py` lists the two calls of `_sync`.
5. GitHub needs no new call. A `wip:` push uses `_push_passed`, and the record uses `set_marks`, as the stop does.

Not verified: a real model run on a pod. The tests replay the steps with a scripted model, a real git repository with an `origin`, and faked GitHub and process edges.

## Existing Tool Considered

The alternatives check of the issue names langgraph (MIT, maintained). It checkpoints the state of a run in its own store and resumes from the last completed step. It does not commit to the item branch, does not keep the state in the job record, and the runner would have to move onto its graph model (the issue comment lists the same gaps). The need here is smaller: git already stores the work and the push already moves it to `origin`. The change builds a keeper of about 150 lines and removes no internal code.

Cost to build: about 60,000 tokens (the keeper, the hooks in the step and in the job, the prompt, two test files, and the fix of the tests that count verification runs) and about 4 hours with two CI runs. Cost to keep: about 3,000 tokens each quarter. Cost to fix one miss: about 10,000 tokens.
