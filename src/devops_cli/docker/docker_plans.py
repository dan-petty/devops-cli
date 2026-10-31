"""Planned execution requests for docker commands under dry run (#2251)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from devops_cli.config.commands import (
    build_cosign_sign_cmd,
    build_cosign_verify_cmd,
)
from devops_cli.dry_run.requests import PlannedRequest


def plan_docker_images(name: str | None = None) -> list[PlannedRequest]:
    """Generate planned request for listing Docker images."""
    suffix = f"?name={name}" if name else ""
    return [
        PlannedRequest(
            method="DOCKER",
            target=f"GET /images/json{suffix}",
        )
    ]


def plan_docker_build(
    context: Path | str,
    tag: str | None = None,
    dockerfile: Path | str | None = None,
    no_cache: bool = False,
) -> list[PlannedRequest]:
    """Generate planned request for building a Docker image."""
    details = {
        "context": str(context),
        "tag": tag,
        "dockerfile": str(dockerfile) if dockerfile else None,
        "no_cache": no_cache,
    }
    return [
        PlannedRequest(
            method="DOCKER",
            target=f"POST /build (tag: {tag or '<none>'}, context: {context})",
            stdin=json.dumps(details),
        )
    ]


def plan_docker_push(image: str) -> list[PlannedRequest]:
    """Generate planned request for pushing a Docker image."""
    return [
        PlannedRequest(
            method="DOCKER",
            target=f"POST /images/{image}/push",
        )
    ]


def plan_docker_prune(volumes: bool = False) -> list[PlannedRequest]:
    """Generate planned requests for pruning Docker resources."""
    requests = [
        PlannedRequest(method="DOCKER", target="POST /containers/prune"),
        PlannedRequest(method="DOCKER", target="POST /images/prune"),
        PlannedRequest(method="DOCKER", target="POST /networks/prune"),
    ]
    if volumes:
        requests.append(PlannedRequest(method="DOCKER", target="POST /volumes/prune"))
    return requests


def plan_docker_stats(name: str | None = None) -> list[PlannedRequest]:
    """Generate planned requests for inspecting container statistics."""
    suffix = f"?name={name}" if name else ""
    return [
        PlannedRequest(method="DOCKER", target=f"GET /containers/json{suffix}"),
        PlannedRequest(
            method="DOCKER",
            target="GET /containers/<container-id>/stats",
            repeat="for each container",
        ),
    ]


def plan_docker_cache(prune: bool = False) -> list[PlannedRequest]:
    """Generate planned requests for inspecting and optionally pruning build cache."""
    requests = [
        PlannedRequest(method="DOCKER", target="GET /system/df"),
    ]
    if prune:
        requests.append(PlannedRequest(method="DOCKER", target="POST /build/prune"))
    return requests


def plan_docker_sandbox(
    command: Sequence[str],
    image: str = "python:3.14-slim",
    workspace: Path | str = ".",
    network_mode: str = "isolated",
    read_only: bool = True,
    rootless: bool = True,
    declared_controls: dict[str, Any] | None = None,
    seccomp_profile: str | Path | None = None,
) -> list[PlannedRequest]:
    """Generate planned requests for running a disposable workload sandbox container."""
    details: dict[str, Any] = {
        "image": image,
        "command": list(command),
        "workspace": str(workspace),
        "network_mode": network_mode,
        "read_only": read_only,
        "rootless": rootless,
    }
    if declared_controls is not None:
        details["declared_controls"] = declared_controls
    if seccomp_profile is not None:
        details["seccomp_profile"] = str(seccomp_profile)
    return [
        PlannedRequest(
            method="DOCKER",
            target="POST /containers/create",
            stdin=json.dumps(details),
        ),
        PlannedRequest(
            method="DOCKER",
            target="POST /containers/<container-id>/start",
        ),
        PlannedRequest(
            method="DOCKER",
            target="POST /containers/<container-id>/wait",
        ),
        PlannedRequest(
            method="DOCKER",
            target="GET /containers/<container-id>/logs",
        ),
        PlannedRequest(
            method="DOCKER",
            target="DELETE /containers/<container-id>",
        ),
    ]


def plan_docker_sign(
    image: str,
    key: str | None = None,
    keyless: bool = True,
    upload: bool = True,
    annotations: list[str] | None = None,
) -> list[PlannedRequest]:
    """Generate planned request for cosign container image signing."""
    cmd = build_cosign_sign_cmd(
        image,
        key=key,
        keyless=keyless,
        upload=upload,
        annotations=annotations,
    )
    return [
        PlannedRequest(
            method="EXEC",
            target="cosign sign",
            argv=tuple(cmd),
        )
    ]


def plan_docker_verify(
    image: str,
    key: str | None = None,
    cert_identity: str | None = None,
    cert_issuer: str | None = None,
    attestation: bool = False,
    predicate_type: str | None = None,
    insecure_ignore_tlog: bool = False,
) -> list[PlannedRequest]:
    """Generate planned request for cosign container image verification."""
    cmd = build_cosign_verify_cmd(
        image,
        key=key,
        cert_identity=cert_identity,
        cert_issuer=cert_issuer,
        attestation=attestation,
        predicate_type=predicate_type,
        insecure_ignore_tlog=insecure_ignore_tlog,
    )
    return [
        PlannedRequest(
            method="EXEC",
            target="cosign verify",
            argv=tuple(cmd),
        )
    ]
