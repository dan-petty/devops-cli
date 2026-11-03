# Design

## Decisions

- **Detect an open finding from the result of the verification pass, not from the plan text.**: The pass already returns each finding with a quote and a `type: DefectType`, and `returning` already checks the quote against the input, so the stage needs no second model and no text parse.
- **Treat a finding as open when its type is one of the four returning defect types (`missing_path`, `false_premise`, `ignores_existing_code`, `spec_delta_wrong`) or reports a placeholder.**: The verification pass classifies findings into `DefectType`; open findings match these defect types or identify placeholder artifacts with evidence quotes.
- **Mark an open finding with the label `plan/needs-fix`.**: A label is a stable, queryable marker that a person can remove, and the `plan/` prefix keeps it apart from the `status/*` and `priority/*` families that hold item state.
- **Decide the refusal of `stage_ready` from the label, not from the comment text.**: Comment text has no machine-readable contract, and the label survives an edit of the comment.
- **Clear the label on a later stage round that returns no open finding.**: A corrected plan then moves on with no person in the loop, and a person can still remove a stale label by hand.
- **Record the item as a failed attempt of class `plan_defect` and not as staged.**: `plan_defect` already exists in `src/devops_cli/roadmap/failure.py`, so the round budget names the real cause and spends no budget on a bad plan.
- **Put the open findings first in the stage comment, ahead of the plan-run report.**: The reviewer sees the defect before the tool-call and token metrics.
- **Add a case recorded from #3174 to the golden set with the defect type `other` and the gate `none`, because no gate of the replay judges the open-finding stop.**: `DefectType` of `src/devops_cli/roadmap/stage_eval_cases.py` holds no placeholder type, and a defect for a gate that does not exist yet is listed and not failed.

## Rejected alternatives

- **Parse the plan text for `x` or `placeholder` to find a defect.**: `docs/roadmap/stage.md` line 41 and the docstring of `src/devops_cli/roadmap/stage.py` show that the verification pass already returns findings with a quote and a kind; a text parse would miss the anchor and duplicate the pass.
- **Add a placeholder value to `DefectType` of `src/devops_cli/roadmap/stage_eval_cases.py` and a gate that refuses it.**: `src/devops_cli/roadmap/stage_eval_cases.py` holds `DefectType` and `GateName` only, and `tests/roadmap/test_roadmap_stage_eval_run.py` holds the set of defect types; the open-finding stop reads the verification result of a model, which the replay makes no call to, so a replay gate could not refuse it.
- **Mark the finding with `status/blocked`.**: CONTEXT.md says the Status family holds item state and that a Blocked item waits on something outside the roadmap, which is not a plan defect.
- **Check only the draft state in `stage_ready`.**: The stage opens every plan as a draft, so the draft state cannot tell a new plan from a plan with an open finding.
- **Keep every finding as a comment only, as today.**: The issue records #3194 and #3174 staged non-draft with placeholder text, so a comment alone does not stop the pull request.
- **Replace or relax a form gate to make the stop cheap.**: `docs/adr/0004-ci-is-the-authoritative-gate.md` makes CI the merge gate, and the issue forbids lowering a gate.
