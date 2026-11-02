# Design

## Decisions

### The `paths` gate judges three types

`check_proposal` is one call in the job: it returns the problems of the path rule, the spec delta rules and the form rule together, and the client sends them back as one list. The replay mirrors that call as the gate `paths`. A defect of the type `spec_delta_wrong` or `verify_form` that this call refuses names `paths` and holds the `message` of the problem, as a `contrived_test` defect does for `kind`.

Rejected: a gate for each rule (`specs` and `form`). The evidence is the live score in `stage_eval_score.py`: it counts a defect as caught when the first reply has a problem of the gate of the type. With three gates in one call, the score would count a missing path as a catch of a form defect only if the gates shared one list, and would need a new split of the problem list otherwise. The split gives each type an exact live rate, but it also changes the live score of the model, which is not in the scope of the issue. The labels and the counts by type give the replay the same answer.

### A defect that the plan cannot show has the gate `none` and a reason

The replay reads the recorded plan, the thinned tree and the capability names. It cannot see code, base spec text or the order of work inside a group. A defect of such a kind could carry no gate without making the replay fail. The field `reason` of a defect says why. It is a label, not review text: the `problem` and `evidence` of a defect stay as the review wrote them.

Rejected: keep these defects `pending`. The type has no gate to wait for: #3012 and #3017 are merged, and no later issue adds one.

Rejected: list known misses as `missed`. A `missed` status fails the replay, which would fail on a gap of a rule that is not a regression. The reasons in `case.json` name the three gaps (`pyproject.toml`, documents at the root and code under `src/`) for a person to judge.

### The report counts by type

The gate table counts by gate, and `paths` now judges three types, so it would hide the types. A second table gives, for each type, the defects caught, missed, waiting and judged by no gate, with the total. One line gives the share of all known defects that a gate judges. A change to a gate or to the stage prompt states these numbers before and after.
