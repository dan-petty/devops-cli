"""A stub keyring and a recorded fake cluster for the cluster Secret push, with no network.

`FakeCluster` stands in for `subprocess.run` beneath `run_subprocess`, so the tests see each
argv, stdin and environment exactly as the child would. It answers the kubectl, gh and helm
commands the push and deploy-stack run, and applies a server-side apply's `List` to its own
Secrets. `FakeKeyring` is an encrypted keyring backend that can be locked. `forbid_requests` makes every
child process, keyring call and socket connection fail the test, for a dry run that must make
none. Names are generic.
"""

from __future__ import annotations

import base64
import json
import platform
import socket
import subprocess
from dataclasses import dataclass, field
from typing import Any

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import KeyringLocked, PasswordDeleteError

from devops_cli.config.constants import CONST_KEYRING_UNLOCK_PROBE_KEY

# The tracer's resource names the platform, whose processor probe runs a local `uname -p` once
# per process. Run it at import, before any test patches `subprocess.run`, so a fake cluster
# and the no-request guard see only the commands under test, whichever test runs first.
platform.platform()

MACHINE_LOGIN = "machine-account"
MACHINE_TOKEN = "ghp-machine-token-value-0001"


class FakeKeyring(KeyringBackend):
    """An encrypted keyring backend held in memory; `locked` makes every call raise."""

    priority = 1  # type: ignore[assignment]

    def __init__(self, values: dict[str, str] | None = None, *, locked: bool = False) -> None:
        super().__init__()
        self.values = dict(values or {})
        self.locked = locked
        self.reads: list[str] = []
        self.writes: dict[str, str] = {}
        self.events: list[str] | None = None

    def get_password(self, service: str, username: str) -> str | None:
        if self.locked:
            raise KeyringLocked("locked")
        self.reads.append(username)
        return self.values.get(username)

    def set_password(self, service: str, username: str, password: str) -> None:
        if self.locked:
            raise KeyringLocked("locked")
        self.writes[username] = password
        self.values[username] = password
        if self.events is not None:
            self.events.append(f"keyring-write {username}")

    def delete_password(self, service: str, username: str) -> None:
        if username not in self.values:
            raise PasswordDeleteError(username)
        del self.values[username]

    def secret_reads(self) -> set[str]:
        """The entries read, without the unlock probe, which reads no secret."""
        return set(self.reads) - {CONST_KEYRING_UNLOCK_PROBE_KEY}


