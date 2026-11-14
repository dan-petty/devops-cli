# Design

## Decisions
1. **Item Label Guard in `_report_ended`**:
   Before calling `_report`, check whether `job is not None and job.labels.get(ITEM_LABEL) != str(item.number)`. If the label does not match, continue the loop without calling `_report` and without adding the Job to `reported`.
   - Rationale: This stops comment creation, log reading, and state recording before any side effects happen.

2. **Preserve `gone` Reporting**:
   When `job is None`, the Job is gone from the cluster. The round continues to report `gone` as before because a gone Job has no log to disclose and legitimate items must settle cleanly.

## Rejected Alternatives
- **Guard in `_report` before `_log_of`**:
  Rejected because `_report_ended` would still add the Job name to `reported` and might perform partial operations. Checking before `_report` keeps `_report_ended` clean and cohesive.
- **Repository label check**:
  Rejected because every runner Job in the repository shares the repository label, which cannot distinguish between two items in the same repository.
