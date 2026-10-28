"""The Engine API's answers to the contract scenarios, recorded from a real engine (#1316).

`record_scenarios` runs each scenario of `tests/support/docker_engine_scenarios.py` through a
`docker.DockerClient` whose socket is a recording proxy in front of a real engine. The proxy sends
each request on to the engine on a new connection and keeps the request line and the reply: its
status, its framing (a length, chunks, or `101 UPGRADED` and raw frames) and its body. A stream
that does not end by itself, such as `stats`, is kept to its first frames. The record goes to
`tests/fixtures/docker_engine/recorded_exchanges.json`, which `RecordedEngine` replays.

The engine can hold other work, so the recording changes and keeps only what the scenarios make:

- A prune is sent to the engine with a filter that matches nothing, so it removes nothing; the
  record keeps the request as the SDK sent it and the engine's reply, which has the same form.
- Every object a scenario makes is named with `devops-contract`. Lists of networks, volumes,
  images, containers and build cache keep those, the engine's own networks and `alpine`.
- `/info` and `/version` keep the facts the SDK callers read. Private IPv4 and IPv6 addresses
  become RFC 5737 and RFC 3849 addresses, and MAC addresses a fixed one. A build cache record's
  description, which names the steps of other builds, becomes its type.

Record again when the docker SDK pin in `uv.lock` changes, or a scenario changes, on a host with a
local Docker-compatible engine and the `alpine:3` image:

    uv run python -c "from tests.support.docker_engine_recording import record_scenarios; record_scenarios()"

It takes the engine's socket from `DOCKER_HOST` when that names a `unix://` socket, else
`/var/run/docker.sock`. `tests/docker/test_engine_contract.py` fails until the record is of the
locked SDK.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import os
import re
import shutil
import socket
import socketserver
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

import docker
import h11

from tests.support.docker_engine_replay import (
    RECORD,
    SHUTDOWN_POLL_SECONDS,
    events,
    read_request,
    send_reply,
    short_socket_dir,
)
from tests.support.docker_engine_scenarios import PREFIX, SCENARIOS, EngineScenario

# How many chunks of a stream that does not end by itself the record keeps.
STREAM_CHUNKS = 3
# How long the proxy waits for the engine's next bytes; an exec or a wait ends well before.
ENGINE_READ_SECONDS = 30.0
# The headers of a reply the record keeps.
KEPT_HEADERS = ("Content-Type", "Api-Version", "Ostype")
# A filter that matches no object, which the proxy adds to each prune.
NEVER_LABEL = "devops.contract.never=1"
_DEFAULT_NETWORKS = frozenset({"bridge", "host", "none"})
_INFO_KEYS = (
    "ServerVersion",
    "OSType",
    "Architecture",
    "Driver",
    "SecurityOptions",
    "PidsLimit",
    "IndexServerAddress",
)
_VERSION_KEYS = ("Version", "ApiVersion", "MinAPIVersion", "Os", "Arch")
_PRUNE = re.compile(r"^/v[\d.]+/(containers|networks|images|volumes|build)/prune$")
_STREAMING = re.compile(r"/containers/[^/]+/stats$")
_IPV4 = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")
_IPV6 = re.compile(r"\b(f[cd][0-9a-f]{2}|fe80)(:[0-9a-f]{0,4}){2,7}\b", re.IGNORECASE)
_MAC = re.compile(r"\b([0-9a-f]{2}:){5}[0-9a-f]{2}\b", re.IGNORECASE)


def _engine_socket() -> Path:
    """The socket of the local engine to record from."""
    host = os.environ.get("DOCKER_HOST", "")
    return (
        Path(host[len("unix://") :]) if host.startswith("unix://") else Path("/var/run/docker.sock")
    )


def _harmless(target: str) -> str:
    """The target to send to the engine: a prune gets a filter that matches nothing."""
    parts = urlsplit(target)
    match = _PRUNE.match(parts.path)
    if not match:
        return target
    query = {key: value for key, value in parse_qsl(parts.query) if key != "filters"}
    key = "id" if match.group(1) == "build" else "label"
    never = "devops-contract-never" if key == "id" else NEVER_LABEL
    query["filters"] = json.dumps({key: [never]})
    return f"{parts.path}?{urlencode(query)}"


class _Reply:
    """What the engine answered to one request."""

    def __init__(self) -> None:
        self.status = 0
        self.headers: dict[str, str] = {}
        self.chunked = False
        self.upgraded = False
        self.chunks: list[bytes] = []


def _read_reply(engine: socket.socket, conn: h11.Connection, streaming: bool) -> _Reply:
    """Read the engine's reply, up to `STREAM_CHUNKS` chunks of a stream that does not end."""
    reply = _Reply()
    for event in events(conn, engine):
        if isinstance(event, h11.InformationalResponse) and event.status_code == 101:
            reply.status, reply.upgraded = 101, True
            reply.headers = _kept(event.headers)
            reply.chunks = [conn.trailing_data[0], *_read_raw(engine)]
            return reply
        if isinstance(event, h11.Response):
            reply.status, reply.headers = event.status_code, _kept(event.headers)
            reply.chunked = _is_chunked(event.headers)
            continue
        if isinstance(event, h11.Data):
            reply.chunks.append(bytes(event.data))
            if streaming and len(reply.chunks) >= STREAM_CHUNKS:
                return reply
            continue
        return reply
    return reply


