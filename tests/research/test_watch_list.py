"""Tests for the watch list of `.devops/research-watch.toml` (#3987)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.exceptions.research import InventoryError
from devops_cli.research.models import ComponentKind, Ecosystem
from devops_cli.research.watch import WATCH_FILE, read_watch_list


def _write(root: Path, text: str) -> None:
    (root / WATCH_FILE).parent.mkdir(parents=True, exist_ok=True)
    (root / WATCH_FILE).write_text(text, encoding="utf-8")


def test_a_repository_with_no_file_has_an_empty_watch_list(tmp_path: Path) -> None:
    assert read_watch_list(tmp_path).watch == []


def test_an_entry_maps_a_component_to_its_repository(tmp_path: Path) -> None:
    _write(
        tmp_path,
        '[[watch]]\necosystem = "helm"\nname = "qdrant"\nrepo = "qdrant/qdrant"\npackage = "qdrant"\n',
    )

    watch = read_watch_list(tmp_path)

    entry = watch.entry_of(Ecosystem.HELM, "qdrant")
    assert (
        None if entry is None else (entry.repo, entry.package),
        watch.entry_of(Ecosystem.DOCKER, "qdrant"),
    ) == (("qdrant/qdrant", "qdrant"), None)


def test_the_watch_list_reads_the_osv_identity_and_the_extra_pin(tmp_path: Path) -> None:
    _write(
        tmp_path,
        '[[watch]]\necosystem = "helm"\nname = "qdrant"\nrepo = "qdrant/qdrant"\n'
        'osv_ecosystem = "Debian"\nosv_name = "qdrant"\npurl = "pkg:helm/qdrant@1.19.1"\n'
        '[[pin]]\nkind = "tool"\nname = "ubuntu"\n'
        'osv_ecosystem = "Ubuntu"\nosv_name = "linux"\nrepo = "example/os"\n',
    )

    watch = read_watch_list(tmp_path)

    entry = watch.entry_of(Ecosystem.HELM, "qdrant")
    pin = watch.pin[0]
    assert (
        None if entry is None else (entry.osv_ecosystem, entry.osv_name, entry.purl),
        (pin.kind, pin.name, pin.version, pin.ecosystem, pin.osv_ecosystem, pin.osv_name),
        pin.repo,
    ) == (
        ("Debian", "qdrant", "pkg:helm/qdrant@1.19.1"),
        (ComponentKind.TOOL, "ubuntu", "", Ecosystem.UNKNOWN, "Ubuntu", "linux"),
        "example/os",
    )


@pytest.mark.parametrize(
    "text",
    [
        '[[watch]]\necosystem = "helm"\nname = "qdrant"\nrepo = "qdrant"\n',
        '[[watch]]\necosystem = "helm"\nname = "qdrant"\nrepo = "a/b"\nextra = 1\n',
        '[[watch]]\necosystem = "snap"\nname = "qdrant"\nrepo = "a/b"\n',
        '[[watch]]\necosystem = "pypi"\nname = "requests"\nrepo = "psf/requests"\n',
        "[[watch\n",
    ],
    ids=["no-owner", "extra-key", "unknown-ecosystem", "covered-elsewhere", "bad-toml"],
)
def test_a_file_that_is_wrong_is_an_error_that_names_it(tmp_path: Path, text: str) -> None:
    _write(tmp_path, text)

    with pytest.raises(InventoryError, match=r"research-watch\.toml"):
        read_watch_list(tmp_path)
