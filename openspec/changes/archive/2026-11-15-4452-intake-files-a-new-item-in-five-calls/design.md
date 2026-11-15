# Design: #4452

## Context

`_apply_placement` wrote a new candidate with `create_issue`, the sub-issue link, one label call
for each added label, one `set_field` for each of Status, Value and Effort, the comment and the
Priority. Each `set_field` reads the issue and then patches it, and a Status write also reads the
label back.

## Decisions

- `set_fields(item, fields)` is a new `RoadmapStore` method: one read, one `PATCH` with every
  label family and every record value, then the existing read-back of the record. The in-memory
  store and the contract suite hold the same promise.
- The create request carries the labels and the record, built with `with_record` and
  `encode_job_record`, so one helper writes the record format.
- Status, Value and Effort of an existing candidate take the batch. The Status label therefore
  skips the read-back of `status_sync.write_status`; a lost label waits for the next run. The
  batch keeps the person-change guard of ADR 0016.
- The dry run names one create request with every label and one batched field request, so it
  matches the run.

## Risks

- A `PATCH` that GitHub answers with an error after it applied the three labels leaves no mark,
  and the next run sees the labels and writes only the Priority. The job record holds the three
  values, so a later field write keeps them.
- The one-Status-writer invariant reads `set_field` of `ItemField.STATUS`; the batched write of
  the store is outside its scan, and the exception is recorded in the intake docstring.
