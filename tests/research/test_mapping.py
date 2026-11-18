"""The watch list maps a pin to its OSV identity, its purl and its registry reference (#3932)."""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest
from packageurl import PackageURL

from devops_cli.research.container_pins import image_component
from devops_cli.research.inventory import read_inventory
from devops_cli.research.models import Component, ComponentKind, Ecosystem
from devops_cli.research.watch import WATCH_FILE, read_watch_list

_DOCKERFILE = "FROM ghcr.io/astral-sh/uv:0.13.6\nFROM python:3.14-slim-trixie\n"
_PYPROJECT = (
    '[project]\nname = "example"\nversion = "0.1.0"\n'
    'dependencies = ["httpx2==2.13.1", "pyyaml==6.0.3"]\n'
)
_MAPPED = (
    "[[watch]]\n"
    'ecosystem = "docker"\n'
    'name = "ghcr.io/astral-sh/uv"\n'
    'repo = "astral-sh/uv"\n'
    'osv_ecosystem = "Debian"\n'
    'osv_name = "uv"\n'
)
_EXTERNAL_PIN = (
    "[[pin]]\n"
    'kind = "tool"\n'
    'name = "ubuntu"\n'
    'version = "24.04"\n'
    'repo = "example/os"\n'
    'osv_ecosystem = "Ubuntu"\n'
    'osv_name = "linux"\n'
)
_TOOLS_LOCK = (
    'python_version = "3.14"\n'
    "\n"
    "[binary.homebrewed]\n"
    'version = "2.0.0"\n'
    'description = "A tool whose source is no GitHub repository"\n'
    'source = "https://downloads.example.com/homebrewed"\n'
    'bin = "homebrewed"\n'
    'format = "binary"\n'
    "\n"
    "[binary.homebrewed.platforms.linux-amd64]\n"
    'url = "https://downloads.example.com/homebrewed/2.0.0/homebrewed"\n'
    'sha256 = "1111111111111111111111111111111111111111111111111111111111111111"\n'
    "\n"
    "[python]\n"
    "\n"
    "[npm]\n"
)


