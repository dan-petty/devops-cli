"""The downloads of a release archive (#4223).

A GitHub outage with HTTP 504 answers failed the checks of two pull requests three or four times
in a row. The installer `install_tools.py` retries each download, and each release download of the
`Dockerfile` keeps its pinned checksum.
"""

from __future__ import annotations

import ast
import re

from tests.support.dockerfile import stages
from tests.support.paths import REPO_ROOT

DOCKERFILE = REPO_ROOT / "Dockerfile"
INSTALL_TOOLS = REPO_ROOT / "src" / "devops_cli" / "commands" / "install_tools.py"


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


def _download_client_calls() -> list[ast.Call]:
    """The calls to `http_client` inside `_download_client` in `install_tools.py`."""
    tree = ast.parse(INSTALL_TOOLS.read_text(encoding="utf-8"))
    (function,) = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_download_client"
    ]
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "http_client"
    ]


def test_the_installer_builds_its_download_client_with_retries() -> None:
    """`devops install-tools` fetches promtool, trivy, helm and the other locked builds with one
    client. The client passes `retries=` to `http_client`, which wraps its transport in the retry
    transport. Its behavior is proved in `tests/commands/test_install_tools.py`."""
    (call,) = _download_client_calls()

    assert [keyword.arg for keyword in call.keywords if keyword.arg == "retries"] == ["retries"]
