"""The Renovate configuration: the shared preset `.github/renovate/base.json` that every Service
repository extends, and the repository parts in `.github/renovate.json` (#4896)."""

from __future__ import annotations

import json
import re
from typing import Any

from tests.support.paths import REPO_ROOT


def _load(*parts: str) -> dict[str, Any]:
    return json.loads(REPO_ROOT.joinpath(*parts).read_text(encoding="utf-8"))


def _renovate() -> dict[str, Any]:
    return _load(".github", "renovate.json")


def _preset() -> dict[str, Any]:
    return _load(".github", "renovate", "base.json")


def test_the_preset_writes_no_git_author() -> None:
    """GitHub writes and signs each commit as the App bot with its noreply address, so no
    config holds an email address."""
    text = json.dumps([_preset(), _renovate()])

    assert (
        _preset()["platformCommit"],
        "gitAuthor" in text,
        re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text),
    ) == ("enabled", False, [])
