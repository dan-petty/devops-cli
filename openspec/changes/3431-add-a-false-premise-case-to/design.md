# Design

## Decisions

- **Store the expected quote in the existing `Defect.evidence` field.** `Defect` already holds free text evidence, and one fixture does not justify a schema change. The evidence holds the exact design line and the exact `missing_path` bullet.
- **Set the gate to `none`.** No stage gate judges a restated cited rule. The verification pass reports the defect, and the case scores it.
- **Use `4e0e2435`, the parent of the plan commit, as the base commit of the case.** The verification pass reads the cited prompt from the checkout of that commit, and the prompt there still defines `missing_path` only for a file that does not exist. On the default branch, #3405 later widens the bullet, so the restatement becomes true and the case has no false premise.
- **Let the case join the score without a code change.** `load_cases` reads every directory under `CASES_DIRECTORY`, and `evaluate_cases` scores each loaded case. The case therefore appears in the score and in the recall of the `false_premise` type.

## Rejected alternatives

- **Add a `Defect.quote` field.** The reply model of the pass has no quote field, and the existing `evidence` field already holds the expected text.
- **Set the gate to `paths`.** The paths gate checks file paths, spec deltas and the verify form, and it does not read a restated rule of a cited file.
- **Use the default branch head as the base commit.** After #3405 the prompt matches the plan, so the case would hold no false premise and would score nothing.
