# Design

## Decisions

- **The shadow call happens after the triage reply is checked.** The planner calls `model.observe(request, raw, judgement.possible_duplicate)` once `_resolve_raw` accepts the reply. A candidate that the triage model cannot answer is skipped and gets no Jev request. The observation never changes the `Proposal`: `observe` returns a mark and nothing else.
- **`ObservingModel` is a runtime-checkable protocol, not a new method of `IntakeModel`.** Every fake and wrapper of `IntakeModel` stays valid. `_MeteredModel` forwards `observe`, because the command wraps the model for its spend report. The meter does not count the Jev request: it counts calls of the triage model.
- **The record is a job record mark, not a file of the Service.** The mark is written with the Priority in the one `set_field` call, so it adds no request. It lives with the issue, so the owner's checkout can read it with `devops roadmap eval jev --from-shadow` without access to the volume of the Service, and a restart loses nothing. The mark holds the time, the answers and the probabilities, and no text. The final labels are the labels of the same issue, so the join needs no second store.
- **The duplicate field holds the nearest item with the highest probability and that probability, even below the 0.90 threshold.** This gives the data for a later cut. The Jev answer is the item number only when the probability reaches the threshold. The triage answer is the checked possible original. Nothing is closed or dropped.
- **A score field holds the confidence as its probability, a choice field holds the probability of the chosen option.** These are the numbers the reason lines of mode `on` already show.
- **Two counters.** `devops_cli_roadmap_intake_jev_fields_total` says which model gave a field (mode `on`). `devops_cli_roadmap_intake_jev_shadow_total` says whether the two models agree (mode `shadow`). Each is a counter of its own mode, with 10 and 15 series. A single counter would need a `mode` label and would mix two meanings of `outcome`.
- **The report states that the final label is a weak truth.** Intake writes the triage label and a label that no person changed counts as final. The columns "only Jev" and "only triage" are the ones that carry information.

## Rejected alternatives

- **A JSON lines file beside `IntakeRecord` in the Service volume.** Rejected: only the pod can read it, a new volume or a new volume path is a host change, and it needs a second join key.
- **A log line with a stable key only.** Rejected: log retention is short, and the report would need a Loki query. The log line adds nothing the mark does not hold. The metric already shows the counts.
- **A comment on the issue.** Rejected: it adds a visible comment and a write to every issue.
- **Keep the bool and add a second setting `roadmap.intake.jev_shadow`.** Rejected: two settings allow the state "on and shadow". One enum, as `jev_screen`, has no such state.
- **Count shadow outcomes in `devops_cli_roadmap_intake_jev_fields_total`.** Rejected: its outcomes `jev` and `fallback` say who decided, and a shadow count would mean something else under the same label.
