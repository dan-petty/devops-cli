"""A hidden release type cannot ship runtime code (#5224).

release-please reads the title type of each merged pull request. A type that its config marks
hidden takes no changelog line and opens no release pull request, so the Service image never gets
the change. This check refuses a hidden type when the pull request changes runtime code under
`src/devops_cli/`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

_TITLE: Final[re.Pattern[str]] = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]*\))?!?:")
_CODE_ROOT: Final[str] = "src/devops_cli/"
_CONFIG: Final[str] = "release-please-config.json"


def hidden_types(config: Mapping[str, Any]) -> set[str]:
    """The title types that `changelog-sections` of `config` hides."""
    sections = config.get("changelog-sections")
    if not isinstance(sections, list):
        return set()
    return {
        str(section["type"])
        for section in sections
        if isinstance(section, dict) and section.get("hidden") and "type" in section
    }


def releasable_types(config: Mapping[str, Any]) -> list[str]:
    """The title types that `changelog-sections` of `config` shows."""
    sections = config.get("changelog-sections")
    if not isinstance(sections, list):
        return []
    return [
        str(section["type"])
        for section in sections
        if isinstance(section, dict) and not section.get("hidden") and "type" in section
    ]


def runtime_code(paths: Sequence[str]) -> list[str]:
    """The paths under `src/devops_cli/` that are not document data."""
    return [path for path in paths if path.startswith(_CODE_ROOT) and not path.endswith(".md")]


def hidden_type_problem(title: str, paths: Sequence[str], config: Mapping[str, Any]) -> str | None:
    """The refusal of a hidden title type that ships runtime code, or None."""
    found = _TITLE.match(title.strip())
    if found is None or found.group("type") not in hidden_types(config):
        return None
    code = runtime_code(paths)
    if not code:
        return None
    shown = ", ".join(f"`{name}`" for name in releasable_types(config))
    listed = ", ".join(f"`{path}`" for path in code)
    return (
        f"The title type `{found.group('type')}` is hidden in {_CONFIG}, so it ships no release, "
        f"but this pull request changes runtime code: {listed}. Use one of {shown}."
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--files", required=True, type=Path)
    args = parser.parse_args(argv)
    from devops_cli.core.repo import find_repo_root

    config = json.loads((find_repo_root() / _CONFIG).read_text(encoding="utf-8"))
    paths = [
        line.strip() for line in args.files.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    problem = hidden_type_problem(args.title, paths, config)
    if problem is not None:
        print(f"::error::{problem}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
