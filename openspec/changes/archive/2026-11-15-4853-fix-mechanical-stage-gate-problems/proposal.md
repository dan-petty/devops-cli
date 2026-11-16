# Proposal: #4853

## Why
Some stage gate problems have one correct edit that needs no model call. The dependencies gate names the other open plan item whose files overlap. The module-test gate names a module whose known test is not in the reads. A criterion text or a registry task can be missing. Each refusal costs a return of prompt tokens or fails the item.

## What Changes
- Add `apply_mechanical_rewrites` in `src/devops_cli/roadmap/stage/stage_rewrite.py`.
- Reclassify `stage_problem_registry` as a mechanical finding in `src/devops_cli/roadmap/stage/stage_findings.py` and `src/devops_cli/roadmap/stage/stage_finding_classes.json`.
- Apply mechanical rewrites in at most two passes in `src/devops_cli/roadmap/stage/stage.py` before returning a proposal to the model.
- Add and increment metric `devops_cli_roadmap_fix_checks_total` with `site="stage.gate"` and `path="mechanical"` on each rewrite.

## Capabilities
- stage-mechanical-gate-rewrite: Apply mechanical gate fixes deterministically without model calls.

## Impact
Reduces stage gate token spend and latency by fixing deterministic gate problems before calling the model.

## Feasibility
Confirmed against stage gate finding classes and existing plan rewrite patterns.

## Existing Tool Considered
The rewrite pattern of `plan_rewrite.py`; no model call. Cost to build: about 0.6M tokens, half a day.
