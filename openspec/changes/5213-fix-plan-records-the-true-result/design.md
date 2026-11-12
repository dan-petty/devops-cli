# Design

## Decisions

- **Read before the marks.** A plan that the reader refuses is a defect of the writer or of the reader, not of this step. So the step writes only `fix_plan.at` and `fix_plan.result`, and no result line: the `fix_plan` grade does not fall for it, and #5214 charges the defect to the stage job. The 6-hour wait of `fix_plan.at` spaces the reads, so a release that repairs the reader reads the plan at the next due round. A read error does not go to the planner, which needs a `StageProposal`.
- **One pass (#5150).** `before` is the open findings of the review of the head in this attempt, and `after` the open findings of the last review of the revision. The findings of the last plan comment have their own count, `comment`, and go to the planner only with a finding of the review of the head.
- **Keep the gated plan.** The planner keeps the gated plan, the step and the findings of the review of the head in attributes, and the `except` block of `revise_plan` copies them into the revision of a failed repair. A failure after the checks then pushes the gated plan (`regated`) and keeps its class on the line.
- **Same plan.** `same_plan` renders both plans with one change name and one date. So the `Kind:` line of an old plan, the date and the fields that no file holds are no change, and a repair that gives the plan of the head again is `unchanged`.
- **Results in order.** `stopped`, `failed`, `revised` or `cleared`, `regated`, `dismissed`, `unchanged`. The first rule that holds decides. Only `revised` and `cleared` repair a finding of the review of the same pass, so only they are a success.
- **Counts that were not measured.** A line leaves out `before` when the review of the head did not run, and `after` when no review of a revision ran, and never writes 0 for them (the rule of #5166). A success line always holds `after`, so the first-pass rule does not change.
- **No screen on the head review.** The count of the head review is the baseline of the attempt. A screen that skips it gives a count of 0 for a review that did not run.
- **A comment that keeps the label lists the findings that keep it.** The next attempt reads the newest plan comment, so a `regated` or `stopped` comment lists the open findings of the review, or those of the last plan comment when no review ran.
- **The open blockers.** The planner of `revise_plan` gets the read of the paths that open plans create, as the stage job does, so a premise that cites such a path stops the repair. The read runs only when the probe finds a cited path that the default branch lacks.

## Rejected alternatives

- **Return a stopped item to New.** ADR 0021 section 8 rule 1 lets a row write only its own record keys and its own marked comments, and the Status is no key of `fix-plan`. The step keeps the label and posts the evidence, and a person decides.
- **Count an unreadable plan as `failed` with `plan_defect`.** Live job fix-plan-validate-4963 did this: the item used an attempt, and each due round lowered the grade of a step that had no defect. The defect is in the writer or the reader (#5205).
- **Separate a variance of the review from a repair with a rule of the text of a finding.** `where` of a finding is free text, and a quote can come from the issue or a cited file (`stage_verify.py:88-97, 298-312`), so a string rule refuses real repairs of `criterion_dropped` and `task_order` findings. `same_plan` removes the identical case here, and #5215 adds a decision check of each finding of the head review on the revision.
- **Edit the `fix-plan` row of ADR 0021 section 8.** The issue asks for it, but `docs/adr/README.md` (#5270) does not let a pull request edit the body of an accepted record. The change adds a `Fact out of date` line to its `Status History`, and `docs/roadmap/stage.md` holds the rules.
- **Give `regated` the success.** A gated plan repairs no finding of a review of the same pass: it only replaces a plan that the checks refuse at the current commit.
