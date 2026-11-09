"""Every download of a release archive retries on a 5xx answer and on a connect failure (#4223).

A GitHub outage with HTTP 504 answers failed the checks of two pull requests three or four times
in a row. These tests read the files that download a release: the `Dockerfile`, the workflows with
their composite actions, and the installer `install_tools.py`. Each one fails for a download with no
retry, so a new download cannot come back without one.
"""

from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path

import pytest
import yaml

from tests.support.dockerfile import stages
from tests.support.paths import REPO_ROOT

DOCKERFILE = REPO_ROOT / "Dockerfile"
INSTALL_TOOLS = REPO_ROOT / "src" / "devops_cli" / "commands" / "install_tools.py"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
ACTIONS = REPO_ROOT / ".github" / "actions"

# A shell command ends at one of these. A backslash at the end of a line joins it to the next.
_COMMAND_END = re.compile(r"&&|\|\||[;|\n]")
# The programs that fetch a file over the network, and the option of each one that retries.
_DOWNLOADERS = {"curl": "--retry", "wget": "--tries"}


def _commands(script: str) -> list[list[str]]:
    """The commands of a shell script as lists of words, with the text of a comment dropped.

    The split is on `&&`, `||`, `;`, `|` and a new line. A command with a quote that spans a
    split, such as a `python -c "a; b"` program, is read from its first words alone: only the name
    of the program and its options matter here.
    """
    found: list[list[str]] = []
    for part in _COMMAND_END.split(script.replace("\\\n", " ")):
        try:
            words = shlex.split(part, comments=True)
        except ValueError:
            words = part.split()
        if words:
            found.append(words)
    return found


def _downloads_without_retry(script: str) -> list[str]:
    """Each curl or wget command of `script` that has no retry option."""
    return [
        " ".join(words)
        for words in _commands(script)
        if (retry := _DOWNLOADERS.get(Path(words[0]).name)) is not None
        and not any(word.startswith(retry) for word in words[1:])
    ]


def _run_scripts(document: object) -> list[str]:
    """The `run` script of each step in a parsed workflow or composite action."""
    if isinstance(document, dict):
        return [
            *([document["run"]] if isinstance(document.get("run"), str) else []),
            *(script for value in document.values() for script in _run_scripts(value)),
        ]
    if isinstance(document, list):
        return [script for item in document for script in _run_scripts(item)]
    return []


def words_text(words: list[str]) -> str:
    """The words of one Dockerfile instruction as one text."""
    return " ".join(words)


def _workflow_files() -> list[Path]:
    return sorted([*WORKFLOWS.glob("*.yml"), *ACTIONS.glob("*/action.yml")])


# ── The finder, proved on scripts of its own ──────────────────────────────────


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        (
            "curl -fsSL https://example.com/a.tar.gz -o a.tar.gz",
            ["curl -fsSL https://example.com/a.tar.gz -o a.tar.gz"],
        ),
        ("curl -fsS --retry 5 https://example.com/a", []),
        ("curl -fsS --retry-all-errors --retry-delay 2 https://example.com/a", []),
        (
            "set -e\napt-get update && curl -fsSL https://example.com/a | tar -xz",
            ["curl -fsSL https://example.com/a"],
        ),
        ("curl -fsSL \\\n  --retry 8 \\\n  https://example.com/a", []),
        ("wget https://example.com/a", ["wget https://example.com/a"]),
        ("wget --tries=5 https://example.com/a", []),
        ("echo curl is a program # curl https://example.com/a", []),
        ("uv run devops install-tools --tool trivy", []),
    ],
    ids=[
        "curl-with-no-retry",
        "curl-retry",
        "curl-retry-all-errors",
        "curl-in-a-pipe",
        "curl-retry-after-a-continuation",
        "wget-with-no-retry",
        "wget-tries",
        "curl-in-a-comment",
        "no-download",
    ],
)
def test_the_finder_names_each_download_that_has_no_retry(script: str, expected: list[str]) -> None:
    """The finder flags a curl or wget command without a retry option and nothing else."""
    found = _downloads_without_retry(script)

    assert found == expected


# ── The files that download a release ─────────────────────────────────────────


def test_the_dockerfile_fetches_no_remote_file_with_add() -> None:
    """BuildKit `ADD` of a URL has no retry option: a 504 answer fails the build, and the
    `--checksum` check names a checksum failure for it. The image fetches a release with
    `devops install-tools`, which retries."""
    remote_adds = [
        " ".join(words)
        for stage in stages(DOCKERFILE.read_text(encoding="utf-8")).values()
        for words in stage
        if words[0].upper() == "ADD"
        and any(word.startswith(("http://", "https://")) for word in words)
    ]

    assert remote_adds == []


def test_every_download_command_of_the_dockerfile_retries() -> None:
    """A `RUN` step that calls curl or wget carries the retry option of that program."""
    scripts = [
        " ".join(words[1:])
        for stage in stages(DOCKERFILE.read_text(encoding="utf-8")).values()
        for words in stage
        if words[0].upper() == "RUN"
    ]

    assert [found for script in scripts for found in _downloads_without_retry(script)] == []


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


def test_every_download_command_of_a_workflow_retries() -> None:
    """A step of a workflow or composite action that calls curl or wget carries the retry option
    of that program. The health checks of the image jobs already do."""
    found = {
        path.relative_to(REPO_ROOT).as_posix(): missing
        for path in _workflow_files()
        if (
            missing := [
                download
                for script in _run_scripts(yaml.safe_load(path.read_text(encoding="utf-8")))
                for download in _downloads_without_retry(script)
            ]
        )
    }

    assert found == {}


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
