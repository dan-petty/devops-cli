"""Offline gate check that every Valkey container keeps `--maxmemory` at most three quarters of its memory limit (#4992)."""

from __future__ import annotations

import re
import shlex
from collections.abc import Iterator, Mapping
from decimal import Decimal
from typing import Any, Final

import yaml
from kubernetes.utils.quantity import parse_quantity

from devops_cli.k8s.argocd_gate import discover_path_applications
from tests.gate.k8s_render import kustomize
from tests.support.k8s_tree import TREE
from tests.support.paths import REPO_ROOT

K8S_DIR: Final = REPO_ROOT / "k8s"
_SHELL_NAMES: Final[frozenset[str]] = frozenset({"sh", "bash", "ash", "dash"})
_SEGMENT_SEPARATORS: Final[frozenset[str]] = frozenset({";", "&&", "||", "|"})
_MAXMEMORY_FLAG: Final = "--maxmemory"
_MEMORY_UNITS: Final[dict[str, int]] = {
    "": 1,
    "b": 1,
    "k": 1000,
    "kb": 1024,
    "ki": 1024,
    "kib": 1024,
    "m": 1000**2,
    "mb": 1024**2,
    "mi": 1024**2,
    "mib": 1024**2,
    "g": 1000**3,
    "gb": 1024**3,
    "gi": 1024**3,
    "gib": 1024**3,
    "t": 1000**4,
    "tb": 1024**4,
    "ti": 1024**4,
    "tib": 1024**4,
}
_MEMORY_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*$")
_ENV_ASSIGNMENT: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")


def _ref(document: Mapping[str, Any]) -> str:
    metadata = document.get("metadata", {})
    kind = str(document.get("kind", "Object"))
    namespace = metadata.get("namespace")
    name = str(metadata.get("name", "<unnamed>"))
    return f"{kind}/{namespace}/{name}" if namespace else f"{kind}/{name}"


def _pod_containers(document: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    """Yield every container in `document` if it defines a pod template."""
    spec = document.get("spec")
    if not isinstance(spec, Mapping):
        return
    match document.get("kind"):
        case "Pod":
            pod = spec
        case "Deployment" | "StatefulSet" | "DaemonSet" | "Job" | "ReplicaSet":
            pod = spec.get("template", {}).get("spec")
        case "CronJob":
            pod = spec.get("jobTemplate", {}).get("spec", {}).get("template", {}).get("spec")
        case _:
            return
    if not isinstance(pod, Mapping):
        return
    for group in ("initContainers", "containers"):
        for container in pod.get(group) or ():
            if isinstance(container, Mapping):
                yield container


def _command_tokens(container: Mapping[str, Any]) -> list[str]:
    """Return flattened argv/script tokens for `container`."""
    raw = [
        str(part) for part in (*(container.get("command") or ()), *(container.get("args") or ()))
    ]
    if not raw:
        return []
    head = raw[0].rsplit("/", 1)[-1]
    if head in _SHELL_NAMES:
        for index, token in enumerate(raw[1:], start=1):
            if token.startswith("-") and "c" in token[1:] and index + 1 < len(raw):
                try:
                    return shlex.split(raw[index + 1])
                except ValueError:
                    return raw[index + 1].split()
    return raw


def _valkey_segments(tokens: list[str]) -> Iterator[list[str]]:
    """Yield simple command token lists whose executable is `valkey-server`."""
    segment: list[str] = []
    for token in [*tokens, ";"]:
        if token in _SEGMENT_SEPARATORS:
            stripped = list(segment)
            while stripped and (stripped[0] == "exec" or _ENV_ASSIGNMENT.match(stripped[0])):
                stripped.pop(0)
            if stripped and stripped[0].rsplit("/", 1)[-1] == "valkey-server":
                yield stripped[1:]
            segment = []
        else:
            segment.append(token)


def _valkey_maxmemory_raw(container: Mapping[str, Any]) -> tuple[bool, str | None]:
    """Return `(runs_valkey, last_maxmemory_value)` for `container`."""
    tokens = _command_tokens(container)
    runs_valkey = False
    bound: str | None = None
    for args in _valkey_segments(tokens):
        runs_valkey = True
        index = 0
        while index < len(args):
            arg = args[index]
            if arg == _MAXMEMORY_FLAG and index + 1 < len(args):
                bound = args[index + 1]
                index += 2
                continue
            if arg.startswith(f"{_MAXMEMORY_FLAG}="):
                bound = arg.split("=", 1)[1]
            index += 1
    return runs_valkey, bound


def _parse_valkey_bytes(raw: str) -> Decimal | None:
    """Parse a Valkey `--maxmemory` quantity using 1024-based `kb`/`mb`/`gb` units."""
    matched = _MEMORY_PATTERN.fullmatch(raw)
    if matched is None:
        return None
    multiplier = _MEMORY_UNITS.get(matched.group(2).lower())
    if multiplier is None:
        return None
    return Decimal(matched.group(1)) * Decimal(multiplier)


def valkey_maxmemory_findings(document: Mapping[str, Any]) -> list[str]:
    """Return findings for `document` where `valkey-server --maxmemory` exceeds 3/4 of limit."""
    findings: list[str] = []
    ref = _ref(document)
    for container in _pod_containers(document):
        runs_valkey, bound_raw = _valkey_maxmemory_raw(container)
        if not runs_valkey or bound_raw is None:
            continue
        cname = str(container.get("name", "<unnamed>"))
        bound_bytes = _parse_valkey_bytes(bound_raw)
        limit_raw = container.get("resources", {}).get("limits", {}).get("memory")
        if bound_bytes is None:
            findings.append(
                f"{ref} container {cname}: invalid --maxmemory {bound_raw!r} (memory limit {limit_raw!r})"
            )
            continue
        if limit_raw is None:
            findings.append(
                f"{ref} container {cname}: --maxmemory {bound_raw} has no memory limit set"
            )
            continue
        limit_bytes = Decimal(str(parse_quantity(str(limit_raw))))
        if bound_bytes * 4 > limit_bytes * 3:
            findings.append(
                f"{ref} container {cname}: --maxmemory {bound_raw} exceeds 3/4 of memory limit {limit_raw}"
            )
    return findings


def _deployment(command: list[str], memory_limit: str | None) -> dict[str, Any]:
    resources: dict[str, Any] = {}
    if memory_limit is not None:
        resources["limits"] = {"memory": memory_limit}
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "valkey-sample", "namespace": "llm"},
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "valkey",
                            "command": command,
                            "resources": resources,
                        }
                    ]
                }
            }
        },
    }


