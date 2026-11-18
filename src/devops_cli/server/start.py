"""The one seam that starts the ASGI server of `devops serve` (#3885).

`devops serve` hands uvicorn the app, or the factory that builds it (`devops_cli.commands.serve`).
While the command called `uvicorn.run` itself, no test could see the app that uvicorn builds from a
factory, nor the host, the port and the log config of the start. `get_server_starter` gives the
process's starter, `UvicornStarter` calls `uvicorn.run`, and `install_server_starter` puts a fake in
its place until `remove_server_starter`, as `install_exporter` does for telemetry
(`devops_cli.telemetry.tracer`).

`StartCall` holds the target and the options of one start, so a fake records exactly what the
command asked for, and `UvicornStarter.config` gives the `uvicorn.Config` of that same call: a
contract test runs a `uvicorn.Server` on it and serves a request on a loopback port
(`tests/server/test_server_start_seam.py`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import uvicorn


@dataclass(frozen=True)
class StartCall:
    """One start of the ASGI server: the target and the options that uvicorn takes."""

    target: Any
    options: Mapping[str, Any] = field(default_factory=dict)

    @property
    def factory(self) -> bool:
        """Whether uvicorn builds the app from the target instead of taking the app itself."""
        return bool(self.options.get("factory", False))

    @property
    def host(self) -> str | None:
        """The host that the server binds, when the start names one."""
        host = self.options.get("host")
        return host if isinstance(host, str) else None

    @property
    def port(self) -> int | None:
        """The port that the server binds, when the start names one."""
        port = self.options.get("port")
        return port if isinstance(port, int) else None

    @property
    def log_config(self) -> dict[str, Any] | None:
        """The logging configuration that the server applies as it starts, if any."""
        log_config = self.options.get("log_config")
        return log_config if isinstance(log_config, dict) else None


class ServerStarter(Protocol):
    """What a command needs of the server: start it on the target with the options of the call."""

    def start(self, target: Any, /, **options: Any) -> None:
        """Start the server on `target`, with the options that uvicorn takes, and return when it
        stops."""
        ...


class UvicornStarter:
    """The real starter: `uvicorn.run` with the options that the caller passes."""

    def start(self, target: Any, /, **options: Any) -> None:
        """Serve `target` until the server stops."""
        import uvicorn

        uvicorn.run(target, **options)

    def config(self, call: StartCall) -> uvicorn.Config:
        """The `uvicorn.Config` of `call`, which a contract test runs a `uvicorn.Server` on."""
        import uvicorn

        return uvicorn.Config(call.target, **dict(call.options))


# The starter that `install_server_starter` put in place of the real one, if any.
_INSTALLED_STARTER: ServerStarter | None = None


def get_server_starter() -> ServerStarter:
    """The process's server starter: the installed one, else the real `UvicornStarter`."""
    if _INSTALLED_STARTER is not None:
        return _INSTALLED_STARTER
    return UvicornStarter()


def install_server_starter(starter: ServerStarter) -> None:
    """Start the process's ASGI server through `starter` until `remove_server_starter`.

    A test installs its fake this way, and the reset of the test floor removes it, so no fake
    reaches a later test.
    """
    global _INSTALLED_STARTER
    _INSTALLED_STARTER = starter


def remove_server_starter() -> None:
    """Remove the starter that `install_server_starter` installed: `get_server_starter` gives the
    real `UvicornStarter` again."""
    global _INSTALLED_STARTER
    _INSTALLED_STARTER = None
