# Tasks

## 1. Find the commits that changed a named path after the base

Reads: `src/devops_cli/roadmap/clone_git.py`, `src/devops_cli/roadmap/stage_paths.py`. Changes: `src/devops_cli/roadmap/stage_moved.py` (new), `tests/roadmap/test_roadmap_stage_moved.py` (new).

- [ ] 1.1 Write `tests/roadmap/test_roadmap_stage_moved.py` first: a clone with two commits that change one named path gives both short hashes and subjects in log order, a commit that changes an unnamed path gives nothing, and a base with no later commit gives an empty list
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_moved.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/roadmap/stage_moved.py` with a frozen `MovedPath` of the path and its commits, and one function that takes the checkout, the base commit, the default branch and the named paths, runs `git log --format=%h%x00%s --name-only <base>..<branch> -- <paths>` through `git()` of `src/devops_cli/roadmap/clone_git.py`, and keeps the entries for the named paths. Give the log its own operation name for the git helper
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_moved.py` passes

## 2. Write the moved paths in the comment of a staged item

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_moved.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 2.1 Add a case to `tests/roadmap/test_roadmap_stage_plan.py`: a plan that names a path which a later commit changed gives a comment with the moved-file heading, the path and the commit, and a plan with no moved path gives a comment with no heading
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 Fetch the default branch in `plan_stage` before the comparison, and read the moved paths of each `StagedChange` with the new function of `src/devops_cli/roadmap/stage_moved.py`. Keep them on `StagedChange`, and render them in `_notes` of `src/devops_cli/roadmap/stage.py` under a heading that `src/devops_cli/lang/en/messages.py` holds, one line for each path with its short hash and subject. Render nothing when no path moved
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. Ask the stage prompt for the preconditions of a callee

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`.

- [ ] 3.1 Add one rule to the `feasibility` section of the stage prompt: give one line for each function that the plan calls whose arguments need a checkout, a client or a network, and name that need in the line
  - Verification: `uv run devops openspec check` passes
- [ ] 3.2 src/devops_cli/ai/tasks/roadmap_stage_change.md, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## 4. Check the prompt rule and the changed code together

Reads: `tests/roadmap/test_roadmap_stage_prompt_rules.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`. Changes: `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 4.1 Add a test to `tests/roadmap/test_roadmap_stage_prompt_rules.py` that loads `src/devops_cli/ai/tasks/roadmap_stage_change.md` and asserts that its text names a checkout, a client and a network as preconditions of `feasibility`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