def _is_chunked(headers: list[tuple[bytes, bytes]]) -> bool:
    """Whether a reply's body comes in chunks."""
    return any(
        name.lower() == b"transfer-encoding" and b"chunked" in value.lower()
        for name, value in headers
    )


def _read_raw(engine: socket.socket) -> list[bytes]:
    """The raw frames after `101 UPGRADED`, until the engine closes the connection."""
    chunks = []
    while data := engine.recv(65_536):
        chunks.append(data)
    return chunks


def _kept(headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    """The reply headers the record keeps."""
    kept = {name.lower(): name for name in KEPT_HEADERS}
    return {
        kept[name.decode().lower()]: value.decode()
        for name, value in headers
        if name.decode().lower() in kept
    }


class _RecordingProxy:
    """A socket in front of the engine that keeps each exchange."""

    def __init__(self, engine: Path) -> None:
        self._engine = engine
        self._dir = short_socket_dir("dkr")
        self.path = self._dir / "proxy.sock"
        self.exchanges: list[dict[str, Any]] = []
        self._server = _ProxyServer(self.path, self)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": SHUTDOWN_POLL_SECONDS},
            daemon=True,
        )

    def forward(self, request: h11.Request, body: bytes) -> dict[str, Any]:
        """Send a request to the engine on a new connection, and keep the exchange."""
        target = request.target.decode()
        upgrade = any(name.lower() == b"upgrade" for name, _ in request.headers)
        headers = [(n, v) for n, v in request.headers if n.lower() != b"connection"]
        headers.append((b"Connection", b"Upgrade" if upgrade else b"close"))
        conn = h11.Connection(h11.CLIENT)
        with socket.socket(socket.AF_UNIX) as engine:
            engine.settimeout(ENGINE_READ_SECONDS)
            engine.connect(str(self._engine))
            engine.sendall(
                conn.send(
                    h11.Request(method=request.method, target=_harmless(target), headers=headers)
                )
            )
            if body:
                engine.sendall(conn.send(h11.Data(data=body)))
            engine.sendall(conn.send(h11.EndOfMessage()))
            reply = _read_reply(
                engine, conn, streaming=bool(_STREAMING.search(urlsplit(target).path))
            )
        exchange = _exchange(request.method.decode(), target, reply)
        self.exchanges.append(exchange)
        return exchange

    def __enter__(self) -> _RecordingProxy:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
        shutil.rmtree(self._dir, ignore_errors=True)


class _ProxyServer(socketserver.ThreadingUnixStreamServer):
    def __init__(self, path: Path, proxy: _RecordingProxy) -> None:
        super().__init__(str(path), _ProxyHandler)
        self.proxy = proxy


class _ProxyHandler(socketserver.BaseRequestHandler):
    server: _ProxyServer

    def handle(self) -> None:
        proxy = self.server.proxy
        conn = h11.Connection(h11.SERVER)
        while True:
            request, body = read_request(conn, self.request)
            if request is None:
                return
            if not send_reply(conn, self.request, proxy.forward(request, body)):
                return
            conn.start_next_cycle()


def _exchange(method: str, target: str, reply: _Reply) -> dict[str, Any]:
    """One recorded exchange, with its body in the form `RecordedEngine` sends again."""
    framing = "upgrade" if reply.upgraded else "chunked" if reply.chunked else "length"
    return {
        "method": method,
        "target": target,
        "status": reply.status,
        "headers": reply.headers,
        "framing": framing,
        "body": _body(reply),
    }


def _body(reply: _Reply) -> dict[str, Any] | None:
    """The reply body: one JSON document, the JSON entries of a stream, text, or base64 frames.

    The engine sends a large JSON document in chunks too, so the form comes from the body.
    """
    data = b"".join(reply.chunks)
    if not data:
        return None
    content_type = reply.headers.get("Content-Type", "")
    if "json" in content_type and not reply.upgraded:
        lines = [json.loads(line) for line in data.splitlines() if line.strip()]
        if len(lines) == 1:
            return {"kind": "json", "value": lines[0]}
        return {"kind": "json_lines", "value": lines}
    if content_type.startswith("text/"):
        return {"kind": "text", "value": data.decode()}
    return {"kind": "base64", "value": base64.b64encode(data).decode()}


# -- Scrubbing ---------------------------------------------------------------------


class _Addresses:
    """Private addresses, each replaced by one documentation address."""

    def __init__(self) -> None:
        self._v4: dict[str, str] = {}
        self._v6: dict[str, str] = {}

    def ipv4(self, match: re.Match[str]) -> str:
        text = match.group(1)
        try:
            address = ipaddress.IPv4Address(text)
        except ValueError:
            return text
        if not address.is_private or address.is_loopback:
            return text
        return self._v4.setdefault(text, f"192.0.2.{len(self._v4) + 1}")

    def ipv6(self, match: re.Match[str]) -> str:
        return self._v6.setdefault(match.group(0), f"2001:db8::{len(self._v6) + 1:x}")


