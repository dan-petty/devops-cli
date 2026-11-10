# Design

## Decisions

- **Print the facts on every `stage reply refused` line, not only on `degenerate`.**: A comparison of a `refused` line with a `degenerate` line shows which fact differs, and the code has one path.
- **Put the new fields before `result=`.**: A reader of the end of the line keeps working.
- **Print `none` for a fact the run does not hold.**: A kept plan or a plain client has no run, and an empty value breaks a `key=value` parser.
- **Take `finish_reason` and `answered` from the last reply of the run.**: The last reply is the one that the gates refuse.

## Rejected alternatives

- **Log the text of the reply.**: The reply may hold private data, and `<n>.refused.json` keeps it already with masking (#4204).
- **Add a metric.**: A metric does not tie the facts to one item. The line does, and a later change may count what the line shows.
