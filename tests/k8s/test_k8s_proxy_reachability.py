"""`configure-urls --addressing proxy` writes only the addresses that the API server reaches (#1634).

The API server dials a Service's endpoints from its own node. A NetworkPolicy that admits only
pods refuses that dial for a pod on another node, and the API server then answers 503 with a
`Status` of reason `ServiceUnavailable`. A loopback HTTP server stands in for the API server: the
run's throwaway kubeconfig points at it, and it answers the version probe, the Service listings
and the proxied GET of each Service root, as the real API server does.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.k8s.service_http import reaches_service
from tests.support.waits import POLL_INTERVAL_SECONDS

CONTEXT = "loopback"
VERSION = {
    "major": "1",
    "minor": "31",
    "gitVersion": "v1.31.4",
    "gitCommit": "0",
    "gitTreeState": "clean",
    "buildDate": "2026-01-01T00:00:00Z",
    "goVersion": "go1.23",
    "compiler": "gc",
    "platform": "linux/amd64",
}
DIAL_FAILURE = {
    "kind": "Status",
    "apiVersion": "v1",
    "metadata": {},
    "status": "Failure",
    "message": "error trying to reach service: dial tcp 192.0.2.10:3000: connect: connection refused",
    "reason": "ServiceUnavailable",
    "code": 503,
}
# The infra stack's Services, by namespace: name and port.
SERVICES: dict[str, list[tuple[str, int]]] = {
    "argocd": [("argocd-server", 80)],
    "monitoring": [("grafana", 80), ("prometheus-server", 9090), ("pyroscope", 4040)],
    "otel": [("tempo", 3200)],
    "llm": [("open-webui", 80), ("qdrant", 6333)],
}


@dataclass
class ApiServer:
    """What the stand-in API server answers, and the paths it was asked for."""

    url: str
    unreachable: set[str] = field(default_factory=set)
    backend_status: dict[str, int] = field(default_factory=dict)
    paths: list[str] = field(default_factory=list)


def _handler(server: ApiServer) -> type[BaseHTTPRequestHandler]:
    """A request handler that answers as the API server does for `server`."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            server.paths.append(self.path)
            parts = self.path.split("?")[0].strip("/").split("/")
            if parts == ["version"]:
                self._json(200, VERSION)
            elif len(parts) == 5 and parts[:2] == ["api", "v1"] and parts[4] == "services":
                self._json(200, _service_list(parts[3]))
            elif len(parts) == 7 and parts[4] == "services" and parts[6] == "proxy":
                target = f"{parts[3]}/{parts[5]}"
                if target in server.unreachable:
                    self._json(503, DIAL_FAILURE)
                else:
                    self._json(server.backend_status.get(target, 302), {"from": "backend"})
            else:
                self._json(404, {"kind": "Status", "reason": "NotFound", "code": 404})

        def _json(self, status: int, body: dict[str, Any]) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            if status == 302:
                self.send_header("Location", f"{self.path}login")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:
            """Keep the test output free of the server's access log."""

    return Handler


def _service_list(namespace: str) -> dict[str, Any]:
    """The ServiceList of a namespace."""
    return {
        "kind": "ServiceList",
        "apiVersion": "v1",
        "metadata": {},
        "items": [
            {
                "metadata": {"name": name, "namespace": namespace},
                "spec": {"ports": [{"name": "http", "port": port, "protocol": "TCP"}]},
            }
            for name, port in SERVICES.get(namespace, [])
        ],
    }


