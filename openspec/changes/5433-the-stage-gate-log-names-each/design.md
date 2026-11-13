# Design

## Decisions

- **One line for each finding, after the counts line.** `log_gate_returns` keeps the `stage gate returns:` line as it is and then logs `stage gate refused finding:` lines. The shepherd queries the counts line, so its fields do not change. The event name does not hold the text `stage gate findings`, so a query of the counts of a return does not match the new line.
- **The last refused reply only.** The new lines come from the same call as the counts line, with the same findings: the findings of the reply that ended the item, or of the last refused reply before a pass. The `stage gate findings:` lines already give the counts of each earlier return.
- **At most 20 findings, each with its place and the count.** `finding=<place>/<count>` gives the count of all findings, so a reader sees how many lines are not there. The trace gate refused 10 paths of #1976, so 20 holds a usual reply.
- **The subject comes from the template.** `finding_subject` reads the field `path`, `tool` or `command` of the template of the code, in that order. The path that `stage_finding` already keeps comes first. A finding of a check outside `check_gates` (`title`, `body`, `validate`, `plan-check`) and an `uncoded` finding have no template, so their subject is `none`.
- **Mask first, then cut, then quote.** `mask_secrets` runs on the full subject, so a cut cannot keep the start of a token that the mask then does not find. The line keeps the first 200 characters. `json.dumps` writes the value as one quoted string, so a space or a line break in a command cannot break the fields of the line.

## Rejected alternatives

- **Add the subjects to the counts line.** The line grows with each finding, and the shepherd queries it by its fields.
- **Add a `subject` field to `StageFinding`.** The refused file keeps each finding, and the model refuses an unknown field (`extra="forbid"`). An older image cannot read a file that a newer image wrote. The subject comes from the template at log time instead.
- **Log the text of each finding.** Some templates hold text of the plan, such as `{problem}` and `{text}`. The telemetry privacy rule lets the log hold only the subject that the gate names.
- **Log the findings of each refused reply.** One item can make up to 22 plan runs, so the log grows by up to 20 lines for each one. The last refused reply decides the item.
