# Design

## Decisions

- **Add `path:N` and `path:N-M` to `_CITATION_PATH`.**: The pattern already defines the path of a citation with `_CITED_PATH`, so the two forms reuse it. A line range can also carry text (`path:N-M:text`). The citation gate keeps its own patterns, so this change does not change which citations it reads.
- **Take the tool names from `tool_names(HOLDER_STAGE_EXTENDED)`.**: `_trace_problems` already builds this set for tool claims. `_claimed_path` gets it as an argument, so the gate has no second list of tool names. A first word that is no toolbox tool, such as `cat`, stays in the path, and the path is refused.
- **Remove a trailing `/` on both sides of the comparison.**: `TraceFacts.of` keeps the `directory` value of a call as the model wrote it, with or without a `/`. A claim of `tests/telemetry/` and a listed `tests/telemetry` (or the reverse) are the same directory.
- **Remove the quoted probe sentences before the claim is read.**: `check_gates` already gets the probe lines of the run for the content gate, which asks the plan to quote one word for word. The trace gate splits each probe line into sentences, drops the end mark, and removes each one from each Feasibility sentence. A quote without its end mark or inside quotation marks is removed too. The words that stay still make a claim, so "I read `x`, and the probe says: ..." is judged on `x`.
- **Read the sentences with white space squashed.**: The content gate compares squashed text with the probe lines, so the trace gate uses the same form to find the quotes.

## Rejected alternatives

- **Match the probe template text with a pattern of its own.**: The templates live in `MESSAGES.roadmap.stage_probe_*`. A second pattern would be a copy that goes out of date, and the gate has the real probe lines of the run.
- **Accept a claimed directory when the run read a file inside it.**: The claim says the run read the directory. A read of one file does not support that, and it would weaken the gate.
- **Re-anchor a stale `path:N:text` citation at the one line that holds its text.**: That is a change to the citation gate, not to the trace gate. The study counted 33 of 41 stale citations that match one line. It is a separate item (see Workflow follow-up of the tasks).
- **Also judge the subject of `reads` when it is the plan, a group or a check, and `read` inside `read-only`.**: The replay of the stored records shows these causes in the refusals that stay. They change which words make a claim, not which path a span names, so they are a separate item with their own evidence.
