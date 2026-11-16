# Proposal: #5916 A Job pod exports its metrics while it runs

## Why
#5916: a cluster Job pod exported its metrics only once, when its process ended. The tracer keeps its counters in an in-memory DELTA reader and exports them only in `flush()`. The Service flushes after each round (#1629). A Job runs one long command, so its only flush was the `atexit` shutdown. On 2026-11-15, each implement runner Job, for example from 21:43Z to 23:42Z, gave one sample of `devops_cli_ai_tokens_total`, at its end. So a Job showed no use while it ran, and `rate(...[5m])` never found two samples of a Job series. A Job that SIGTERM or SIGKILL ended lost its counts. The images run `devops` as PID 1 with no init, and the kernel drops SIGTERM to a PID 1 that has no handler. So the runner ran on until SIGKILL and exported nothing.

## What Changes
- The tracer exports its metrics every `OTEL_METRIC_EXPORT_INTERVAL` milliseconds, 60000 by default, from the first metric of the process on. The export goes through the existing `flush()`: the same DELTA temporality, the same OTLP/JSON encoding, and the same `_send_payload` path with its dry-run gate and its queue cap. A command that ends before the first interval exports once, at its end, as before. The shutdown stops the export thread at once.
- The `devops` entry point sets a SIGTERM handler. The handler exports what the tracer holds, in a thread of its own, for at most 5 s. Then it does what the handler before it did. With the default action, it sends SIGTERM again, so the process stops as before: the signal ends it, or, as PID 1, it runs on until SIGKILL.
- `docs/ENV_VARS.md` lists `OTEL_METRIC_EXPORT_INTERVAL`, and `docs/TELEMETRY.md` tells when a process exports its metrics.

## Capabilities
- Modified: `otlp-export`, with two ADDED requirements.

## Impact
- The metrics of a Job reach Prometheus while the Job runs, about one sample a minute for each series. `rate(...[5m])` and the panels of the ai-spend dashboard then see the Jobs.
- Job pods of one workload that run at the same time keep one stream (`service.instance.id=devops-cli-job`, #2039, #4697). `deltatocumulative` adds their deltas. It drops a point whose start is before the start of the stream (`ErrOlderStart`) or whose time is not after the last point (`ErrOutOfOrder`). In the 7 days to 2026-11-16 it dropped 812 out-of-order points and 363 older-start points, and it took about 702000 points. With a periodic export, such a drop loses one interval of one pod, not the whole run. This change keeps the shared instance id.
- A process that records a metric has one more daemon thread. The exit of a command does not wait longer.
- The change fits one pull request.

## Feasibility
- `src/devops_cli/telemetry/tracer.py` on main: an `InMemoryMetricReader` with DELTA temporality, an export only in `flush()`, the flush of the Service after each round and the `atexit` shutdown.
- Prometheus: one sample for each Job series, at the end of the Job (the evidence of the issue). `otelcol_deltatocumulative_datapoints` by `error`, 7 days: the numbers above.
- `deltatocumulative` source (opentelemetry-collector-contrib, `Aggregate`): it refuses `dp.StartTimestamp() < state.StartTimestamp()` and `dp.Timestamp() <= state.Timestamp()`.
- opentelemetry-sdk 1.45.2, `PeriodicExportingMetricReader`: `collect()` collects under the lock of the measurement consumer and exports under the `_export_lock` of the reader, which are two different locks.
- `Dockerfile`: `ENTRYPOINT ["devops"]` with no init. pid_namespaces(7): the init process of a namespace gets only the signals for which it has a handler, except SIGKILL and SIGSTOP.

## Existing Tool Considered
- The `PeriodicExportingMetricReader` of the OpenTelemetry SDK, with its variable `OTEL_METRIC_EXPORT_INTERVAL`. The change keeps the variable and its default, and does not use the reader. The reader collects outside the lock that holds its export. So a tick of the reader and the flush of the Service after a round can collect in one order and export in the other order, and the collector then drops the earlier delta as out of order. The `_flush_lock` of the tracer already holds the collection and the export together. The small thread that calls `flush()` instead costs about 40 lines, about 30000 tokens and 1 hour to build, and one test module to keep.
- The Python `signal` module for the handler. No library gives "export, then do what the handler before did".
- The change deletes no internal code.
