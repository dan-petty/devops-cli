"""The OpenSpec trees the gate is recorded and tested over (#1844).

A scenario is a small checkout: `openspec/` with a configuration and some change folders, the
generated skills the repository commits, and a git history in which the changes merged one commit
each, in the order named. `build_scenario` writes it. `tests/support/openspec_recording.py` runs
the real, pinned OpenSpec over each scenario and keeps what it answered, and
`tests/support/fakes/openspec.py` answers a test's runs of the same commands from that record, so
the tree a test builds and the tree the record was made over are the same.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

# A configuration with one rule, written in the folded style the committed one uses.
CONFIG = """schema: spec-driven

context: |
  Example context for every artifact.

rules:
  proposal:
    - >-
      Cite the issue as #<issue> in Why.
"""

# What the gate finds in a configuration OpenSpec reads but ignores, with exit 0: a rule that
# YAML read as a mapping, a rule under an artifact that does not exist, and a context over 50 KB.
CONFIG_WITH_WARNINGS = """schema: spec-driven

context: |
  {context}

rules:
  proposal:
    - Cite the issue: in Why.
  nonsense:
    - >-
      A rule for an artifact that does not exist.
""".format(context="x" * 52_000)

_PURPOSE = (
    "## Purpose\n\nExport every widget to a file in a stable format that other tools can read.\n\n"
)
_WHY = "## Why\n\nIssue #{issue} asks for it, and nothing else in the checkout does it yet.\n\n"
_PROPOSAL_REST = (
    "## What Changes\n\nThe export.\n\n## Feasibility\n\nChecked against the real tool.\n\n"
    "## Existing Tool Considered\n\nNone covers it.\n"
)
_TICKED = "## 1. Export\n\n- [x] 1.1 Write the file\n"
_UNTICKED = "## 1. Export\n\n- [ ] 1.1 Write the file\n"


@dataclass(frozen=True)
class OpenSpecScenario:
    """A checkout: its files by path from its root, and the changes it committed one by one, in
    the order they merged. A change folder not named in `merged` is not committed."""

    files: dict[str, str]
    merged: tuple[str, ...] = ()


def delta(operation: str, requirement: str, text: str, *, purpose: bool = False) -> str:
    """A spec delta applying `operation` to `requirement`, starting with a Purpose when it
    creates its capability."""
    return (
        f"{_PURPOSE if purpose else ''}## {operation} Requirements\n\n"
        f"### Requirement: {requirement}\n{text}\n\n"
        f"#### Scenario: {requirement} works\n- **WHEN** the user exports\n"
        "- **THEN** a file is written\n"
    )


def rename_delta(old: str, new: str) -> str:
    """A spec delta renaming requirement `old` to `new`."""
    return (
        f"## RENAMED Requirements\n\n- FROM: `### Requirement: {old}`\n"
        f"- TO: `### Requirement: {new}`\n"
    )


def change(
    name: str, capability: str = "", spec_delta: str = "", *, ticked: bool = False
) -> dict[str, str]:
    """The files of the change folder `name`: one that changes `capability` with `spec_delta`, or,
    given none, one that declares `skip_specs`."""
    folder = f"openspec/changes/{name}"
    issue = name.split("-")[0]
    skip = "" if spec_delta else "skip_specs: true\n"
    files = {
        f"{folder}/.openspec.yaml": f"schema: spec-driven\ncreated: 2026-10-22\n{skip}",
        f"{folder}/proposal.md": _WHY.format(issue=issue) + _PROPOSAL_REST,
        f"{folder}/tasks.md": _TICKED if ticked else _UNTICKED,
    }
    if spec_delta:
        files[f"{folder}/specs/{capability}/spec.md"] = spec_delta
    return files


def _scenario(
    *changes: dict[str, str], merged: tuple[str, ...] = (), config: str = CONFIG
) -> OpenSpecScenario:
    """A scenario holding `changes` and an empty `openspec/specs` and archive."""
    files = {
        "openspec/config.yaml": config,
        "openspec/specs/.gitkeep": "",
        "openspec/changes/archive/.gitkeep": "",
    }
    for files_of_change in changes:
        files.update(files_of_change)
    return OpenSpecScenario(files, merged)


_WIDGET = "The system SHALL export every widget to a file."
_JSON = "The system SHALL export every widget to a file in JSON."
_YAML = "The system SHALL export every widget to a file in YAML."
_AGAIN = "The system SHALL export every widget to a file, again."

SCENARIOS: dict[str, OpenSpecScenario] = {
    "empty": _scenario(),
    "pair": _scenario(
        change(
            "1901-export-widgets",
            "widget-export",
            delta("ADDED", "Export widgets", _WIDGET, purpose=True),
            ticked=True,
        ),
        change("1902-export-json", "widget-export", delta("MODIFIED", "Export widgets", _JSON)),
        merged=("1901-export-widgets", "1902-export-json"),
    ),
    "merged-out-of-issue-order": _scenario(
        change(
            "1930-export-widgets",
            "widget-export",
            delta("ADDED", "Export widgets", _WIDGET, purpose=True),
        ),
        change("1920-export-json", "widget-export", delta("MODIFIED", "Export widgets", _JSON)),
        merged=("1930-export-widgets", "1920-export-json"),
    ),
    "missing-purpose": _scenario(
        change(
            "1910-export-widgets",
            "widget-export",
            delta("ADDED", "Export widgets", _WIDGET),
            ticked=True,
        ),
        merged=("1910-export-widgets",),
    ),
    "modified-spec-absent": _scenario(
        change(
            "1911-export-json",
            "widget-export",
            delta("MODIFIED", "Export widgets", _JSON),
            ticked=True,
        ),
        merged=("1911-export-json",),
    ),
    "duplicate-added": _scenario(
        change(
            "1912-export-widgets",
            "widget-export",
            delta("ADDED", "Export widgets", _WIDGET, purpose=True),
        ),
        change(
            "1913-export-widgets-again",
            "widget-export",
            delta("ADDED", "Export widgets", _AGAIN),
        ),
        merged=("1912-export-widgets", "1913-export-widgets-again"),
    ),
    "requirement-modified-twice": _scenario(
        change(
            "1914-export-widgets",
            "widget-export",
            delta("ADDED", "Export widgets", _WIDGET, purpose=True),
        ),
        change("1915-export-json", "widget-export", delta("MODIFIED", "Export widgets", _JSON)),
        change("1916-export-yaml", "widget-export", delta("MODIFIED", "Export widgets", _YAML)),
        merged=("1914-export-widgets", "1915-export-json", "1916-export-yaml"),
    ),
    "skip-specs-change": _scenario(
        change("1918-reword-docs", ticked=True), merged=("1918-reword-docs",)
    ),
    "requirement-renamed-and-modified": _scenario(
        change(
            "1921-export-widgets",
            "widget-export",
            delta("ADDED", "Export widgets", _WIDGET, purpose=True),
        ),
        change("1922-export-json", "widget-export", delta("MODIFIED", "Export widgets", _JSON)),
        change(
            "1923-dump-widgets", "widget-export", rename_delta("Export widgets", "Dump widgets")
        ),
        merged=("1921-export-widgets", "1922-export-json", "1923-dump-widgets"),
    ),
    "unknown-metadata-key": _scenario(
        {
            **change(
                "1917-export-widgets",
                "widget-export",
                delta("ADDED", "Export widgets", _WIDGET, purpose=True),
            ),
            "openspec/changes/1917-export-widgets/.openspec.yaml": (
                "schema: spec-driven\ncreated: 2026-10-22\nmilestone: v0.2.39\n"
            ),
        },
        merged=("1917-export-widgets",),
    ),
    "archived-change-with-unticked-task": _scenario(
        {
            f"openspec/changes/archive/2026-10-01-1900-old-export/{path}": text
            for path, text in {
                ".openspec.yaml": "schema: spec-driven\ncreated: 2026-10-01\n",
                "proposal.md": _WHY.format(issue="1900") + _PROPOSAL_REST,
                "tasks.md": _UNTICKED,
            }.items()
        },
    ),
    "configuration-openspec-ignores": _scenario(config=CONFIG_WITH_WARNINGS),
}


def _change_names(files: dict[str, str]) -> list[str]:
    """The names of the active change folders `files` holds, in path order."""
    pattern = re.compile(r"openspec/changes/(?!archive/)([^/]+)/")
    return sorted({match[1] for path in files if (match := pattern.match(path))})


def _git(root: Path, *args: str) -> None:
    """Run git in `root` as a fixed author, so a commit needs no identity of the machine's."""
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def build_scenario(name: str, root: Path, committed_skills: Path) -> None:
    """Write scenario `name` under `root` and commit it: the skills read from `committed_skills`
    and everything but the changes first, then each change in the order it merged. A change the
    scenario does not name as merged is left uncommitted."""
    from devops_cli.openspec.skills import generated_files

    scenario = SCENARIOS[name]
    for path, text in scenario.files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text, encoding="utf-8")
    for path, content in generated_files(committed_skills).items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_bytes(content)
    _git(root, "init", "-q")
    held_back = [f"openspec/changes/{change_name}" for change_name in _change_names(scenario.files)]
    _git(root, "add", "-A", "--", ".", *(f":!{path}" for path in held_back))
    _git(root, "commit", "-q", "--allow-empty", "-m", "base")
    for change_name in scenario.merged:
        _git(root, "add", f"openspec/changes/{change_name}")
        _git(root, "commit", "-q", "-m", change_name)
