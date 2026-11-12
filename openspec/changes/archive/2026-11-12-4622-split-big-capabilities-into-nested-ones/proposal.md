# Proposal: #4622

## Why

Issue #4622 asks to split the big OpenSpec capabilities into nested capabilities, to cut merge conflicts. In the conflict census of 2026-11-04 to 2026-11-11, 97 of the 130 conflicting base updates of topic pull requests included a file under `openspec/specs/`, and 62 were only in such files. `openspec/specs/roadmap-stage/spec.md` alone had 81 conflicts. `openspec archive` 1.14.3 appends each ADDED requirement at the end of the file of its capability, so two pull requests that archive into one capability always conflict.

## What Changes

- The four big capabilities become 44 nested capabilities under an area of the same name: `roadmap-stage` (342 requirements) gives 21, `roadmap-implement-job` (145) gives 7, `roadmap-implement-step` (91) gives 7 and `roadmap-refine` (81) gives 9. Each nested capability holds the requirements of one gate or module, from 4 to 36. Each requirement moves word for word, in the order of its old file, and each nested capability gets a Purpose. The four old files go.
- The deltas of the 13 open change folders that name a split capability move to the nested capability that holds their requirements, and their proposals name the new ids.
- The stage job reads the base capabilities from `openspec list --specs --json` and reads the file of each one. The flat folder walk of `read_base_specs` goes. A spec delta of a stage reply can name a nested capability, and the validation copies the base spec of a nested capability.
- The plan reader and the refine context read a spec file at any depth as the capability of its folder path. A nested capability covers a module by the name of its area.
- `openspec/config.yaml` states the limit of 80 requirements, the nested layout and the rule that a new requirement goes into the nested capability of its gate or module. An invariant test fails for a capability over the limit, and for an area that holds a `spec.md` of its own.
- The stage prompt names the form of a nested capability. The roadmap documents link to the nested capabilities.

The stage job, the plan check and refine now read and write nested capabilities, which a consumer observes, so the change carries a spec delta.

## Capabilities

- `roadmap-stage/spec-delta`: the stage job reads the capabilities that OpenSpec lists.
- `roadmap-implement-job/selection`: the plan check reads a nested capability.
- `roadmap-refine/context`: the context reads a nested capability.

## Impact

- `openspec/specs/` (the four areas), `openspec/changes/` (13 open deltas), `openspec/config.yaml`.
- `src/devops_cli/roadmap/stage/stage_specs.py`, `stage_tools.py`, `stage.py`, `stage_eval_run.py`, `stage_change.py`, `stage_validate.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, and their tests.
- `docs/roadmap/stage.md`, `docs/roadmap/implement.md`, `docs/roadmap/refine.md`.
- An open pull request or plan that has a delta of a split capability moves it with one `git mv` of `specs/<old>/spec.md` to `specs/<old>/<nested>/spec.md`. A delta that stays at the old id archives into a new `openspec/specs/<old>/spec.md`, which the invariant test refuses.
- The change fits one pull request.

## Feasibility

Confirmed on the pinned OpenSpec 1.14.3 (`~/.local/share/devops-cli/tools/openspec/1.14.3`):

- `dist/utils/spec-discovery.js` walks `specs/` recursively and gives `specs/<area>/<id>/spec.md` the id `<area>/<id>` (#1353 of OpenSpec).
- In a scratch tree with `specs/area/cap-one/spec.md` and `specs/flat/spec.md`, `openspec list --specs --json` listed `area/cap-one` and `flat`, `openspec show area/cap-one --type spec --json` gave its requirements, `openspec validate --specs --strict` passed both, and `openspec archive` applied an ADDED and a MODIFIED requirement of `changes/c1/specs/area/cap-one/spec.md` to the nested file.
- After the split, `openspec validate --specs --strict` passes all 290 capabilities, and `openspec validate --all --strict` passes every open change folder.
- For each of the four areas, the requirements that `openspec show <area> --type spec --json` gives on `origin/main` equal the union of the requirements of its nested capabilities: the same 659 names, texts and scenarios, with none lost, added or changed (342, 145, 91 and 81).

## Existing Tool Considered

OpenSpec 1.14.3 itself: its nested layout and `openspec list --specs --json` cover the need. The change deletes the flat folder walk of `read_base_specs` and the private listing of `StageTools`, and reads the capabilities from the tool. The plan reader and refine read a commit, not a checkout, so they keep their git listing and only take a folder path at any depth.

Rejected: a git union merge driver (GitHub ignores the merge drivers of `.gitattributes` in its own merge and conflict check, and ADR 0010 showed that a union merge hides a lost edit), an archive after the merge (a rule change that the owner did not choose), and a GitHub merge queue (not available to a repository of a user account).
