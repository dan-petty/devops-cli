"""The downloads of a release archive (#4223).

A GitHub outage with HTTP 504 answers failed the checks of two pull requests three or four times
in a row. Each release download of the `Dockerfile` keeps its pinned checksum.
"""

from __future__ import annotations

import re

from tests.support.dockerfile import stages
from tests.support.paths import REPO_ROOT

DOCKERFILE = REPO_ROOT / "Dockerfile"


def words_text(words: list[str]) -> str:
    """The words of one Dockerfile instruction as one text."""
    return " ".join(words)


def test_every_release_download_of_the_dockerfile_keeps_its_pinned_checksum() -> None:
    """The retry weakens no check: an instruction that names a GitHub release URL also checks a
    SHA-256 of 64 hexadecimal digits with `sha256sum`."""
    unchecked = [
        " ".join(words)
        for stage in stages(DOCKERFILE.read_text(encoding="utf-8")).values()
        for words in stage
        if "github.com/" in " ".join(words)
        and "/releases/download/" in " ".join(words)
        and not (
            "sha256sum" in words_text(words) and re.search(r"\b[0-9a-f]{64}\b", words_text(words))
        )
    ]

    assert unchecked == []
