# Design

## Decisions

- **Catch the change in the writer of the Service round.** `RefineWriter.settle` catches `RoadmapItemChangedError` in its own `except` clause, before the clause of `DevOpsCLIError`. The error class is the one fact that tells a race from a failed write, and the store raises it before it changes anything. So the item needs no record, and the next round reads it again. The selection takes the item again, because refine wrote no mark.
- **One result for both checks of the race.** The store guard and the body check of `_apply_refined` find the same event: the item changed between the read and the write. Both give `RefineApplied(changed_count=1)`, and `settle` writes no result line and counts no write for both. The body check keeps its WARNING line, which its test reads (#1539).
- **A changed item writes no result line.** `docs/roadmap/job-success.md` already says that an alternatives check whose body a person changed since the read writes no line, and #5166 plans the same for intake. The race is no attempt of the job: refine did not revert a change that it did not see (ADR 0002), and no fix of refine can prevent the race. So the grade counts it neither as a success nor as a failure. The INFO line keeps each race visible in Loki.
- **A failed model call stays a failure.** When the record write of a `RefineFailure` meets a changed item, the failure stays in the failures of the round, and its line stays `error` with the class of the model call. Only the INFO line replaces the WARNING of a failed write.
- **The CLI path does not change.** `apply_refine`, which `devops roadmap refine --confirm` runs, still lets `RoadmapItemChangedError` go to the person (#5114). The issue is about the Service round.

## Rejected alternatives

- **Log `skipped` with `success=true`, as the acceptance of the issue says.** The issue builds this on the claim that intake counts `skipped` as an intended result, and that claim is false. A `success=true` line also counts an attempt that wrote nothing as a success, which lifts the grade of refine with no work, and it gives a third rule for the same race next to the rule of alternatives and the plan of #5166.
- **Log `skipped` with `success=false`, as intake does today.** The grade would still count a race that no fix can prevent as a fault of refine.
- **Make the body check raise `RoadmapItemChangedError`.** `apply_refine` would then stop the CLI round at the first changed body, which is a change of the CLI that the issue does not ask for.
- **Catch the error in `_apply_result`.** That also changes `apply_refine`, and the test of #5114 expects the CLI to raise.
