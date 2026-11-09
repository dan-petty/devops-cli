# Design

## Decisions

- **Record the hits in `facts.json` as a `references` tuple on `CaseFacts`.**: The facts file already holds what the gates need of the tree, as `tracked` and `search_evidence` do, and a case with no field reads the empty default of the model.
- **Give `PlanUnderTest` a `references` field with an empty default, set from `case.facts.references` in `of_case`.** The `paths` gate takes a `PlanUnderTest` and never sees the case, so the gate reads the hits from the plan under test. A reply has no probed hits at this point, so the default is empty.
- **Pass `references=plan.references` in `_path_gate` to `check_proposal`.** The job already passes its probed hits by the same keyword, so the replay and the job run one copy of the check.
- **Add one synthetic case whose plan renames the claim module and leaves two test files unchanged.** The case holds two paths that hold the old dotted name and one `missing_path` defect with the gate `paths`, so the replay shows both the refusal and the named paths. The case reads no commit and holds the files of its tree.
- **Keep the case counts as literals and raise them in this change.** The pinned counts name the size of the set, and a change that adds a case states the new size in the same pull request.

## Rejected alternatives

- **Read `case.facts.references` inside `_path_gate`.** The gate takes a `PlanUnderTest` and never sees the case, so the gate would grow a second input and a second path for the job and the replay to diverge.
- **Make `references` a required key of every `facts.json`.** It would fail every existing case until each of the 56 folders gets the key, and no rule needs the key on a case whose plan moves no module.
- **Reuse a case that already holds a `missing_path` defect.** Those cases record no reference hit, so the reference check cannot refuse them and the case would not prove the pass-through.
- **Add a `references.json` to each case folder.** It adds a file to about 56 folders and no rule needs a file of its own.
