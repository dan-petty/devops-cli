"""The network profile `kube-api` of the tool sandbox: a relay to the Kubernetes API server (#2132).

bubblewrap can keep the whole network of the host (`--share-net`) or give a sandbox a network
namespace with only a loopback device. It has no filter for one address. So the sandbox of a
kube-api run keeps `--unshare-all`, and reaches the API server of one context only through a relay
of programs that already do this work:

- `kubectl proxy`, outside the sandbox, on a Unix socket in a scratch directory. It reads the
  kubeconfig and the credentials of the user, sends each request to the API server of the context,
  and refuses the methods that change a resource and the paths that reach past the API server
  (`CONST_KUBE_API_REJECTED_METHODS`, `CONST_KUBE_API_REJECTED_PATHS`). `setpriv --pdeathsig KILL`
  of util-linux ends it with the shell that started it.
- `socat`, in the sandbox, on the loopback port `CONST_KUBE_API_RELAY_PORT`. It relays each
  connection to the socket, which the sandbox sees in the read-only bind of the scratch directory.
- A kubeconfig in the scratch directory that names the relay, the context and its namespace, and no
  credentials. `kubectl config view --minify` reads the context and its namespace from the
  kubeconfig of the user, as the proxy reads it. The tool reads the kubeconfig of the sandbox
  through `KUBECONFIG`. The credentials of the user stay outside the sandbox.

Two shell scripts connect these programs (`CONST_KUBE_API_HOST_SCRIPT` outside the sandbox and
`CONST_KUBE_API_SANDBOX_SCRIPT` in it). `SandboxToolExecutor` starts the whole run as one command
through `run_subprocess`, so the wall-clock limit of the request applies to it.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

import httpx2

from devops_cli.config.constants import (
    CONST_KUBE_API_HOST_SCRIPT,
    CONST_KUBE_API_KUBECONFIG_NAME,
    CONST_KUBE_API_PROGRAMS,
    CONST_KUBE_API_REJECTED_METHODS,
    CONST_KUBE_API_REJECTED_PATHS,
    CONST_KUBE_API_RELAY_HOST,
    CONST_KUBE_API_RELAY_PORT,
    CONST_KUBE_API_SANDBOX_SCRIPT,
    CONST_KUBE_API_SCRATCH_PREFIX,
    CONST_KUBE_API_SCRIPT_NAME,
    CONST_KUBE_API_SOCKET_NAME,
    CONST_KUBE_API_WAIT_INTERVAL_SECONDS,
    CONST_KUBE_API_WAIT_RETRIES,
    CONST_TOOL_NETWORK_KUBE_API,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.sandbox import SandboxError, SandboxUnavailableError


class KubeApiPrograms(NamedTuple):
    """The full path of each program of a kube-api run, in the order of
    `CONST_KUBE_API_PROGRAMS`. The PATH of the sandbox leads with the `.venv/bin` of the tree, so
    each script starts each program by its full path."""

    sh: str
    socat: str
    kubectl: str
    setpriv: str


def kube_api_programs() -> KubeApiPrograms:
    """The programs of a kube-api run on this host. A host without one of them raises
    `SandboxUnavailableError` that names each program that it does not have."""
    found = {name: shutil.which(name) for name in CONST_KUBE_API_PROGRAMS}
    missing = [name for name, path in found.items() if path is None]
    if missing:
        raise SandboxUnavailableError(
            f"The network profile {CONST_TOOL_NETWORK_KUBE_API} needs "
            f"{', '.join(missing)}, which this host does not have"
        )
    return KubeApiPrograms(*(str(found[name]) for name in CONST_KUBE_API_PROGRAMS))


def _user_context(kubectl: str, name: str | None) -> tuple[str, str | None]:
    """The name and the namespace of the context `name` of the kubeconfig of the user, else of its
    current context.

    `kubectl config view --minify` reads the kubeconfig as `kubectl proxy` then reads it: the files
    that `KUBECONFIG` names, else `~/.kube/config`. Its output redacts the credentials. A kubeconfig
    that kubectl cannot read, or that has no such context, raises `SandboxError`.
    """
    selected = [f"--context={name}"] if name else []
    done = run_subprocess(
        [kubectl, "config", "view", "--minify", "--output=json", *selected],
        quiet=True,
        check=False,
        local_read=True,
    )
    if done.returncode != 0:
        cause = next(iter(done.stderr.strip().splitlines()), f"exit code {done.returncode}")
        raise SandboxError(
            f"kubectl cannot read the context {name or 'current'} of the kubeconfig: {cause}"
        )
    context = json.loads(done.stdout)["contexts"][0]
    return context["name"], context["context"].get("namespace")


def _relay_kubeconfig(context: str, namespace: str | None) -> dict[str, Any]:
    """A kubeconfig with one cluster, one context and one user, each named `context`. The cluster
    is the relay in the sandbox, the context keeps `namespace`, and the user has no credentials."""
    server = str(
        httpx2.URL(scheme="http", host=CONST_KUBE_API_RELAY_HOST, port=CONST_KUBE_API_RELAY_PORT)
    )
    scope = {"namespace": namespace} if namespace else {}
    return {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [{"name": context, "cluster": {"server": server}}],
        "contexts": [{"name": context, "context": {"cluster": context, "user": context, **scope}}],
        "users": [{"name": context, "user": {}}],
        "current-context": context,
    }


def _wait() -> tuple[str, str]:
    """The retries and the interval of a wait for the proxy or the relay, as script arguments."""
    return str(CONST_KUBE_API_WAIT_RETRIES), f"{CONST_KUBE_API_WAIT_INTERVAL_SECONDS:g}"


@dataclass(frozen=True)
class KubeApiRelay:
    """One kube-api run: its programs, its context, and the scratch directory that holds the
    socket of the proxy and the kubeconfig of the tool."""

    programs: KubeApiPrograms
    context: str
    directory: Path

    @property
    def socket(self) -> Path:
        """The Unix socket of `kubectl proxy`."""
        return self.directory / CONST_KUBE_API_SOCKET_NAME

    @property
    def kubeconfig(self) -> Path:
        """The kubeconfig of the tool, with no credentials."""
        return self.directory / CONST_KUBE_API_KUBECONFIG_NAME

    @property
    def read_only_binds(self) -> tuple[Path, ...]:
        """What the sandbox binds read-only for the relay: the scratch directory, the shell and
        `socat`."""
        return (self.directory, Path(self.programs.sh), Path(self.programs.socat))

    @property
    def env(self) -> dict[str, str]:
        """The environment of the tool in the sandbox."""
        return {"KUBECONFIG": str(self.kubeconfig)}

    def sandbox_command(self, tool_command: Sequence[str]) -> list[str]:
        """The command in the sandbox: the relay to the socket, then `tool_command`."""
        return [
            self.programs.sh,
            "-c",
            CONST_KUBE_API_SANDBOX_SCRIPT,
            CONST_KUBE_API_SCRIPT_NAME,
            self.programs.socat,
            str(self.socket),
            str(CONST_KUBE_API_RELAY_PORT),
            *_wait(),
            *tool_command,
        ]

    def host_command(self, sandbox_command: Sequence[str]) -> list[str]:
        """The command outside the sandbox: `kubectl proxy` on the socket, then
        `sandbox_command`, the bubblewrap command."""
        return [
            self.programs.sh,
            "-c",
            CONST_KUBE_API_HOST_SCRIPT,
            CONST_KUBE_API_SCRIPT_NAME,
            str(self.socket),
            self.programs.setpriv,
            self.programs.kubectl,
            self.context,
            CONST_KUBE_API_REJECTED_METHODS,
            ",".join(CONST_KUBE_API_REJECTED_PATHS),
            self.programs.socat,
            *_wait(),
            *sandbox_command,
        ]


@contextmanager
def kube_api_relay(context: str | None) -> Iterator[KubeApiRelay]:
    """The relay of one kube-api run to the context `context`, else to the current context.

    The scratch directory and the kubeconfig in it exist until the run ends. A host without a
    program of the relay raises `SandboxUnavailableError`, and a context that the kubeconfig of the
    user does not have raises `SandboxError`. Both come before the scratch directory exists.
    """
    programs = kube_api_programs()
    name, namespace = _user_context(programs.kubectl, context)
    with tempfile.TemporaryDirectory(prefix=CONST_KUBE_API_SCRATCH_PREFIX) as scratch:
        relay = KubeApiRelay(programs=programs, context=name, directory=Path(scratch))
        relay.kubeconfig.write_text(json.dumps(_relay_kubeconfig(name, namespace)), "utf-8")
        yield relay


__all__ = ["KubeApiPrograms", "KubeApiRelay", "kube_api_programs", "kube_api_relay"]