def _write_repository(root: Path, mapping: str) -> None:
    """A repository of a package file, a container file and the mapping file `mapping`."""
    (root / WATCH_FILE).parent.mkdir(parents=True, exist_ok=True)
    (root / WATCH_FILE).write_text(mapping, encoding="utf-8")
    (root / "Dockerfile").write_text(_DOCKERFILE, encoding="utf-8")
    (root / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")


def _named(components: list[Component], name: str) -> Component:
    return next(component for component in components if component.name == name)


def test_a_mapped_component_gets_its_osv_identity(tmp_path: Path) -> None:
    from devops_cli.research.mapping import apply_mapping, mapped_inventory

    _write_repository(tmp_path, _MAPPED)

    mapped = apply_mapping(read_inventory(tmp_path).components, read_watch_list(tmp_path))

    component = _named(mapped, "ghcr.io/astral-sh/uv")
    assert (component.osv_ecosystem, component.osv_name, component.repo) == (
        "Debian",
        "uv",
        "astral-sh/uv",
    )
    assert (component.ecosystem, len(mapped), mapped_inventory(tmp_path).summary.total) == (
        Ecosystem.DOCKER,
        4,
        4,
    )


def test_an_extra_pin_of_the_mapping_file_is_listed(tmp_path: Path) -> None:
    from devops_cli.research.mapping import mapped_inventory

    _write_repository(tmp_path, _EXTERNAL_PIN)

    inventory = mapped_inventory(tmp_path)

    pin = _named(inventory.components, "ubuntu")
    assert (
        pin.file,
        pin.line,
        pin.kind,
        pin.ecosystem,
        pin.version,
        pin.repo,
        pin.osv_ecosystem,
        pin.osv_name,
    ) == (
        "external",
        0,
        ComponentKind.TOOL,
        Ecosystem.UNKNOWN,
        "24.04",
        "example/os",
        "Ubuntu",
        "linux",
    )
    assert inventory.summary.total == 5


def test_an_unmapped_pin_stays_unknown_and_is_counted(tmp_path: Path) -> None:
    from devops_cli.research.mapping import mapped_inventory

    _write_repository(tmp_path, _MAPPED)
    lock = tmp_path / "src" / "devops_cli" / "tools_lock" / "tools.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text(_TOOLS_LOCK, encoding="utf-8")

    inventory = mapped_inventory(tmp_path)

    component = _named(inventory.components, "homebrewed")
    assert (
        component.ecosystem,
        component.osv_ecosystem,
        component.osv_name,
        component.repo,
        component.purl,
    ) == (Ecosystem.UNKNOWN, "", "", "", "")
    assert (inventory.summary.unknown, inventory.summary.total) == (1, 5)


def test_a_package_component_gets_a_purl(tmp_path: Path) -> None:
    from devops_cli.research.mapping import mapped_inventory, purl_of

    _write_repository(tmp_path, _MAPPED)

    inventory = mapped_inventory(tmp_path)

    component = _named(inventory.components, "pyyaml")
    purl = PackageURL.from_string(component.purl)
    assert (purl.type, purl.name, purl.version) == ("pypi", "pyyaml", "6.0.3")
    assert (
        purl_of(component),
        purl_of(
            Component(
                kind=ComponentKind.PYTHON_PACKAGE,
                ecosystem=Ecosystem.PYPI,
                name="pyyaml",
                version="",
                file="pyproject.toml",
                line=1,
            )
        ),
        purl_of(
            Component(
                kind=ComponentKind.TOOL,
                ecosystem=Ecosystem.GITHUB_RELEASE,
                name="kubectl",
                version="1.37.1",
                file="src/devops_cli/tools_lock/tools.lock",
                line=3,
            )
        ),
    ) == ("pkg:pypi/pyyaml@6.0.3", "", "")


def test_an_image_component_keeps_its_registry_reference(tmp_path: Path) -> None:
    from devops_cli.research.mapping import mapped_inventory, registry_of

    _write_repository(tmp_path, _MAPPED)

    inventory = mapped_inventory(tmp_path)

    assert (
        _named(inventory.components, "ghcr.io/astral-sh/uv").registry,
        _named(inventory.components, "python").registry,
        _named(inventory.components, "pyyaml").registry,
        registry_of(image_component("python:3.14-slim-trixie", "Dockerfile", 2)),
    ) == ("ghcr.io", "docker.io", "", "docker.io")


def test_a_rendered_image_is_listed_when_a_renderer_is_given(tmp_path: Path) -> None:
    from devops_cli.research.mapping import mapped_inventory

    _write_repository(tmp_path, _MAPPED)
    calls: list[int] = []

    def renderer() -> list[str]:
        calls.append(1)
        return ["quay.io/example-org/only-in-chart:1.2.3"]

    inventory = mapped_inventory(tmp_path, renderer=renderer)

    image = _named(inventory.components, "quay.io/example-org/only-in-chart")
    assert (image.file, image.line, image.kind, image.version, image.registry) == (
        "rendered",
        0,
        ComponentKind.CONTAINER_IMAGE,
        "1.2.3",
        "quay.io",
    )
    assert (len(calls), inventory.summary.total) == (1, 5)


def test_the_default_inventory_starts_no_program_and_opens_no_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from devops_cli.research import render
    from devops_cli.research.mapping import mapped_inventory

    _write_repository(tmp_path, _MAPPED)
    built: list[str] = []

    def refuse(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("the inventory reached beyond its files")

    def renderer_never_built(*_args: Any, **_kwargs: Any) -> None:
        built.append("renderer_for")
        raise AssertionError("the default inventory built the renderer")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(render, "renderer_for", renderer_never_built)

    inventory = mapped_inventory(tmp_path)

    assert [component.name for component in inventory.components] == [
        "ghcr.io/astral-sh/uv",
        "python",
        "httpx2",
        "pyyaml",
    ]
    assert (built, inventory.summary.total) == ([], 4)
