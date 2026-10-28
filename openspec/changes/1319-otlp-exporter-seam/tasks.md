# Tasks

## 1. The collector edge is one exporter seam

- [x] Add the contract suite: the same cases on the OTLP fake and on `HttpOtlpExporter` over a loopback receiver (the path of each signal, a 2xx success, 4xx, 5xx and refused failures with one text, the probe of a reachable and an unreachable collector)
  - Verification: `uv run devops ci test tests/telemetry/test_otlp_exporter_contract.py`
- [x] Add failing tests: a gRPC protocol or endpoint is refused with its setting's name; a refused setting keeps the command running with export off; the process tracer exports to the configured collector; the `otlp` fixture reaches the fake; an installed exporter stays until it is removed
  - Verification: `uv run devops ci test tests/telemetry/test_otlp_export.py`
- [x] Add `telemetry/exporter.py` (`OtlpExporter`, `HttpOtlpExporter` on the egress-checked client, `RefusedExporter`, `otlp_exporter`), make the client take its exporter, add `install_exporter` and `remove_exporter`, and delete `_get_grpc_exporter`, `_get_http_client` and the raw-socket probe
  - Verification: `uv run devops ci test tests/telemetry/`
- [x] Swap `opentelemetry-exporter-otlp-proto-grpc` for `opentelemetry-sdk` in the direct dependencies, and lock
  - Verification: `uv run devops ci deps`

## 2. Tests read exports from the OTLP fake

- [x] Add `tests/support/fakes/otlp.py` with `FakeCollector` and the `otlp` fixture, and register `remove_exporter` in the floor's reset list
  - Verification: `uv run devops ci test tests/telemetry/ tests/invariants/`
- [x] Move the export tests of `tests/test_telemetry_collector_export.py` and `tests/test_telemetry.py`, and every user of the `captured` fixture, onto the fake; delete `tests/support/telemetry_capture.py` and the tests of the deleted gRPC and client code
  - Verification: `uv run devops ci test tests/test_telemetry.py tests/test_telemetry_collector_export.py tests/test_telemetry_instruments.py`
- [x] Lower the swallowed-failures ceiling of `telemetry/tracer.py`
  - Verification: `uv run devops ci test tests/test_swallowed_failures_ratchet.py`
- [x] Describe the fake in `docs/TESTING.md` and OTLP/HTTP-only export in the knowledge base, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 1319-otlp-exporter-seam`

## Workflow follow-up

- #2536: spans, metrics and logs are built and encoded by the OpenTelemetry SDK and sent as OTLP protobuf through this seam.
- #1334 and the other package items of #1307 move the remaining tests that patch `_send_payload` onto the fake.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
