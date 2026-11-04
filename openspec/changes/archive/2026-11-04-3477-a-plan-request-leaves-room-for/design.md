# Design

## Decisions

- **Use fixed caps of 20,480 tokens for the context and 8,192 tokens for the body, each also at most its share of the window.**: The issue measured that the caps as shares of a 65,536-token window (32,768 and 16,384 tokens) leave the request over the limit of 49,152 tokens. A fixed cap does not grow when the window grows to the 1,048,576 tokens of the model, and the share keeps a small window safe.
- **Send the names of the capabilities when the run has `read_spec`, and the full entries when it has no tool.**: The names count 1,117 tokens and the entries count 27,910 tokens. A run with no tool cannot read a spec, so it keeps the entries. The check `check_proposal` reads the specs from the checkout and not from the request, so it does not change.
- **Decide on-demand delivery from `ToolboxClient.reads_specs`, which is true when the run has OpenSpec.**: A toolbox run without OpenSpec answers to `read_spec` that no spec can be read, so the names alone would leave the model without a purpose.
- **Give the purpose in the answer of `read_spec` for one capability.**: The prompt tells the model to choose a capability by its purpose. The `overview` field of `openspec show --json` holds the Purpose text, so the tool needs no new read.
- **Record the offered tools in the hook and pass them to `RunTrace.absorb`.**: The messages of a run do not hold the tools that a request offered. Only the hook sees them, so the hook is the one place that can record them.
- **State the reason of a run with no tool call from the trace.**: `trace.offered` tells if any request offered a tool. A request offers no tool only when the window limit or the budget takes the tools. The first request never lacks budget, so a run that offered no tool reached the window limit.
- **Measure the refine investigation request in a test that prints the counts.**: The issue asks for a measure and no change to refine. A test needs no new command and runs offline.

## Rejected alternatives

- **Keep the window fractions and raise `context_window`.**: The gateway model allows 1,048,576 tokens, but a larger window makes the shares larger and the request larger. The hook limit follows the window, so the request would stay near the limit.
- **Remove the capabilities from the request.**: The model must choose a capability, and the names give it the list. A request with no names makes the model guess.
- **Add a new tool for capabilities.**: `read_spec` exists and covers the need.
- **Fail the run when the first request is over the limit.**: A run with no tool call can still return a valid plan, and the stage comment now says why it made no call.
- **Add a metric for the requests over the limit.**: #3240 owns the metrics.
