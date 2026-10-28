"""The edge between the tracer and the OpenTelemetry collector (#1319).

The tracer builds each signal's OTLP export request and queues it on its own executor. An
`OtlpExporter` sends the encoded request to the collector and probes whether the collector
answers. `HttpOtlpExporter` is the one real exporter: it posts to the collector's OTLP/HTTP
paths through the egress-checked client (`devops_cli.http.client`) at the private level, as
internal infrastructure. The `devops_cli.http` imports sit in the functions that use them:
that package imports the tracer, which imports this module. devops-cli sends no OTLP over gRPC: `otlp_exporter` refuses a gRPC
protocol or endpoint with an error that names the setting, instead of posting HTTP to a gRPC
port.

The exporter turns every failure into an `OtlpExportError` whose message is the text the tracer
records in `last_export_error`, so a test double gives the same text as the real exporter
(`tests/telemetry/test_otlp_exporter_contract.py`).
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import httpx2

from devops_cli.config.defaults import DEFAULT_OTEL_HTTP_TIMEOUT_SECONDS
from devops_cli.exceptions.telemetry import OtlpExportError, OtlpProtocolError

JSON_CONTENT_TYPE = "application/json"
CONNECT_FAILED = "Cannot connect to the collector"
NO_ANSWER_IN_TIME = "The collector did not answer in time"
PROBE_FAILED = "Connection probe failed"
# The protocols of the OpenTelemetry specification that devops-cli sends: both are OTLP/HTTP.
_HTTP_PROTOCOLS = frozenset({"http/json", "http/protobuf"})
_GRPC_PORT = 4317
# An export request with no data is valid OTLP: the collector answers it and stores nothing.
_EMPTY_TRACES_REQUEST = b'{"resourceSpans":[]}'


class OtlpSignal(StrEnum):
    """An OTLP signal, as the path of the collector's OTLP/HTTP receiver for it."""

    TRACES = "/v1/traces"
    METRICS = "/v1/metrics"
    LOGS = "/v1/logs"


@dataclass(frozen=True)
class ProbeResult:
    """Whether the collector answered a probe, and how."""

    reachable: bool
    detail: str


class OtlpExporter(Protocol):
    """What the tracer needs of a collector: take one signal's export request, and answer a
    probe."""

    endpoint: str

    def export(self, signal: OtlpSignal, body: bytes, content_type: str) -> None:
        """Send one encoded export request; raise `OtlpExportError` when the collector does not
        take it."""
        ...

    def probe(self, timeout: float) -> ProbeResult:
        """Report whether the collector answers within `timeout` seconds."""
        ...

    def close(self) -> None:
        """Release the connections the exporter holds."""
        ...


def json_body(payload: object) -> bytes:
    """Encode an OTLP/JSON export request as httpx2 encodes a JSON body."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )


def status_failure(status_code: int) -> str:
    """The failure text of an export that the collector answered with `status_code`."""
    return f"HTTP {status_code}"


class HttpOtlpExporter:
    """Posts OTLP export requests to the collector's OTLP/HTTP receiver."""

    def __init__(
        self, endpoint: str, *, timeout: float = DEFAULT_OTEL_HTTP_TIMEOUT_SECONDS
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self._timeout = timeout
        self._client: httpx2.Client | None = None
        self._lock = threading.Lock()

    def _shared_client(self) -> httpx2.Client:
        with self._lock:
            if self._client is None or self._client.is_closed:
                self._client = _collector_client(self._timeout)
            return self._client

    def export(self, signal: OtlpSignal, body: bytes, content_type: str) -> None:
        try:
            response = self._shared_client().post(
                f"{self.endpoint}{signal}", content=body, headers={"Content-Type": content_type}
            )
        except httpx2.TimeoutException as exc:
            raise OtlpExportError(NO_ANSWER_IN_TIME) from exc
        except httpx2.ConnectError as exc:
            raise OtlpExportError(CONNECT_FAILED) from exc
        if not response.is_success:
            raise OtlpExportError(status_failure(response.status_code))

    def probe(self, timeout: float) -> ProbeResult:
        try:
            with _collector_client(timeout) as client:
                response = client.post(
                    f"{self.endpoint}{OtlpSignal.TRACES}",
                    content=_EMPTY_TRACES_REQUEST,
                    headers={"Content-Type": JSON_CONTENT_TYPE},
                )
        except httpx2.HTTPError:
            return ProbeResult(False, PROBE_FAILED)
        if response.is_success:
            return ProbeResult(True, f"HTTP {response.status_code} OK")
        return ProbeResult(False, f"HTTP {response.status_code} probe failed")

    def close(self) -> None:
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None


class RefusedExporter:
    """The exporter of a configuration that `otlp_exporter` refused: it sends nothing, and every
    export and probe reports why."""

    def __init__(self, endpoint: str, reason: str) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.reason = reason

    def export(self, signal: OtlpSignal, body: bytes, content_type: str) -> None:
        raise OtlpExportError(self.reason)

    def probe(self, timeout: float) -> ProbeResult:
        return ProbeResult(False, self.reason)

    def close(self) -> None:
        return None


def _collector_client(read_timeout: float) -> httpx2.Client:
    """An egress-checked client for the collector, with a short connect and pool wait, so an
    absent collector costs the command at most a second."""
    from devops_cli.http.client import new_http_client
    from devops_cli.http.egress import EgressLevel

    return new_http_client(
        level=EgressLevel.PRIVATE,
        timeout=httpx2.Timeout(connect=1.0, read=read_timeout, write=read_timeout, pool=1.0),
    )


def _names_grpc(endpoint: str) -> bool:
    """Whether an endpoint asks for gRPC: the `grpc` scheme or the OTLP gRPC port."""
    from devops_cli.http.urls import read_url_or_authority

    target = read_url_or_authority(endpoint)
    if target is None:
        return False
    try:
        port = target.port
    except ValueError:
        port = None
    return target.scheme.lower() == "grpc" or port == _GRPC_PORT


def otlp_exporter(endpoint: str, protocol: str | None = None) -> HttpOtlpExporter:
    """The exporter for the collector at `endpoint`.

    `protocol` is `OTEL_EXPORTER_OTLP_PROTOCOL` unless given. A gRPC protocol, or with no
    protocol an endpoint with the `grpc` scheme or port 4317, raises `OtlpProtocolError`.
    """
    chosen = protocol or os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL")
    if chosen and chosen.lower() not in _HTTP_PROTOCOLS:
        raise OtlpProtocolError(
            f"OTEL_EXPORTER_OTLP_PROTOCOL is {chosen!r}, but devops-cli sends OTLP over HTTP "
            "only. Set it to http/protobuf or http/json, or remove it."
        )
    if not chosen and _names_grpc(endpoint):
        raise OtlpProtocolError(
            "The telemetry endpoint (telemetry.endpoint or OTEL_EXPORTER_OTLP_ENDPOINT) names "
            "OTLP over gRPC, with the grpc scheme or port 4317, but devops-cli sends OTLP over "
            "HTTP only. Set it to the collector's OTLP/HTTP address, port 4318 by default."
        )
    return HttpOtlpExporter(endpoint)


__all__ = [
    "CONNECT_FAILED",
    "JSON_CONTENT_TYPE",
    "NO_ANSWER_IN_TIME",
    "PROBE_FAILED",
    "HttpOtlpExporter",
    "OtlpExporter",
    "OtlpSignal",
    "ProbeResult",
    "RefusedExporter",
    "json_body",
    "otlp_exporter",
    "status_failure",
]