@pytest.fixture
def api_server(
    config: Callable[..., Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[ApiServer]:
    """A loopback API server that a kubeconfig of the test and the configured context point at."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    server = ApiServer(url=f"http://127.0.0.1:{httpd.server_address[1]}")
    httpd.RequestHandlerClass = _handler(server)
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": POLL_INTERVAL_SECONDS}, daemon=True
    )
    thread.start()

    kubeconfig = tmp_path / "kubeconfig"
    monkeypatch.setenv("KUBECONFIG", str(kubeconfig))
    kubeconfig.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "v1",
                "kind": "Config",
                "clusters": [{"name": CONTEXT, "cluster": {"server": server.url}}],
                "users": [{"name": CONTEXT, "user": {"token": "test-token"}}],
                "contexts": [{"name": CONTEXT, "context": {"cluster": CONTEXT, "user": CONTEXT}}],
                "current-context": CONTEXT,
            }
        ),
        encoding="utf-8",
    )
    config(k8s={"context": CONTEXT})
    try:
        yield server
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.mark.parametrize(
    ("unreachable", "backend_status", "reached"),
    [
        (set(), 302, True),
        (set(), 503, True),
        ({"monitoring/grafana:80"}, 302, False),
    ],
    ids=["redirect", "backend-503", "dial-failure"],
)
def test_an_address_counts_as_reached_unless_the_api_server_cannot_dial_it(
    api_server: ApiServer, unreachable: set[str], backend_status: int, reached: bool
) -> None:
    """Any answer from the Service counts, its own 503 included; the API server's Status does not."""
    api_server.unreachable = unreachable
    api_server.backend_status = {"monitoring/grafana:80": backend_status}

    assert (
        reaches_service("k8s://monitoring/grafana:80", context=CONTEXT),
        api_server.paths,
    ) == (reached, ["/api/v1/namespaces/monitoring/services/grafana:80/proxy/"])


def _url(document: dict[str, Any], section: str) -> Any:
    """The `url` of a section of a config file."""
    return (document.get(section) or {}).get("url")


def test_proxy_mode_writes_only_the_addresses_the_api_server_reaches(
    api_server: ApiServer, cli: Callable[..., Any], config: Callable[..., Path]
) -> None:
    """Grafana, Prometheus, Pyroscope and Tempo run on a worker behind a perimeter, Argo CD does not.

    The command writes the Argo CD address, which loads again as written, and for each other
    Service it writes nothing and names the modes that reach it.
    """
    from devops_cli.config.settings import load_settings

    api_server.unreachable = {
        "monitoring/grafana:80",
        "monitoring/prometheus-server:9090",
        "monitoring/pyroscope:4040",
        "otel/tempo:3200",
    }
    before = yaml.safe_load(config().read_text(encoding="utf-8")) or {}

    result = cli("k8s", "configure-urls", "--addressing", "proxy", "--stack", "infra")

    after = yaml.safe_load(config().read_text(encoding="utf-8")) or {}
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        {
            section: _url(after, section)
            for section in ("argocd", "grafana", "prometheus", "tempo", "pyroscope")
        },
        load_settings().argocd.url,
        [
            key
            for key in ("argocd.url", "grafana.url", "prometheus.url", "tempo.url", "pyroscope.url")
            if f"Did not write {key}" in output
        ],
        "--addressing fqdn" in output,
    ) == (
        0,
        {
            "argocd": "k8s://argocd/argocd-server:80",
            **{
                section: _url(before, section)
                for section in ("grafana", "prometheus", "tempo", "pyroscope")
            },
        },
        "k8s://argocd/argocd-server:80",
        ["grafana.url", "prometheus.url", "tempo.url", "pyroscope.url"],
        True,
    )


def test_proxy_mode_writes_the_llm_address_that_answers(
    api_server: ApiServer, cli: Callable[..., Any], config: Callable[..., Path]
) -> None:
    """Qdrant answers through the API server and Open WebUI does not, so only Qdrant is written."""
    from devops_cli.config.settings import load_settings

    api_server.unreachable = {"llm/open-webui:80"}
    api_server.backend_status = {"llm/qdrant:6333": 200}
    before = yaml.safe_load(config().read_text(encoding="utf-8")) or {}

    result = cli("k8s", "configure-urls", "--addressing", "proxy", "--stack", "llm")

    after = yaml.safe_load(config().read_text(encoding="utf-8")) or {}
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        _url(after, "qdrant"),
        load_settings().qdrant.url,
        _url(after, "open_webui") == _url(before, "open_webui"),
        ["Did not write open_webui.url" in output, "Did not write qdrant.url" in output],
    ) == (0, "k8s://llm/qdrant:6333", "k8s://llm/qdrant:6333", True, [True, False])
