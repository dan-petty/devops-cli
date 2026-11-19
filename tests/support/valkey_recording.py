"""The replies of a real Valkey server to the contract scenarios, recorded (#4557).

`record_scenarios` runs each scenario of `tests/support/valkey_scenarios.py` through a valkey-py
client whose port is a recording proxy in front of a real `valkey-server`. The proxy sends each
command on to the server and keeps the command (the words of its RESP array) and the reply (the
RESP2 text that the server sent). Each scenario gets a new client, so its exchanges start with the
handshake of valkey-py: `CLIENT SETINFO LIB-NAME` and `LIB-VER`. The record keeps the version of
the server and of valkey-py, and goes to `tests/fixtures/valkey/recorded_exchanges.json`, which
`RecordedValkey` replays.

`SCRIPT FLUSH` in a scenario removes each script of the server. Never record from a Valkey that
holds other data, such as a Valkey of the cluster. `record_scenarios` connects only to 127.0.0.1
and refuses a server that holds a key. Start a new, empty server with no persistence, and make it
available on a loopback port. Use one of these two ways.

On a Debian workstation, the Debian packages give a server with no install. The server needs
`liblzf.so.1`, which a Debian host often does not have, so download `liblzf1` too. Unpack the
packages in an empty scratch directory, and give the loader their library directory (on amd64):

    apt-get download valkey-server valkey-tools liblzf1
    for f in *.deb; do dpkg-deb -x "$f" root; done
    LD_LIBRARY_PATH=root/usr/lib/x86_64-linux-gnu root/usr/bin/valkey-server --bind 127.0.0.1 \
        --port 6390 --save '' --appendonly no --protected-mode yes

In a cluster, start a temporary Pod of the official image `valkey/valkey` and forward a loopback
port to it. The Pod must be new and empty. Never forward to a Valkey of the cluster that holds
data. Give the Pod the security context of `k8s/llm/valkey-devops.yaml` when the namespace
enforces one:

    kubectl -n <namespace> run valkey-contract-record --image=valkey/valkey:<tag> \
        --restart=Never -- valkey-server --bind 127.0.0.1 --save '' --appendonly no \
        --protected-mode yes
    kubectl -n <namespace> port-forward pod/valkey-contract-record 6390:6379

Then record:

    uv run python -c "from tests.support.valkey_recording import record_scenarios; record_scenarios(6390)"

Then stop the server. For the Pod, stop the port-forward and delete the Pod:

    kubectl -n <namespace> delete pod valkey-contract-record

Record again when the valkey-py pin in `uv.lock` changes, or when a scenario changes. In a new
record, only the `PTTL` reply of `lock_lifecycle` changes by some milliseconds. It is the time
between two commands, and the scenario keeps only a bounded fact of it.
`tests/valkey/test_valkey_contract.py` fails until the record is of the locked valkey-py.
"""

from __future__ import annotations

import json
import socket
import socketserver
import threading
from pathlib import Path
from typing import Any

import valkey

from tests.support.valkey_replay import (
    LOOPBACK,
    RECORD,
    SHUTDOWN_POLL_SECONDS,
    pack_command,
    read_command,
    read_reply,
)
from tests.support.valkey_scenarios import SCENARIOS, ValkeyScenario

# How long the proxy and the clients wait for the server's reply.
SERVER_READ_SECONDS = 10.0


class _RecordingProxy(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """A loopback port that sends each command on to the server and keeps each exchange."""

    daemon_threads = True

    def __init__(self, server_port: int) -> None:
        super().__init__((LOOPBACK, 0), _ProxyHandler)
        self.server_port = server_port
        self.exchanges: list[dict[str, Any]] = []
        self._thread = threading.Thread(
            target=self.serve_forever,
            kwargs={"poll_interval": SHUTDOWN_POLL_SECONDS},
            name="valkey-recording-proxy",
            daemon=True,
        )

    @property
    def port(self) -> int:
        port: int = self.server_address[1]
        return port

    def __enter__(self) -> _RecordingProxy:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.shutdown()
        self.server_close()
        self._thread.join()


class _ProxyHandler(socketserver.StreamRequestHandler):
    server: _RecordingProxy

    def handle(self) -> None:
        address = (LOOPBACK, self.server.server_port)
        with (
            socket.create_connection(address, timeout=SERVER_READ_SECONDS) as upstream,
            upstream.makefile("rb") as replies,
        ):
            while (command := read_command(self.rfile)) is not None:
                upstream.sendall(pack_command(command))
                reply = read_reply(replies)
                # The exchange is kept before the client reads the reply, so the record is
                # complete once the client has its last reply.
                self.server.exchanges.append({"command": command, "reply": reply.decode()})
                self.wfile.write(reply)


def _client(port: int) -> valkey.Valkey:
    return valkey.Valkey(
        host=LOOPBACK, port=port, decode_responses=True, socket_timeout=SERVER_READ_SECONDS
    )


def _record_scenario(scenario: ValkeyScenario, server_port: int) -> list[dict[str, Any]]:
    """Run one scenario through the proxy on a new client, and return its exchanges."""
    with _RecordingProxy(server_port) as proxy:
        client = _client(proxy.port)
        try:
            scenario.run(client)
        finally:
            client.close()
        return list(proxy.exchanges)


def _server_version(port: int) -> str:
    """The version of the server, refused when the server holds a key."""
    direct = _client(port)
    try:
        # The keyspace section names each database that holds a key, so it is empty on an empty server.
        if direct.info("keyspace"):
            raise RuntimeError(f"the Valkey on port {port} holds keys; record from an empty one")
        version: str = direct.info("server")["valkey_version"]
    finally:
        direct.close()
    return version


def record_scenarios(port: int) -> None:
    """Record every scenario from the empty Valkey on a loopback port, and write the record."""
    server_version = _server_version(port)
    record = {
        "valkey_py": valkey.__version__,
        "server": {"valkey_version": server_version},
        "scenarios": {s.name: _record_scenario(s, port) for s in SCENARIOS},
    }
    Path(str(RECORD)).parent.mkdir(parents=True, exist_ok=True)
    Path(str(RECORD)).write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