def check_valkey_maxmemory_bound_above_three_quarters_reports_finding() -> None:
    """Negative control: a `valkey` container with `--maxmemory 512mb` and limit `512Mi` fails (#4992)."""
    direct = valkey_maxmemory_findings(
        _deployment(["valkey-server", "--maxmemory", "512mb"], "512Mi")
    )
    wrapped = valkey_maxmemory_findings(
        _deployment(
            ["sh", "-c", "exec valkey-server /run/valkey/auth.conf --maxmemory 512mb"],
            "512Mi",
        )
    )
    assert (len(direct), [t for t in ("valkey", "512mb", "512Mi") if t not in direct[0]]) == (
        1,
        [],
    )
    assert (len(wrapped), [t for t in ("valkey", "512mb", "512Mi") if t not in wrapped[0]]) == (
        1,
        [],
    )


def check_valkey_maxmemory_bound_at_three_quarters_passes() -> None:
    """A `valkey` container whose `--maxmemory` is exactly 3/4 of its memory limit passes (#4992)."""
    assert (
        valkey_maxmemory_findings(_deployment(["valkey-server", "--maxmemory", "768mb"], "1Gi"))
        == []
    )


def check_valkey_without_maxmemory_is_ignored() -> None:
    """A `valkey` container with no `--maxmemory` flag produces no ratio finding (#4992)."""
    assert valkey_maxmemory_findings(_deployment(["valkey-server"], "512Mi")) == []
    assert (
        valkey_maxmemory_findings(_deployment(["redis-exporter", "--maxmemory", "512mb"], "512Mi"))
        == []
    )


def check_each_environment_valkey_maxmemory_stays_within_three_quarters() -> None:
    """Every `valkey-server` container across the environment kustomizations stays at most 3/4 of its memory limit (#4992)."""
    checked = 0
    findings: list[str] = []
    for dir_path in discover_path_applications(TREE, K8S_DIR / "argocd" / "apps").values():
        for document in yaml.load_all(kustomize(dir_path).stdout, Loader=yaml.CSafeLoader):
            if not isinstance(document, Mapping):
                continue
            for container in _pod_containers(document):
                runs_valkey, bound_raw = _valkey_maxmemory_raw(container)
                if runs_valkey and bound_raw is not None:
                    checked += 1
            findings.extend(valkey_maxmemory_findings(document))
    assert checked >= 3, f"Expected at least 3 bounded Valkey containers, inspected {checked}"
    assert findings == [], "\n".join(findings)
