# Proposal: #5019

## Why
No automated step settles merge conflicts on open bot pull requests. When a rebase conflict occurs during an implement runner job, the item stops with class `conflict` and action `wait`, which requires manual intervention to clear. In high-frequency release repositories, 75% of conflicting base updates come from OpenSpec archive appends. Closes #5019.

## What Changes
This change adds the `fix-conflict` step under `devops_cli.roadmap.steps.fix_conflict` and the CLI command `devops roadmap step fix-conflict --pull N`.
- Implements two tiers of conflict resolution:
  - Tier 1 (deterministic, no model call): handles archive conflicts by dropping the archive commit, rebasing, and running the finish step again from the change folder; handles generated docs conflicts by taking the base branch and running `devops docs generate`; handles `uv.lock` by taking the base branch and running `uv lock`.
  - Tier 2 (model): sends remaining conflicted files, both sides, and plan scope to the model.
- Stops immediately if a release path (`CHANGELOG.md`, manifests, version lines) conflicts.
- Applies strict safety bounds: processes only bot pull requests with no subsequent human commits, enforces soft cap of 2 rounds (extendable to 3 if conflicted files decrease) and hard cap of 4 rounds, and enforces at most one model round per `<base>:<head>`.
- Validates with `openspec validate --specs --strict` and scoped checks before pushing.
- Integrates the step into the implement runner job so rebase conflicts trigger a fix round instead of waiting.
- Updates `docs/ROADMAP_WORKFLOW.md` and failure action table so `conflict` maps to `repair`.

## Capabilities
- `roadmap-fix-conflict`: provides deterministic and model-assisted merge conflict resolution for bot pull requests.

## Impact
- Automates resolution of base merge conflicts (especially OpenSpec archive appends and generated doc drift).
- Reduces manual human stops in the roadmap implement pipeline.

## Feasibility
- Tested against git rebase, `git merge-tree --write-tree`, `devops docs generate`, and `uv lock`.
- Verified archive commit isolation and re-archiving on top of rebased branches.

## Existing Tool Considered
- `git rebase` and `git merge-tree --write-tree` are used directly.
- The GitHub update-branch API was rejected because it refuses merge conflicts.
- Git union driver was rejected because it can duplicate conflicting requirements.
- Mergiraf was rejected due to its GPLv3 license.
