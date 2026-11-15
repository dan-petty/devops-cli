# Design

## Decisions

- **Scan the plan texts for an absence word next to the word check or guard, the code span of the named check, and the code span of the call site, instead of adding a reply field.**: The plan of #3368 stated the claim in its Feasibility text, so a required reply field would not catch a prose claim and would change the reply schema and its prompt for no gain.
- **Keep the scan and the search in `src/devops_cli/roadmap/stage/stage_probe.py`, not in `stage_change.py`.**: The scan makes no plan finding: the job returns the item instead of sending the reply back to the model, so it is no rule of the plan check and no new gate.
- **Read the body of the call site and of the functions that it calls in the same file first, then search the source files of the staging commit, with the commands that the probe of the item has left.**: The helper that the plan missed sits beside its call site, and a whole-tree search first can report a check that the call site never calls. Sharing the commands of the one run keeps the item within the bound of 10 that the base spec states.
- **Reuse `FalsePremise` with a `PremiseKind` field instead of adding a new outcome class.**: `plan_stage`, `plan_item`, `apply_stage` and `fix_plan` already return a `FalsePremise` to New, so a second class would repeat each of those paths for the same write.
- **Record `refine.next_step` as `retry` for a claim, and keep `edit` for a false absence.**: The body of a duplicate item is correct and only the plan was wrong, so a body edit would wait for a change that no person needs to make.
- **Write the plan-level tests in `tests/roadmap/stage/test_roadmap_stage_plan.py` and seed the sample file with `advance_origin`.**: The module already holds the plan-level tests of the probe quote and of the return, and `advance_origin` is the helper that the module already uses to add a file to the staging commit.

## Rejected alternatives

- **Search the whole base tree first and report the first line that holds the check.**: `src/devops_cli/roadmap/implement/implement_run.py:1463:def _delivery_title(self) -> str:` shows that the check sits one call below the cited site: a tree-first search reports the definition of the title check in another module, not the call in the helper that the plan missed, and it can name a check that the call site never reaches.
- **Ask the verifier model to find the claim in the plan.**: ADR 0005 keeps a finding deterministic and from a tool, and `docs/adr/0005-review-findings-come-from-tools-not-models.md` rejects a model verdict on a code claim, so the search is a read-only tool answer.
- **Add a required `missing_checks` field to `StageProposal`.**: The refused plan of #3368 made the claim in its Feasibility text, so a field that a model may leave empty catches no prose claim and changes the reply schema.
- **Stop the item as Blocked instead of returning it to New.**: `src/devops_cli/roadmap/stage/stage.py:925:class FalsePremise:` is the outcome that returns an item to New, and the issue asks for that return with the evidence, not for a stop.
