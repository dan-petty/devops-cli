"""The tree that `devops ci` checks, as a root of its own under `tmp_path`.

`devops ci` verifies the work tree it runs in: the nearest root with a `.git` entry above the
current directory. A test that starts the gate in the repository's own root lets the gate clean the
`.coverage.*` files of the run that tests it. `ci_root` makes a tree under `tmp_path` and makes it
the current directory, so a gate run in a test cleans and caches only there.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from tests.support.fakes.process import ProcessAnswer, ProcessFake

HEAD = "deadbeef" + 32 * "0"
"""The commit that `git rev-parse HEAD` answers in a tree of the gate."""


@pytest.fixture
def ci_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty work tree under `tmp_path`, the current directory, as the root a gate verifies."""
    root = tmp_path / "tree"
    (root / ".git").mkdir(parents=True)
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def ci_head(process_fake: ProcessFake) -> ProcessFake:
    """The process fake of a tree with a commit, so the gate takes a fingerprint of its files.

    Git answers `rev-parse HEAD` with a commit and every other command with success and no output,
    which is a clean tree with no tracked file.
    """
    process_fake.answer(
        lambda call: "rev-parse" in call.argv, ProcessAnswer(returncode=0, stdout=HEAD + "\n")
    )
    return process_fake


def tracked_blobs(process_fake: ProcessFake, blobs: Mapping[str, str]) -> None:
    """Make git list `blobs`, a path for each hash, as the tracked files of a clean tree."""
    listing = "".join(f"100644 {digest} 0\t{path}\n" for path, digest in blobs.items())
    process_fake.answer(
        lambda call: "ls-files" in call.argv, ProcessAnswer(returncode=0, stdout=listing)
    )
