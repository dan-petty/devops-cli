# Design

## Decisions

- **Store the expected quote in the existing `Defect.evidence` field.** `Defect` already holds free text evidence, and one fixture does not justify a schema change. The evidence holds the exact design line and the exact `missing_path` bullet.
- **Set the gate to `none`.** No stage gate judges a restated cited rule. The verification pass reports the defect, and the case scores it.
- **Use `4e0e2435`, the parent of the plan commit, as the base commit of the case.** The verification pass reads the cited prompt from the checkout of that commit, and the prompt there still defines `missing_path` only for a file that does not exist. On the default branch, #3405 later widens the bullet, so the restatement becomes true and the case has no false premise.
- **Let the case join the score without a code change.** `load_cases` reads every directory under `CASES_DIRECTORY`, and `evaluate_cases` scores each loaded case. The case therefore appears in the score and in the recall of the `false_premise` type.

- **Add the case to half B of the fixed split and move no other case.** The cuts in `src/devops_cli/roadmap/stage/jev_screen_cuts.json` were fitted on the recorded halves. Half B is the smaller half (27 cases against 29), and `halves` puts the new case there too.
- **Test the case with no git.** `docs/TESTING.md` lets no test start a system program or skip on the state of the host. The quote test reads the plan of the case and a source tree under `tmp_path`, and it proves that the plan cites the prompt. The match test calls `matched_defects`, which reads no checkout. The Feasibility section records the bullet of the prompt at the base commit.
- **Keep the body that the stage job wrote.** The pass reads the whole plan, `pull_request_body` too. The body that the author edited later says that the change widens `missing_path`, which is the corrected premise, so the plan would hold both premises.

## Rejected alternatives

- **Add a `Defect.quote` field.** The reply model of the pass has no quote field, and the existing `evidence` field already holds the expected text.
- **Set the gate to `paths`.** The paths gate checks file paths, spec deltas and the verify form, and it does not read a restated rule of a cited file.
- **Make the split again with `halves` over all 57 cases.** It moves 42 other cases to the other half, so the fitted cuts no longer match the half that they were fitted on.
- **Read the prompt of the base commit with `git show` in the test.** The test then starts a real git and skips in a clone that lacks the commit, so a wrong base commit passes with no failure.
- **Score the case with `evaluate_cases` on `stage_repo`.** The run checks out a real git repository under `tmp_path`, and `matched_defects` gives the same proof with no git.
- **Use the default branch head as the base commit.** After #3405 the prompt matches the plan, so the case would hold no false premise and would score nothing.
