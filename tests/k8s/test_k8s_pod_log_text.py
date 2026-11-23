"""The text of a pod log, read through the real Kubernetes client (#3091).

`kubernetes` 37 decodes the body of `read_namespaced_pod_log` to `str`. The client reads
a loopback server here, with no fake between the call and the bytes.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from kubernetes import client

from devops_cli.k8s.service import read_pod_log_text

LOGS = {
    "plain": "Tool call: read_file, ok.\n\N{CHECK MARK} Took 1 item(s).\n".encode(),
    "json": b'{"k": 1}',
}


class _LogHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = LOGS[self.path.split("/")[-2]]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Write no line to the test output."""


@pytest.fixture
def core() -> Iterator[client.CoreV1Api]:
    server = HTTPServer(("127.0.0.1", 0), _LogHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    configuration = client.Configuration()
    configuration.host = f"http://127.0.0.1:{server.server_port}"
    try:
        yield client.CoreV1Api(client.ApiClient(configuration))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_a_plain_read_of_the_client_gives_the_text_of_the_bytes(
    core: client.CoreV1Api,
) -> None:
    """The client decodes the body as text with line breaks and UTF-8 characters."""
    shown = core.read_namespaced_pod_log("plain", "devops")

    assert shown.startswith("Tool call: read_file, ok.\n")


@pytest.mark.parametrize(
    ("pod", "expected"),
    [
        ("plain", "Tool call: read_file, ok.\n\N{CHECK MARK} Took 1 item(s).\n"),
        ("json", '{"k": 1}'),
    ],
)
def test_the_log_is_the_text_the_pod_wrote(core: client.CoreV1Api, pod: str, expected: str) -> None:
    assert read_pod_log_text(core, pod, "devops", tail_lines=40) == expected
