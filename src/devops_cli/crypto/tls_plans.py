"""Planned requests for `devops tls enable-k8s` (#412, #886, #2258).

A dry run makes zero external requests and returns ordered PlannedRequest items. The four
kubectl commands of each namespace come from the builders below, which `enable_k8s_cmd` also
calls, so the plan cannot drift from the run.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devops_cli.dry_run.requests import PlannedRequest

RENDERED_SECRET_PLACEHOLDER = "<output of the previous request>"


def _context_args(context: str | None) -> list[str]:
    return ["--context", context] if context else []


def namespace_check_argv(namespace: str, context: str | None) -> list[str]:
    """The command that reads whether `namespace` exists."""
    return ["kubectl", "get", "namespace", namespace, *_context_args(context)]


def namespace_create_argv(namespace: str, context: str | None) -> list[str]:
    """The command that creates `namespace`."""
    return ["kubectl", "create", "namespace", namespace, *_context_args(context)]


def secret_render_argv(
    secret_name: str, cert_path: Path, key_path: Path, namespace: str, context: str | None
) -> list[str]:
    """The command that renders the TLS secret on the client, where kubectl refuses a
    certificate and a key that do not match."""
    return [
        "kubectl",
        "create",
        "secret",
        "tls",
        secret_name,
        f"--cert={cert_path}",
        f"--key={key_path}",
        "-n",
        namespace,
        "--dry-run=client",
        "-o",
        "yaml",
        *_context_args(context),
    ]


def secret_apply_argv(namespace: str, context: str | None) -> list[str]:
    """The command that applies the rendered secret, read on standard input."""
    return ["kubectl", "apply", "-f", "-", "-n", namespace, *_context_args(context)]


def plan_enable_k8s(
    namespaces: Sequence[str],
    secret_name: str,
    cert_path: Path,
    key_path: Path,
    context: str | None,
) -> list[PlannedRequest]:
    """The four kubectl requests of each namespace, in the order of the run."""
    requests: list[PlannedRequest] = []
    for namespace in namespaces:
        requests += [
            PlannedRequest(
                method="kubectl",
                target=f"namespace/{namespace}",
                argv=tuple(namespace_check_argv(namespace, context)),
            ),
            PlannedRequest(
                method="kubectl",
                target=f"namespace/{namespace}",
                argv=tuple(namespace_create_argv(namespace, context)),
                condition="the namespace does not exist",
            ),
            PlannedRequest(
                method="kubectl",
                target=f"secret/{secret_name}",
                argv=tuple(
                    secret_render_argv(secret_name, cert_path, key_path, namespace, context)
                ),
            ),
            PlannedRequest(
                method="kubectl",
                target=f"secret/{secret_name}",
                argv=tuple(secret_apply_argv(namespace, context)),
                stdin=RENDERED_SECRET_PLACEHOLDER,
                condition="the secret renders",
            ),
        ]
    return requests
