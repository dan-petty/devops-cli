"""Tests for the watch list of `.devops/research-watch.toml` (#3987)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from devops_cli.exceptions.research import InventoryError
from devops_cli.research.models import Ecosystem
from devops_cli.research.watch import WATCH_FILE, read_watch_list
from tests.support.paths import REPO_ROOT


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


# The binaries of the tools lock that the watch list leaves out, because the advisories of their
# repositories name no package that matches the pin. The comment of the file gives the reasons.
_UNMAPPED_BINARIES = frozenset({"helm", "promtool", "cloudflared"})


def test_each_release_binary_of_the_tools_lock_maps_to_its_source_or_is_left_out_on_purpose() -> (
    None
):
    """The watch list repeats the `source` of each binary of the tools lock. This test holds the two
    together, so a new binary needs its entry or a place in the list of binaries left out."""
    lock = tomllib.loads(
        (REPO_ROOT / "src/devops_cli/tools_lock/tools.lock").read_text(encoding="utf-8")
    )
    watch = read_watch_list(REPO_ROOT)

    mapped = {}
    for name in lock["binary"]:
        entry = watch.entry_of(Ecosystem.GITHUB_RELEASE, name)
        mapped[name] = None if entry is None else entry.repo

    assert mapped == {
        name: None
        if name in _UNMAPPED_BINARIES
        else tool["source"].removeprefix("https://github.com/")
        for name, tool in lock["binary"].items()
    }
