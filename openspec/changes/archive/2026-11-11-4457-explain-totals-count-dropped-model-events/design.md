# Design

## Decisions

- The encoded trace keeps four sums of the dropped events: `dropped_tokens`, `dropped_seconds`, `dropped_repair_rounds` and `dropped_outcomes`. They are the inputs of `trace_totals`, so the totals of a long run equal the totals of the full run. The bound drops attempt events only when no model event is left, but it can drop them, so their repair rounds and outcomes are kept too.
- One class, `TraceSums`, makes the sums of a set of events. `trace_totals` uses it for the kept events, and `encode` uses it for each dropped event, so the two sums cannot disagree.
- The sums count toward the bound. `encode` measures the frame of the JSON with the sums of the events that it has dropped so far, so the text stays within `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS`.
- A sum of zero is not written. A trace that fits the bound has the same form as before, and a reader of an old record sees no new key.
- The decoded sums are the start of the sums of the next encode, the same as the decoded `dropped`. `encode` does not change the trace, so the job can encode the same trace many times with no double count.
- `decode` checks the type of each sum and raises `TraceDecodeError`, the same as for `dropped`, so `explain` names `implement.trace` for a value that is not a trace.

## Rejected alternatives

- Read the token total from `implement.spend`. The record holds no seconds, and it does not give the repair rounds or the outcomes.
- Raise the bound or keep more model events. A longer run still drops them, and the bound protects the size of the issue body.
- Count only the model events and leave out the attempt events. The bound drops attempt events when no model event is left, and the totals would then be wrong again.
- Write the four keys always. Every trace that fits the bound would change its form for no gain.
