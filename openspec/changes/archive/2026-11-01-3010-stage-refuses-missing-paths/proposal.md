# Proposal

## Why

Issue #3010: about 25 of the 37 plans that the stage job opened on 2026-10-31 name a file that does not exist on `main`. The plan of #2260 names `src/devops_cli/commands/uv_cmd.py` and `tests/test_roadmap_dry_runs.py`. The plan of #2162 names 13 test files that moved. The plan of #2116 names `tests/test_scanner_tool_executor.py`, which #2830 moved to `tests/security/`. The model copies old paths from the issue body and cannot list files.

Today `missing_paths` only adds a note to the stage comment. The draft still opens, a person merges the plan, and the implement Job stops at group 1. At least 12 issues are `status/blocked` for this reason.

## What Changes

- A new module `src/devops_cli/roadmap/stage_paths.py` holds `StagedTree`, the tracked files of the checkout at the staged commit (`git ls-files -z`), and `path_problems`.
- `check_proposal` takes the tree. A path that is no file at the commit, and that no group up to its own creates, is a problem of the reply. The paths are those of `reads` and `changes`, the paths in code spans of the three tasks, and the paths in `verify`.
- The problem lists the files of the commit with the same file name. The reply goes back to the model once. A second reply with a missing path stops the item with `RoadmapStageError`, so no draft opens.
- The job checks the groups again after a split.
- `missing_paths`, `StagedChange.missing` and the note in the stage comment go away: the comment can no longer name a missing path.
- The stage prompt tells the model that the job checks every path. `k8s/README.md` step 15 and the stage spec say the same.
- The dry run lists the one `git ls-files` read of a round.
- Observable behavior changes (a job stops on a reply, and a comment loses a sentence), so the change carries a spec delta.
- The change fits one pull request.

The change does not build the other checks of the evaluation of 2026-11-01 (the premise probe, the callers of a symbol, the spec-delta rule, the test command, the group order and the acceptance map).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: adds the requirement "The plan names files that exist at the staged commit". It replaces "A staged item gets one comment and a record" with "The comment and the record of a staged item": the comment no longer names missing paths.

## Impact

- Code: `src/devops_cli/roadmap/stage_paths.py` (new), `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/lang/en/messages.py`.
- Prompt: `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Documents: `k8s/README.md`, `openspec/specs/roadmap-stage/spec.md` (by archive).
- Tests: `tests/roadmap/test_roadmap_stage_paths.py` (new), `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/roadmap/test_roadmap_dry_runs.py`, `tests/support/roadmap_stage.py`.

## Feasibility

- `git grep -n "missing_paths" -- src` shows one definition in `stage_change.py` and one use in `stage.py`. The use fills `StagedChange.missing`, and `_notes` prints it in the comment. Nothing stops the item.
- `git ls-files | grep test_scanner_tool_executor.py` prints `tests/security/test_scanner_tool_executor.py`. `git ls-files | grep -c "uv_cmd.py"` prints 0. The plans of #2260 and #2116 name the old paths, so the premise holds on `origin/main`.
- `git ls-files -z` lists the 4680 tracked files of the checkout in 6 ms. One read in a round costs nothing next to a model call.
- `named_files` in `step_files.py` keeps a code span only when it is a file inside the checkout, so a wrong path is invisible to the budget measure. The check has to run on the reply, before the files are written.
- The suffixes of the tracked files are `.md`, `.py`, `.yaml`, `.json`, `.yml`, `.ambr`, `.tf`, `.j2`, `.toml`, `.lock`, `.txt`, `.example`, `.in`, `.html`, `.css`, `.jsonc` and `.graphql`. The first components of the paths are names such as `src`, `tests`, `docs` and `k8s`. Both sets are enough to tell a path from a word, a label such as `status/blocked` or a dotted name.

## Existing Tool Considered

The change builds on tools the code already uses: `git ls-files` (the same command family as `planned.py`), `fnmatch` of the standard library for a glob in `reads` or `changes`, and the markdown-it parser of `step_files.py` for the code spans of a task. No library checks the paths of a plan against a commit. The check is about 120 lines. The cost to build is about 60 000 tokens, to keep it about 5 000 tokens a year, and to fix it about 10 000 tokens. It takes one working day. The change deletes `missing_paths`, `StagedChange.missing` and the message `stage_comment_missing`.
