"""A recorded fake cluster for the cluster Secret push, with no network.

`FakeCluster` stands in for `subprocess.run` beneath `run_subprocess`, so the tests see each
argv, stdin and environment exactly as the child would. It answers the kubectl and helm commands
the push and deploy-stack run, and applies a server-side apply's `List` to its own
Secrets. The keyring fake is `tests/support/fakes/keyring.py`. Names are generic.
"""

from __future__ import annotations

import base64
import json
import subprocess
from dataclasses import dataclass, field
from typing import Any

# The GitHub App's private key as the keyring holds it, and the Secret key it is pushed to.
APP_KEY_ENTRY = "DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY"
APP_KEY = "app-private-key-value-0001"


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
    """Namespaces, Secrets and workloads, answering the commands run against them."""

    namespaces: set[str] = field(default_factory=lambda: {"llm", "cloudflared", "devops"})
    secrets: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    workloads: set[tuple[str, str]] = field(default_factory=set)
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
        if argv[:2] == ["helm", "version"]:
            return 0, "v3.17.0"
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
