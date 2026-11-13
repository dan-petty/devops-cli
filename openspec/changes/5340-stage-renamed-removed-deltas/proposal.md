# Proposal: #5340

## Why

The stage job cannot write a RENAMED or a REMOVED spec delta. `StageSpec` holds only `added` and `modified`, and `spec_file` writes only those two sections. So a plan that changes the meaning of a requirement keeps the old name above the new text. Plan #5182 (item #3785) did this, and its delivery #5336 merged a requirement whose name says the opposite of its text. The planner also wrote a false reason in its design: "a delta refuses a modified name". OpenSpec and `openspec/config.yaml` accept RENAMED and REMOVED.

Closes #5340.

## What Changes

- `StageSpec` gets `renamed` (pairs of `from_name` and `to_name`) and `removed` (`name`, `reason` and an optional `migration`). `spec_file` writes them as `## RENAMED Requirements` FROM and TO lines and `## REMOVED Requirements` blocks with `**Reason**:` and `**Migration**:` lines, the form of the OpenSpec documents and of the hand-written plans of this repository.
- The spec-delta gate refuses a rename or a removal on a new capability, a `from_name` or a removed `name` that the base spec does not have, and a `to_name` that the base spec has already.
- The job copies the base scenarios that a MODIFIED block omits also for a requirement under its new name: it reads them under the old name of the rename.
- The stale-command check accepts a removed base requirement, and a renamed base requirement that a MODIFIED block rewrites under its new name.
- The stage prompt tells the planner when to rename and when to remove. The review prompt makes a MODIFIED requirement whose name no longer fits its text a `spec_delta_wrong` finding, so the review gate sends such a plan back.
- The plan reader reads both sections back, so write, then read, keeps each fact (#5205), and fix-plan keeps a rename or a removal when it writes a plan again. Plan-check compares a MODIFIED requirement under a new name with the base text under its old name.
- The change fits one pull request.

## Capabilities

- Modified: `roadmap-stage/spec-delta` (the reply, the delta file, the gate, the scenario copy and the prompts).
- Modified: `roadmap-plan-check` (the plan reader and the moved-spec check).

## Impact

- `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_validate.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/lang/en/messages.py`.
- `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`.
- `docs/roadmap/stage.md`, `docs/roadmap/plan-check.md`.
- A plan with no rename and no removal gives the same files as before. The fix takes effect in the Service after a release and a new Service image.

## Feasibility

- Source at `origin/main` 54cf0a526: `StageSpec` in `src/devops_cli/roadmap/stage/stage_change.py` holds only `capability`, `purpose`, `added` and `modified`; `spec_file` writes only `## ADDED Requirements` and `## MODIFIED Requirements`; `_spec` of `src/devops_cli/roadmap/plan_read.py` reads only those two sections.
- Real plans: the spec deltas of the Service plan pull requests #5350, #5333, #5283 and #5182 (open or merged in the last 14 days) hold only ADDED and MODIFIED. #5182 modifies `The alloy-profiles pod does not run on the node ...` with a text that says that the pod runs on every node, and its `design.md` says that a delta refuses a modified name. #5336 archived that text into `openspec/specs/monitoring-collectors/spec.md`.
- Tool: `openspec --version` on `PATH` is 1.17.0. Its parser (`dist/core/parsers/requirement-blocks.js`) reads `- FROM: \`### Requirement: <name>\`` and `- TO: ...` pairs and `### Requirement: <name>` headers under REMOVED. Its validator refuses a MODIFIED block under the old name of a rename, and its archive (`dist/core/specs-apply.js`) applies RENAMED, then REMOVED, then MODIFIED, then ADDED, and refuses a FROM that the spec does not have or a TO that it has. `validate` does not check that a FROM exists, so the stage gate checks it.
- Hand-written plans of this repository use the same form, for example the archived changes of #5150 (RENAMED) and #4798 (REMOVED with `**Reason**:` and `**Migration**:`).
- The last `plan_defect` failure of the stage job (item #5118, plan #5350, 2026-11-13 03:40Z) is a `spec_delta_wrong` finding about a duplicated requirement, not about a rename. So this change does not fix that failure. It removes the cause of the false names that #5182 shows.
- #5256 asks for the reader part. The writer and the reader share one contract (#5205), so this change holds both.

## Existing Tool Considered

OpenSpec defines the delta form and validates it, and the job already runs `openspec validate --strict` on each plan. No tool writes the delta from the reply of the model, so the change extends the writer and the reader of the job. Cost to build: about 1.5M agent tokens and 3 hours. Keep: the two models and their render and read functions.
