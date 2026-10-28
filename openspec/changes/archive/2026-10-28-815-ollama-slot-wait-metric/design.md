# Design

## The instrument

`devops_cli_ai_ollama_slot_wait_seconds` is a histogram in seconds with two labels:

- `priority`: the `RequestPriority` value that the call waited with (`high`, `normal` or `as_available`). The value is the resolved priority: the argument when the caller gives one, else the `current_request_priority` of the context.
- `outcome`: `ok` when the call holds a slot, `timeout` when its deadline passed with no slot. The words are those of `devops_cli_ai_gateway_slot_wait_seconds`, so one query reads both histograms the same way. An `as_available` call with no free slot has a deadline of 0 s, so it observes `timeout` at once.

## Where the wait is measured

The clock starts before the call takes `ollama_slot_condition` and stops when `_wait_for_slot` returns or raises its `AIClientError`. The wait for the lock is part of the queue, so it counts. `emit` runs after the call leaves the condition, so the export never holds the lock that the other callers wait on.

Each call observes once. A call that finds a free slot observes about 0 s. The quantiles then describe all calls, and the count of the histogram is the count of slot requests.

## The panel

"Ollama Slot Wait by Priority (p95)" sits in the free half of the last row of `ai-spend.json` (x 12, y 36), beside "Response Cache Hit Share". It charts:

- `histogram_quantile(0.95, sum by (priority) (increase(devops_cli_ai_ollama_slot_wait_seconds[1h])))`, the p95 wait over the last hour by priority, outcomes together. A timeout counts at the wait that it had, so a timeout pushes the quantile up.
- `histogram_count(sum by (priority) (increase(devops_cli_ai_ollama_slot_wait_seconds[1h])))`, the slot requests of the hour, so a p95 over a few calls is visible as such.

The description states the limits of `increase()` that `test_every_panel_counting_with_increase_states_its_limits` asks for.

## Rejected alternatives

- **The name `devops_cli_ai_slot_wait_seconds` that the issue proposed.** Rejected: since #815 was filed, `devops_cli_ai_gateway_slot_wait_seconds` records the gateway's slot. A name with no pool reads as if it covered both waits, and it covers only Ollama's.
- **One histogram for both pools, with a `pool` label.** Rejected: the gateway's slot has no priority, so its points would carry an empty `priority`. The gateway histogram also has a span and docs of its own (`ai.llm.gateway_slot`). A rename of it is not part of this issue.
- **A span for the Ollama wait, as the gateway has.** Not asked by #815. The metric covers the need, and a span adds one span to each Ollama call.
- **Gauges of the lease counts and queue lengths.** Rejected by the issue: each command is its own process, so a gauge keeps only the last process's value.
- **Observe only the calls that waited.** Rejected: the quantiles would then ignore the calls that had no wait, and the count would not show how often calls queue.

## Test

The tests call `acquire_ollama_slot` and read the exported points through the `captured` fixture. No test patches a devops-cli name.

- A call with a free slot sends one point with its priority and outcome `ok`.
- A `normal` call that waits behind a held slot sends one point with outcome `ok` after the holder releases. The test waits until `get_ollama_waiting_counts` shows the call in the queue, then releases the slot.
- An `as_available` call with no free slot raises `AIClientError` and sends one point with outcome `timeout`.
