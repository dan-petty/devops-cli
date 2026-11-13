This review is a later review. An earlier review of this plan found defects, and the planner wrote a revision of the plan in answer. The JSON document has two more keys:

- `earlier`: each open finding of the earlier review, with its `number`, `type`, `where`, `problem` and `quote`.
- `answer`: each block of lines of the plan that the revision added or changed. The planner fixes a finding at its place, or shows in `feasibility`, with a quote of the inputs, that the finding is no defect. Both answers are in `answer`. A line that the revision only removed is not in `answer`.

Give one verdict for each finding of `earlier`:

- `gone`: the plan does not have the defect now. The revision fixed it, or `answer` shows with a quote of the issue, the plan or a file that it is no defect.
- `holds`: the plan still has the defect. A claim with no quote that proves it does not make a defect gone.

Then report new defects. Report a new defect only in a text of `answer`, and copy its `quote` from that text, also for a `criterion_dropped` defect. A defect in a text that the revision did not change is not a new defect of this review: the earlier review judged that text. Do not report an earlier finding again as a new finding.

The reply has the keys `earlier` and `findings` and no other key. The value of `earlier` is a list of objects with the keys `number` (the number of the finding in `earlier`) and `verdict` (`holds` or `gone`), one for each earlier finding. The value of `findings` is the list of new findings, in the form above, or an empty list.