def _scrub_text(text: str, addresses: _Addresses) -> str:
    text = _IPV4.sub(addresses.ipv4, text)
    text = _IPV6.sub(addresses.ipv6, text)
    return _MAC.sub("02:42:c0:00:02:01", text)


def _scrub_value(value: Any, addresses: _Addresses) -> Any:
    if isinstance(value, str):
        return _scrub_text(value, addresses)
    if isinstance(value, list):
        return [_scrub_value(item, addresses) for item in value]
    if isinstance(value, dict):
        return {
            _scrub_text(key, addresses): _scrub_value(item, addresses)
            for key, item in value.items()
        }
    return value


def _ours(name: str) -> bool:
    return PREFIX in name


def _keep_info(info: dict[str, Any]) -> dict[str, Any]:
    kept = {key: info[key] for key in _INFO_KEYS if key in info}
    kept["Name"] = "engine.example.com"
    kept["RegistryConfig"] = {"Mirrors": [], "IndexConfigs": {}}
    return kept


def _keep_version(version: dict[str, Any]) -> dict[str, Any]:
    kept = {key: version[key] for key in _VERSION_KEYS if key in version}
    kept["Components"] = [
        {"Name": part.get("Name"), "Version": part.get("Version")}
        for part in version.get("Components") or []
    ]
    return kept


def _keep_networks(networks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [n for n in networks if n.get("Name") in _DEFAULT_NETWORKS or _ours(n.get("Name", ""))]


def _keep_volumes(reply: dict[str, Any]) -> dict[str, Any]:
    return {
        "Volumes": [v for v in reply.get("Volumes") or [] if _ours(v.get("Name", ""))],
        "Warnings": reply.get("Warnings"),
    }


def _ours_or_alpine(image: dict[str, Any]) -> bool:
    tags = image.get("RepoTags") or []
    return any(tag.startswith("alpine:") or _ours(tag) for tag in tags)


def _keep_disk_usage(usage: dict[str, Any]) -> dict[str, Any]:
    cache = [
        {**entry, "Description": f"{entry.get('Type', 'regular')} record"}
        for entry in (usage.get("BuildCache") or [])[:2]
    ]
    return {
        **{key: value for key, value in usage.items() if key == "LayersSize"},
        "Images": [i for i in usage.get("Images") or [] if _ours_or_alpine(i)],
        "Containers": [
            c for c in usage.get("Containers") or [] if any(_ours(n) for n in c.get("Names") or [])
        ],
        "Volumes": [v for v in usage.get("Volumes") or [] if _ours(v.get("Name", ""))],
        "BuildCache": cache,
    }


_KEEP: tuple[tuple[re.Pattern[str], Callable[[Any], Any]], ...] = (
    (re.compile(r"/info$"), _keep_info),
    (re.compile(r"/version$"), _keep_version),
    (re.compile(r"/networks$"), _keep_networks),
    (re.compile(r"/volumes$"), _keep_volumes),
    (re.compile(r"/system/df$"), _keep_disk_usage),
)


def _scrub(exchange: dict[str, Any], addresses: _Addresses) -> dict[str, Any]:
    """An exchange with the engine's other work and its host's addresses taken out."""
    body = exchange["body"]
    if body is None or body["kind"] not in ("json", "json_lines"):
        return exchange
    value = body["value"]
    path = urlsplit(exchange["target"]).path
    for pattern, keep in _KEEP:
        if pattern.search(path) and exchange["status"] == 200:
            value = keep(value)
    return {**exchange, "body": {**body, "value": _scrub_value(value, addresses)}}


# -- Recording ---------------------------------------------------------------------


def _record_scenario(scenario: EngineScenario, engine: Path) -> list[dict[str, Any]]:
    """Run one scenario through the proxy, and return its scrubbed exchanges."""
    direct = docker.DockerClient(base_url=f"unix://{engine}")
    scenario.prepare(direct)
    try:
        with _RecordingProxy(engine) as proxy:
            client = docker.DockerClient(base_url=f"unix://{proxy.path}", timeout=60)
            scenario.run(client)
            client.close()
            exchanges = list(proxy.exchanges)
    finally:
        scenario.clean(direct)
        direct.close()
    addresses = _Addresses()
    return [_scrub(exchange, addresses) for exchange in exchanges]


def record_scenarios(engine: Path | None = None) -> None:
    """Record every scenario from a local engine, and write the record."""
    socket_path = engine or _engine_socket()
    direct = docker.DockerClient(base_url=f"unix://{socket_path}")
    try:
        version = _keep_version(direct.version())
    finally:
        direct.close()
    record = {
        "sdk": docker.__version__,
        "engine": version,
        "scenarios": {s.name: _record_scenario(s, socket_path) for s in SCENARIOS},
    }
    Path(str(RECORD)).parent.mkdir(parents=True, exist_ok=True)
    Path(str(RECORD)).write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