def _encode(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


@dataclass
class Call:
    """One child process: its argv without `--context`, stdin and environment."""

    argv: list[str]
    stdin: str | None
    env: dict[str, str]


@dataclass
class FakeCluster:
    """Namespaces, Secrets, workloads and gh accounts, answering the commands run against them."""

    namespaces: set[str] = field(default_factory=lambda: {"llm", "cloudflared", "devops"})
    secrets: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    workloads: set[tuple[str, str]] = field(default_factory=set)
    gh_accounts: dict[str, tuple[str, str]] = field(
        default_factory=lambda: {MACHINE_LOGIN: (MACHINE_TOKEN, "keyring")}
    )
    gh_state: str = "success"
    fail: set[str] = field(default_factory=set)
    calls: list[Call] = field(default_factory=list)
    events: list[str] = field(default_factory=list)

    def add_secret(
        self,
        namespace: str,
        name: str,
        data: dict[str, str],
        *,
        annotations: dict[str, str] | None = None,
        manager: str = "kubectl-client-side-apply",
    ) -> None:
        """A live Secret whose keys `manager` owns."""
        self.secrets[(namespace, name)] = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "annotations": dict(annotations or {}),
                "managedFields": [
                    {"manager": manager, "fieldsV1": {"f:data": {f"f:{k}": {} for k in data}}}
                ],
            },
            "data": {key: _encode(value) for key, value in data.items()},
        }

    def live_data(self, namespace: str, name: str) -> dict[str, str]:
        """A live Secret's decoded data."""
        raw = self.secrets[(namespace, name)].get("data", {})
        return {key: base64.b64decode(value).decode() for key, value in raw.items()}

    def commands(self, *prefix: str) -> list[list[str]]:
        """The recorded argv starting with the prefix."""
        return [call.argv for call in self.calls if call.argv[: len(prefix)] == list(prefix)]

    def applies(self) -> list[Call]:
        """The server-side apply calls."""
        return [c for c in self.calls if c.argv[:3] == ["kubectl", "apply", "--server-side"]]

    def applied_items(self) -> list[dict[str, Any]]:
        """The Secrets of every server-side apply."""
        return [item for call in self.applies() for item in json.loads(call.stdin or "{}")["items"]]

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        argv = list(cmd)
        if "--context" in argv:
            index = argv.index("--context")
            del argv[index : index + 2]
        self.calls.append(Call(argv, kwargs.get("input"), dict(kwargs.get("env") or {})))
        self.events.append(" ".join(argv[:3]))
        code, stdout = self._answer(argv, kwargs)
        return subprocess.CompletedProcess(cmd, code, stdout, "error" if code else "")

    def _answer(self, argv: list[str], kwargs: dict[str, Any]) -> tuple[int, str]:
        if argv[2:3] and argv[2].startswith("secret/"):
            argv = [*argv[:2], *argv[2].split("/", 1), *argv[3:]]
        if argv[0] in self.fail:
            return 1, ""
        if argv[0] == "gh":
            return self._gh(argv, kwargs.get("env") or {})
        if argv[:2] == ["kubectl", "get"]:
            return 0, self._get(argv)
        if argv[:3] == ["kubectl", "apply", "--server-side"]:
            self._server_side_apply(json.loads(kwargs["input"]))
            return 0, ""
        if argv[:3] == ["kubectl", "annotate", "secret"]:
            namespace = argv[argv.index("-n") + 1]
            annotation = argv[-1].removesuffix("-")
            self.secrets[(namespace, argv[3])]["metadata"]["annotations"].pop(annotation, None)
        return 0, ""

    def _get(self, argv: list[str]) -> str:
        namespace = argv[argv.index("-n") + 1] if "-n" in argv else ""
        if argv[2] == "namespace":
            return f"namespace/{argv[3]}\n" if argv[3] in self.namespaces else ""
        if argv[2] == "secret":
            live = self.secrets.get((namespace, argv[3]))
            return json.dumps(live) if live else ""
        return f"{argv[2]}\n" if (namespace, argv[2]) in self.workloads else ""

    def _server_side_apply(self, manifest: dict[str, Any]) -> None:
        for item in manifest["items"]:
            meta = item["metadata"]
            key = (meta["namespace"], meta["name"])
            live = self.secrets.setdefault(
                key, {"metadata": {**meta, "annotations": {}, "managedFields": []}, "data": {}}
            )
            live["data"].update(item["data"])
            live["metadata"]["labels"] = meta["labels"]
            live["metadata"]["managedFields"].append(
                {
                    "manager": "devops-cli",
                    "fieldsV1": {"f:data": {f"f:{k}": {} for k in item["data"]}},
                }
            )

    def _gh(self, argv: list[str], env: dict[str, str]) -> tuple[int, str]:
        if argv[1:3] == ["auth", "status"]:
            stored = [
                {
                    "login": login,
                    "tokenSource": source,
                    "state": self.gh_state,
                    "host": "github.com",
                }
                for login, (_, source) in self.gh_accounts.items()
            ]
            # gh lists an ambient GH_TOKEN first, as the active account, under its owner's login.
            ambient = [
                {"login": login, "tokenSource": "GH_TOKEN", "state": "success", "active": True}
                for login, (token, _) in self.gh_accounts.items()
                if token == env.get("GH_TOKEN")
            ]
            return 0, json.dumps({"hosts": {"github.com": ambient + stored}})
        if argv[1:3] == ["auth", "token"]:
            login = argv[argv.index("--user") + 1]
            account = self.gh_accounts.get(login)
            return (0, account[0] + "\n") if account else (1, "")
        return 1, ""


def forbid_requests(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Make every child process (kubectl, gh, helm), keyring call and socket connection raise.

    Returns the requests attempted, so a test also sees one a caller caught and swallowed.
    Telemetry is turned off to keep the tests fast; that a dry run exports nothing either is
    tested in `tests/test_telemetry_collector_export.py`.
    """
    from devops_cli.telemetry import tracer

    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "false")
    monkeypatch.setattr(tracer, "_resolve_telemetry_settings", lambda: (None, False))
    attempted: list[str] = []

    def refuse(kind: str) -> Any:
        def raiser(*args: Any, **kwargs: Any) -> Any:
            attempted.append(f"{kind}: {args[0] if args else kwargs}")
            raise AssertionError(f"a dry run made an external request ({kind})")

        return raiser

    monkeypatch.setattr(subprocess, "run", refuse("subprocess.run"))
    monkeypatch.setattr(subprocess, "Popen", refuse("subprocess.Popen"))
    monkeypatch.setattr(keyring, "get_keyring", refuse("keyring"))
    monkeypatch.setattr(socket.socket, "connect", refuse("socket"))
    monkeypatch.setattr(socket, "create_connection", refuse("socket"))
    return attempted
