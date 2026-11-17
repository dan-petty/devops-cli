"""The contract of the server start seam (#3885).

`devops serve` starts the ASGI server through `devops_cli.server.start`, so a test installs a
`FakeServerStarter` and reads the start call and the app that the fake built. This module holds
the fake and the real `UvicornStarter` to the same call: the real starter serves one request on a
loopback port that the test process binds and stops, and the fake records the same host, port,
factory flag and log config.
"""

from __future__ import annotations

import socket
import threading
from typing import Any

import httpx2
import uvicorn

from tests.support.fakes.server import FakeServerStarter
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS, wait_until


def service_app() -> Any:
    """The app factory of a start that sets `factory`: uvicorn builds the app from it."""
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_the_real_starter_serves_a_request_on_a_loopback_port_and_stops() -> None:
    """The fake and the real starter take one start call, and the real one serves a request.

    The test process binds the loopback socket, so the network floor lets the request through and
    the start cannot take a port of the workstation. `remove_server_starter` gives
    `get_server_starter` the real starter again, which serves the request and stops.
    """
    from devops_cli.server.start import (
        UvicornStarter,
        get_server_starter,
        install_server_starter,
        remove_server_starter,
    )

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    fake = FakeServerStarter()
    install_server_starter(fake)
    try:
        assert get_server_starter() is fake
        get_server_starter().start(
            service_app, host="127.0.0.1", port=port, factory=True, log_config=None
        )
    finally:
        remove_server_starter()

    starter = get_server_starter()
    assert isinstance(starter, UvicornStarter)
    assert (len(fake.calls), len(fake.apps)) == (1, 1)
    call = fake.calls[0]
    config = starter.config(call)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        assert wait_until(lambda: server.started)
        with httpx2.Client(trust_env=False) as client:
            response = client.get(f"http://127.0.0.1:{port}/healthz")
    finally:
        server.should_exit = True
        thread.join(THREAD_HANDOFF_BOUND_SECONDS)
        listener.close()

    assert (
        response.status_code,
        response.json(),
        (call.host, call.port, call.factory, call.log_config),
        (config.host, config.port, config.factory, config.log_config),
        thread.is_alive(),
    ) == (
        200,
        {"status": "ok"},
        ("127.0.0.1", port, True, None),
        ("127.0.0.1", port, True, None),
        False,
    )
