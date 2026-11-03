# Proposal

## Why

A staged plan can rest on a base that `main` has moved past. The plan in #3261 held two stale facts: a title rule that `staging_title` had changed, and two callees that need a checkout, which the plan did not say. Both reached a reviewer, who had to find them (#3309). The stage job now names the plan's files that `main` changed after the base, and the prompt asks for the preconditions of each callee.

## What Changes

- A new module `src/devops_cli/roadmap/stage_moved.py` finds the commits that changed a path after the base commit.
- The stage job keeps the moved paths of each planned item and writes them in the comment of the staged item.
- New messages in `src/devops_cli/lang/en/messages.py` give the heading and the lines of the moved-file section.
- The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` asks for one `feasibility` line for each called function whose arguments need a checkout, a client or a network.
- The change alters the comment that the stage job writes, so it carries a spec delta on `roadmap-stage`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The comment lists the named paths that moved, A moved path gives its commits in log order, The comparison reads the latest default branch, The prompt asks for the preconditions of a called function

## Impact

- Code: `src/devops_cli/roadmap/stage_moved.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_moved.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- `list_files` and `read_file` showed that `src/devops_cli/roadmap/stage.py` holds `StagePlan.sha`, the base commit of a run: `sha: str = ""`, set from `read_stage_selection` with `sha = inspect_checkout(source, repo)`.
- `read_file` of `src/devops_cli/roadmap/stage.py` showed that `_stage_one` posts the comment with `texts.stage_comment_staged.format(marker=..., branch=..., pull=..., budget=..., groups=..., notes=_notes(change))`, so the comment is the place for the moved-file section.
- `read_file` of `src/devops_cli/roadmap/stage_change.py` showed that a group holds `reads` and `changes` as `list[RepositoryPath]`, so the union of both is the set of paths the plan names.
- `read_file` of `src/devops_cli/roadmap/clone_git.py` showed the `git(cwd, *args, operation=...)` helper that runs a git command in the clone, so the log needs no new process edge.
- The premise holds: the code cited by the issue exists at the staging commit and holds the state the issue describes.
- First check against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_moved.py` runs the new tests offline.
- Second check against the real system: `uv run devops ci lint` runs Ruff over the new module and the changed files.

## Existing Tool Considered

Git covers the need. `git log --format=%h%x00%s --name-only <base>..<default> -- <path>` lists the commits that changed a path and the files of each commit, from the clone that the stage job already holds. The repository already wraps it in `git()` of `src/devops_cli/roadmap/clone_git.py`, so the change adds no dependency and no network call. Git does not parse the plan's `reads` and `changes` lists, so the change adds about 80 lines of code and its tests: a build of roughly 6k tokens, a keep cost of a few hundred tokens per change, and under an hour of work. It deletes no internal code.
