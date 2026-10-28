# Proposal

## Why

Issue #1319: the tracer sends OTLP through private methods, so a test can read what it exports only by patching them, and the export ignores the egress check.

- `OTelTelemetryClient` posted traces, metrics and logs through `_send_payload` and `_send_payload_sync`, over a raw `httpx2.Client` that `_get_http_client` cached. The collector probe `test_connection` opened its own `httpx2.Client`, or a raw socket for gRPC. Neither client went through the egress-checked factory (`devops_cli.http.client`), which #2437 waits on.
- `_get_grpc_exporter` had no caller in `src`. A gRPC protocol, or an endpoint with the `grpc` scheme or port 4317, still posted OTLP/HTTP JSON to that port, and every export failed with only a count. `opentelemetry-exporter-otlp-proto-grpc` was a direct dependency for that dead code.
- 17 test files patched or called the private export methods, and the `captured` fixture (`tests/support/telemetry_capture.py`) patched `_send_payload` too.

## What Changes

- `src/devops_cli/telemetry/exporter.py` is the edge between the tracer and the collector. The `OtlpExporter` Protocol names what the tracer needs: export one signal's encoded request (`OtlpSignal`: `/v1/traces`, `/v1/metrics`, `/v1/logs`) and probe the collector.
- `HttpOtlpExporter` is the real exporter. It posts to the collector through `new_http_client` at the private egress level, as internal infrastructure, and turns each failure into an `OtlpExportError` with a fixed text: `HTTP <status>`, "Cannot connect to the collector" or "The collector did not answer in time". The probe posts an empty trace export request, which the collector answers and does not store.
- `otlp_exporter(endpoint, protocol)` is the one place that builds the real exporter. A protocol other than `http/json` or `http/protobuf` in `OTEL_EXPORTER_OTLP_PROTOCOL`, or with no protocol an endpoint with the `grpc` scheme or port 4317, raises `OtlpProtocolError` with a message that names the setting.
- `OTelTelemetryClient` takes an `exporter`. The executor, the dry-run suppression and the success and failure counters stay in the client. `get_tracer()` builds the exporter through `otlp_exporter`; on `OtlpProtocolError` it logs a warning, turns export off and gives the tracer a `RefusedExporter`, whose probe reports the message. `install_exporter` and `remove_exporter` put an exporter in place of the configured one, with export on.
- Deleted: `_get_grpc_exporter`, `_grpc_exporter`, `_get_http_client`, the raw-socket gRPC probe and the `protocol` attribute. `opentelemetry-exporter-otlp-proto-grpc` leaves the direct dependencies, and `opentelemetry-sdk`, which `src` imports for the `MeterProvider`, joins them at the same version.
- Tests: `tests/support/fakes/otlp.py` holds `FakeCollector`, the OTLP fake, behind its `otlp` fixture. The contract suite `tests/telemetry/test_otlp_exporter_contract.py` holds it to `HttpOtlpExporter`. The export tests of `tests/test_telemetry_collector_export.py` and `tests/test_telemetry.py`, and every user of the `captured` fixture, use the fake. `tests/support/telemetry_capture.py` is deleted.
- The export reaches the collector over the egress-checked client, a gRPC setting fails with a message, and the probe sends no ping span, so the change carries a spec delta: the new capability `otlp-export`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `otlp-export`: how devops-cli sends OTLP to the collector, how it reports an export that fails, how it probes the collector, and how it refuses gRPC.

## Impact

- `src/devops_cli/telemetry/exporter.py` (new), `src/devops_cli/telemetry/tracer.py`, `src/devops_cli/exceptions/telemetry.py`, `pyproject.toml`, `uv.lock`.
- `tests/support/fakes/otlp.py` (new), `tests/telemetry/` (new), `tests/conftest.py`, the test files that used the `captured` fixture or patched the deleted names, and `tests/fixtures/swallowed_failures_ceilings.json`.
- `docs/TESTING.md` and the OpenTelemetry pages of the knowledge base.

## Feasibility

- On `origin/main` 0379f21e, `telemetry/tracer.py` posted every signal through `_send_payload_sync` with `httpx2.Client(timeout=...)`, probed with a second `httpx2.Client` or `socket.create_connection`, and `_get_grpc_exporter` had no caller (`rg -n '_get_grpc_exporter' src`). `git grep` found 17 test files that reach `_send_payload`, `_send_payload_sync`, `_get_http_client` or `_grpc_exporter`, 9 that use the `captured` fixture and 4 that build its `Captured` sink by hand.
- `new_http_client(level=EgressLevel.PRIVATE)` (`devops_cli.http.client`) exists, as #2430 moved other clients onto it. #2437 names #1319 as the item that moves the telemetry clients.
- `devops_cli.http` imports the tracer through `http.broker` and `telemetry.context`, so the exporter imports `devops_cli.http` inside the functions that use it, as the tracer did.
- `opentelemetry-sdk` 1.45.1 is installed through `logfire`, and `src` imports `opentelemetry.sdk.metrics`. `uv lock` with the swap removes only `opentelemetry-exporter-otlp-proto-grpc`; `grpcio` stays for other packages.
- The hermetic floor lets a test reach a loopback port that a socket in the test process binds (`tests/conftest.py`, `prevent_external_network_calls`), so the contract suite's real side posts to its own `ThreadingHTTPServer`, and to `refusing_port` for a collector that does not run.
- Owner order: #1307 lists #1312 as the only hard predecessor of #1319, and #1312 is closed. No other open item owns this work. #1334 moves the other telemetry, server, UI and output tests onto the fake.

## Existing Tool Considered

- The OpenTelemetry SDK's `InMemorySpanExporter` and `InMemoryMetricReader`: the tracer already reads its metrics through `InMemoryMetricReader`, but its spans and logs are not SDK objects, so the SDK's in-memory exporter cannot see them, and neither in-memory double answers with a failure or a probe result. The fake records the requests that the collector receives instead, and the contract suite holds it to the real exporter.
- The SDK's own OTLP/HTTP exporters (`opentelemetry-exporter-otlp-proto-http`) take only a `requests.Session`, so they would bypass the egress-checked client.
- The 2026-10-08 amendment on #1319 asks for the SDK's `SpanExporter` and `MetricExporter`, with the official protobuf encoders. That needs the spans to be SDK spans, which is the larger refactor the amendment recorded beside it. It is filed as #2536, which builds on this seam. This change builds a Protocol of three methods, a real exporter of about 100 lines, a fake and a contract suite, about 40k tokens and half a day, and deletes `_get_grpc_exporter`, `_get_http_client`, the raw-socket probe, `tests/support/telemetry_capture.py` and the private-method patches of the migrated tests.
