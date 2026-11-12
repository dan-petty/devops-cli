"""The tree that `devops ci` checks, as a root of its own under `tmp_path`.

`devops ci` verifies the work tree it runs in: the nearest root with a `.git` entry above the
current directory. A test that starts the gate in the repository's own root lets the gate clean the
`.coverage.*` files of the run that tests it. `ci_root` makes a tree under `tmp_path` and makes it
the current directory, so a gate run in a test cleans and caches only there.

The `bwrap` row of the gate checks whether the host can make the sandbox of a review before it
runs. `sandbox_host` gives that check a stand-in for bubblewrap and for prlimit on PATH, so a gate
run in a test reads no tool of the host and runs the row on every host.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import pytest

from tests.support.fakes.process import ProcessAnswer, ProcessFake

HEAD = "deadbeef" + 32 * "0"
"""The commit that `git rev-parse HEAD` answers in a tree of the gate."""


@pytest.fixture
def sandbox_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A host whose PATH finds a stand-in for bubblewrap and for prlimit. Nothing starts them: the
    process fake answers the check of the host, with success unless a test scripts a refusal.
    Returns the stand-in for bubblewrap."""
    bin_dir = tmp_path / "sandbox-host-bin"
    bin_dir.mkdir()
    for name in ("bwrap", "prlimit"):
        stand_in = bin_dir / name
        stand_in.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
        stand_in.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return bin_dir / "bwrap"


@pytest.fixture
def ci_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sandbox_host: Path) -> Path:
    """An empty work tree under `tmp_path`, the current directory, as the root a gate verifies, on
    the host of `sandbox_host`."""
    root = tmp_path / "tree"
    (root / ".git").mkdir(parents=True)
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def ci_head(process_fake: ProcessFake, sandbox_host: Path) -> ProcessFake:
    """The process fake of a tree with a commit, so the gate takes a fingerprint of its files, on
    the host of `sandbox_host`.

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
