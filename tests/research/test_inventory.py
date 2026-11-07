"""The inventory lists every pin of a repository as a typed component, and reaches nothing outside the files."""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions.research import InventoryError
from devops_cli.research.inventory import read_inventory
from devops_cli.research.models import Component, ComponentKind, Ecosystem
from tests.support.paths import FIXTURES

FIXTURE_REPO = FIXTURES / "research" / "repo"

_PIP = (ComponentKind.PYTHON_PACKAGE, Ecosystem.PYPI)
_NODE = (ComponentKind.NODE_PACKAGE, Ecosystem.NPM)
_TOOL = ComponentKind.TOOL
_IMAGE = (ComponentKind.CONTAINER_IMAGE, Ecosystem.DOCKER)
_ACTION = (ComponentKind.ACTION, Ecosystem.GITHUB_ACTIONS)


def _component(
    kind_and_ecosystem: tuple[ComponentKind, Ecosystem],
    name: str,
    version: str,
    file: str,
    line: int,
) -> Component:
    kind, ecosystem = kind_and_ecosystem
    return Component(
        kind=kind, ecosystem=ecosystem, name=name, version=version, file=file, line=line
    )


EXPECTED = [
    _component(_IMAGE, "ghcr.io/astral-sh/uv", "0.13.6", "Dockerfile", 2),
    _component(_IMAGE, "python", "3.14-slim-trixie", "Dockerfile", 4),
    _component(_IMAGE, "ghcr.io/example-org/tool", "1.2.3", "Dockerfile", 6),
    _component(
        (ComponentKind.DEVCONTAINER_FEATURE, Ecosystem.DEVCONTAINER_FEATURE),
        "ghcr.io/devcontainers/features/common-utils",
        "2.5.9",
        ".devcontainer/devcontainer-lock.json",
        3,
    ),
    _component(_ACTION, "actions/checkout", "v7", ".github/workflows/ci.yml", 7),
    _component(_ACTION, "astral-sh/setup-uv", "v10.2.0", ".github/workflows/ci.yml", 8),
    _component(_ACTION, "astral-sh/setup-uv", "v10.0.1", ".github/workflows/ci.yml", 13),
    _component(_IMAGE, "ghcr.io/example-org/linter", "3.4.5", ".github/workflows/ci.yml", 14),
    _component(_ACTION, "example-org/no-comment", "v2", ".github/workflows/ci.yml", 15),
    _component(_ACTION, "actions/cache", "v6.1.0", ".github/actions/setup/action.yml", 5),
    _component(
        (ComponentKind.CHART, Ecosystem.HELM), "qdrant", "1.19.1", "k8s/argocd/apps/qdrant.yaml", 9
    ),
    _component(_IMAGE, "valkey/valkey", "9.1.2-alpine", "k8s/llm/valkey.yaml", 10),
    _component(_IMAGE, "example/untagged", "latest", "k8s/llm/valkey.yaml", 12),
    _component(_IMAGE, "ghcr.io/example-org/web", "v0.11.4", "k8s/llm/values-web.yaml", 3),
    _component(_PIP, "httpx2", "2.13.1", "pyproject.toml", 5),
    _component(_PIP, "pyyaml", "6.0.3", "pyproject.toml", 6),
    _component(_PIP, "pytest", "9.1.1", "pyproject.toml", 11),
    _component(
        _NODE,
        "@example/helper",
        "0.4.2",
        "src/devops_cli/tools_lock/example-npm/package-lock.json",
        11,
    ),
    _component(
        _NODE,
        "example-npm",
        "1.14.3",
        "src/devops_cli/tools_lock/example-npm/package-lock.json",
        14,
    ),
    _component(_PIP, "bandit", "1.9.4", "src/devops_cli/tools_lock/bandit.txt", 3),
    _component(_PIP, "colorama", "0.4.6", "src/devops_cli/tools_lock/bandit.txt", 6),
    Component(
        kind=_TOOL,
        ecosystem=Ecosystem.GITHUB_RELEASE,
        name="kubectl",
        version="1.37.1",
        file="src/devops_cli/tools_lock/tools.lock",
        line=3,
    ),
    Component(
        kind=_TOOL,
        ecosystem=Ecosystem.UNKNOWN,
        name="homebrewed",
        version="2.0.0",
        file="src/devops_cli/tools_lock/tools.lock",
        line=14,
    ),
    Component(
        kind=_TOOL,
        ecosystem=Ecosystem.PYPI,
        name="bandit",
        version="1.9.4",
        file="src/devops_cli/tools_lock/tools.lock",
        line=25,
    ),
    Component(
        kind=_TOOL,
        ecosystem=Ecosystem.NPM,
        name="example-npm",
        version="1.14.3",
        file="src/devops_cli/tools_lock/tools.lock",
        line=32,
    ),
    _component(
        (ComponentKind.TERRAFORM_PROVIDER, Ecosystem.TERRAFORM),
        "hashicorp/aws",
        "~> 5.0",
        "tf/aws/versions.tf",
        5,
    ),
    _component(_PIP, "certifi", "2026.9.1", "uv.lock", 5),
]


def test_inventory_lists_one_component_for_each_pin_of_the_fixture_repository() -> None:
    inventory = read_inventory(FIXTURE_REPO)

    assert sorted(inventory.components, key=_sort_key) == sorted(EXPECTED, key=_sort_key)


def _sort_key(component: Component) -> tuple[str, int, str]:
    return (component.file, component.line, component.name)


def test_inventory_order_is_stable() -> None:
    first = read_inventory(FIXTURE_REPO)
    second = read_inventory(FIXTURE_REPO)

    assert first.model_dump_json() == second.model_dump_json()
    assert first.components == sorted(first.components, key=_sort_key)


def test_the_same_action_at_two_versions_is_two_components() -> None:
    setup_uv = [
        component.version
        for component in read_inventory(FIXTURE_REPO).components
        if component.name == "astral-sh/setup-uv"
    ]

    assert setup_uv == ["v10.2.0", "v10.0.1"]


def test_a_pin_with_no_ecosystem_is_listed_and_counted() -> None:
    inventory = read_inventory(FIXTURE_REPO)

    unknown = [c.name for c in inventory.components if c.ecosystem == Ecosystem.UNKNOWN]

    assert unknown == ["homebrewed"]
    assert inventory.summary.unknown == 1
    assert inventory.summary.total == len(EXPECTED)


def test_summary_counts_each_kind_and_ecosystem() -> None:
    summary = read_inventory(FIXTURE_REPO).summary

    assert summary.by_kind == {
        "action": 5,
        "chart": 1,
        "container-image": 7,
        "devcontainer-feature": 1,
        "node-package": 2,
        "python-package": 6,
        "terraform-provider": 1,
        "tool": 4,
    }
    assert sum(summary.by_ecosystem.values()) == summary.total


def test_the_reader_starts_no_program_and_opens_no_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("the inventory reached beyond its files")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)

    assert read_inventory(FIXTURE_REPO).components


def test_a_file_that_does_not_parse_is_an_error_that_names_the_file(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("dependencies = [", encoding="utf-8")

    with pytest.raises(InventoryError, match=r"pyproject\.toml") as raised:
        read_inventory(tmp_path)

    assert raised.value.error_code == "RESEARCH_INVENTORY_ERROR"
    assert raised.value.exit_code == 1


def test_a_repository_with_none_of_the_files_has_no_components(tmp_path: Path) -> None:
    inventory = read_inventory(tmp_path)

    assert (inventory.components, inventory.summary.total) == ([], 0)
