# Proposal: #6704

## Why

The stage Job pushes the plan with plain git from a worktree of the clone that the planner reads (`_worktree`, `_commit_and_push`, `_push`). implement, fix-checks and fix-conflict push on the phases of ADR 0030, from `roadmap/phases/`. The owner decided that stage gets a real shell only when `publish` pushes (#6528 comment 7053539044). Closes #6704.

## What Changes

- The stage round runs the three phases of the plan commit in sequence, in one process (`stage_phases.py`). `prepare` clones the issue branch into a new run folder (`clone_branch`). The agent work writes the change folder on the staged commit and writes the patch (`write_patch`). `publish` applies the patch to the tip of the default branch as one commit and pushes it with a lease (`publish_patch`): on `stage.sha` for a re-stage, else on the tip that `prepare` found.
- `_worktree`, `_commit_and_push`, `_push` and `_rebase_onto_default` go.
- `clone_branch` takes the identity of the commit, so the stage commit keeps the identity of the clone of the job.
- A re-stage whose branch moved past `stage.sha` pushes nothing, also when the new tree is the tree of `stage.sha`.
- A draft that GitHub refuses deletes the pushed branch from the repository that the push went to (`delete_branch` of the phases).
- The `base` of `add_worktree`, which only the old push read, goes.

## Capabilities

- `roadmap-stage/round`: the push of the plan commit and the staged commit of its change folder.

## Impact

The plan commit goes on the tip of the default branch with no rebase, and a re-stage replaces the plan branch with one commit. The CronJob and the command do not change; `--phase` and `--work` come with #6705.

## Feasibility

The stage tests run the round on real git with a local `origin`. The new tests fail on `main` and pass with this change.

## Existing Tool Considered

`roadmap/phases/` holds the clone, the patch and the publish already (#6655); the change reuses them and adds no tool.
