# Proposal

## Why

Issue #3301 reports that the premise probe of the stage job (#3176) says a file is absent when it exists at the plan base. The probe asks the HEAD commit of the clone. The round resets that clone to `origin/main` when it starts, and the stage job fetches `origin/main` again later, so its HEAD can be older than `origin/main`. A path added between the two reads is then reported as absent. The plan of #3248 used that false answer and wrote a design around a file that exists. The stage job must read one commit: the default branch of `origin`, as fetched.

## What Changes

- The stage job takes as its staged commit the commit of `origin/<default branch>` that it fetched. It no longer takes the HEAD of the clone. The origin check stays.
- Before it plans an item, the stage job moves the clone to the staged commit with `git merge --ff-only`. The toolbox refuses a checkout whose HEAD is not the staged commit, so the probe, the path check and the tools read one commit. A clone that has diverged from `origin`, or that holds a commit that `origin` lacks, fails the run, and no item is staged. The error names the reason of git, or the commit that the clone cannot move to.
- The branch of a staged item starts at the staged commit. The probe and the branch then share one commit. A pushed branch that the job takes over keeps its own tip.
- The fail-to-pass tests reproduce the false "absent" answer, the stale clone and the branch start point. The probe logic does not change.
- The report of the plan names the staged commit. The dry run lists the move of the clone and the start of each worktree at the staged commit.
- The `roadmap-stage` spec gets two added requirements. The staged commit and the branch start point are observable: a plan, a probe line and a branch parent differ.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: two requirements are added. The staged commit is the default branch of `origin`, and a staged branch starts at the staged commit.

## Impact

- Code: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/git/worktree_add.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/core/test_repos_worktrees_add.py`
- Specs: `openspec/specs/roadmap-stage/spec.md` gets the two added requirements when this change archives.

## Feasibility

- The file of #3301 exists at the base. `git cat-file -e 4571d5f3:src/devops_cli/ai/mcp/roles.py` exits 0. The commit `69234732` (#3233) is an ancestor of `4571d5f3`. `git cat-file -e 69234732^:src/devops_cli/ai/mcp/roles.py` exits 128, so a commit before #3233 reports the path as absent. This is the stale-clone case.
- The probe asks the clone HEAD. `inspect_checkout` runs `git rev-parse HEAD` (`src/devops_cli/roadmap/refine.py`, line 598), and `read_stage_selection` calls it (`src/devops_cli/roadmap/stage.py`, line 1164). The probe runs `git cat-file -e <sha>:<path>` at that sha (`src/devops_cli/roadmap/stage_probe.py`, line 121).
- The round resets HEAD to `origin/<default>` when it starts (`ensure_checkout`, `src/devops_cli/roadmap/run.py`, lines 378 and 379). Before this change, the stage job did not move HEAD after that reset. `read_planned_changes` fetches `origin/<default>` again later (`src/devops_cli/roadmap/planned.py`, line 71).
- The branch starts at a fresh `origin/main`, not at the probe commit (`src/devops_cli/git/worktree_add.py`, lines 176 to 187).
- The toolbox refuses a checkout whose HEAD is not the staged commit (`src/devops_cli/roadmap/stage_tools.py`, lines 77 to 88). So moving the clone is part of the fix, not an extra.
- The run log of #3248 was not read. The stale clone is inferred from the code of `origin/main` at `d254410c`.

## Existing Tool Considered

Git covers the need. `git rev-parse origin/<default>` names the fetched commit. `git merge --ff-only <sha>` moves the clone and refuses a diverged clone. It keeps the HEAD of a clone that is ahead of `sha`, so the job checks HEAD after the move. `git worktree add <path> -b <branch> <start>` starts the branch at a given commit. No new library is needed, and the change adds no helper. The cost of building it is about 1,500 tokens to write and about 300 tokens to keep, plus about 1 hour of elapsed time.

Deleted code: the HEAD read in `read_stage_selection`. The staged commit now comes from the fetched default branch. No module is deleted.

## Dependencies

None. The change overlaps #3276 and #3418 in the stage module. It has no blocker.
