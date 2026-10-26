# Design

## Architecture

`OTelTelemetryClient` delivers traces, metrics, and logs over background worker threads using `ContextPropagatingThreadPoolExecutor`.
Worker threads are named with the prefix `devops-otel`.
During application exit and test suite teardown, `shutdown()` and `reset_tracer()` clean up client resources.

## Thread Lifecycle and Shutdown Synchronization

1. In `OTelTelemetryClient.shutdown()`:
   - Call `self.flush()` to drain queued spans and metrics up to the drain timeout.
   - Call `self._executor.shutdown(wait=True, cancel_futures=True)` outside `self._client_lock`.
   - Acquiring no lock during thread waiting prevents deadlocks with worker threads calling `_get_http_client()`.
   - Worker threads join cleanly and terminate before `shutdown()` returns.
   - Acquire `with self._client_lock` to shut down the meter provider, gRPC exporter, and close the HTTP client.

2. In `OTelTelemetryClient._send_payload_sync()`:
   - Check `self.enabled` before and after acquiring the HTTP client.
   - Exit immediately if the client is disabled.

3. In `devops_cli.telemetry.logging_bridge._resolve_exporter()`:
   - Read `_GLOBAL_TRACER` directly.
   - Return `None` if `_GLOBAL_TRACER` is `None` or disabled.
   - Do not lazily instantiate a new tracer when exporting log records.

4. In `devops_cli.telemetry.tracer.reset_tracer()`:
   - Call `detach_otel_logging_handler()` first to detach the handler from the logger.
   - Set `_GLOBAL_TRACER` to `None`.
   - Call `dropped.shutdown()` to join all worker threads.
