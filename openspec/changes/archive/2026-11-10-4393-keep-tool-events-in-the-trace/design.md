# Design

## Decisions

- The first cause is the order. A model event is added at the moment the reply comes, so no code has to sort the events or to keep a second list. `ToolCallLog` already owns the trace and the hooks of the step, so the new hook goes there. The list order is the order of the run, so the events need no sequence field, and a trace from before the change decodes in its stored order.
- The seconds of a model event come from the monotonic clock, from the request hook to the reply hook. This replaces the difference of the two timestamps of the messages, which the post-turn pass needed.
- `ToolCallLog.replied` holds the identities of the replies that have an event. `_trace_replies` skips them and empties the set at the end of the turn, so an identity cannot match a later object.
- The exit status comes from the last line of the result of a `shell` call, read as JSON. No pattern match on the output of the command: the line is the one that the supervisor wrote, and the output of the command stands before it.
- The second cause is the bound. `encode` drops the oldest model events first, and only then the oldest of the other events. The model events are the most events of a run and hold only tokens and seconds, which `implement.spend` also keeps for the whole run. The tool, check, retry and attempt events are the only record of what the run did. `encode` takes the indexes of the events in one stable sort (model events first, each kind oldest first) and removes them until the text fits, so the kept events keep the order of the run.
- Measure of a synthetic run of 100 requests and 150 shell calls with exit statuses, then the attempt event (251 events, bound 8,192 characters). The base keeps 67 model events and the attempt event, and no tool event (`dropped` 183). The order fix alone keeps 26 model events, 41 tool events and the attempt event (`dropped` 183). The order fix with the model-first bound keeps 68 tool events and the attempt event (`dropped` 182). A run of 200 requests with 3 tool calls and 2 checks among them keeps 67 model events and no tool or check event on the base and with the order fix alone. With the model-first bound it keeps the 3 tool events, the 2 checks, the attempt event and the newest 62 model events, in the order of the run.

## Rejected alternatives

- Keep the newest events of every kind (the order fix only). A long run then still loses its older tool and check events to the model events beside them, and the issue asks that the model events go first.
- Fold the oldest model events into a summary for each window of requests. The summary is a second event shape for `decode`, `explain` and `trace_totals`, and the spend of the job record already holds the tokens of the run.
- Give each kind a fixed quota of the bound. It wastes room when one kind is absent and adds a setting.
- Add a sequence number to each event. The hook makes the list order the order of the run, so the number adds a field and a sort that give nothing more.
- Raise `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS`. The issue asks for the same bound.
- Read the exit status from `CommandFinishedEvent` on the event stream. It needs a handler that matches events to calls with no ordering against the tool result, and it adds a second path to the same fact.
