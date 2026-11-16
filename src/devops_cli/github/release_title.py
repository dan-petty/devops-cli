"""A hidden release type cannot ship runtime code (#5224).

release-please reads the title type of each merged pull request. A type that its config marks
hidden takes no changelog line and opens no release pull request, so the Service image never gets
the change. This check refuses a hidden type when the pull request changes runtime code under
`src/devops_cli/`.

The open step of the roadmap (#5974) calls the same functions before it writes a title, and puts
the type of `release_type` in place of a hidden type, so the check and the step cannot disagree.
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
RELEASE_CONFIG_PATH: Final[str] = "release-please-config.json"
# The status that GitHub gives a file that a diff adds, and the types that ship a diff of runtime
# code under a hidden type (#5974): a new runtime file adds behavior, and a change of runtime code
# with no new file changes behavior. A person retitled #5920, which added a module, to `feat`, and
# #5940, which changed messages only, to `fix`.
ADDED_STATUS: Final[str] = "added"
_ADDS_TYPE: Final[str] = "feat"
_CHANGES_TYPE: Final[str] = "fix"


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
        f"The title type `{found.group('type')}` is hidden in {RELEASE_CONFIG_PATH}, so it ships no release, "
        f"but this pull request changes runtime code: {listed}. Use one of {shown}."
    )


def release_type(added: Sequence[str], config: Mapping[str, Any]) -> str:
    """The shown type that ships a diff of runtime code (#5974): `feat` when `added`, the paths that
    the diff adds, hold runtime code, else `fix`. When `config` hides that type too, its first shown
    type stands in."""
    wanted = _ADDS_TYPE if runtime_code(added) else _CHANGES_TYPE
    shown = releasable_types(config)
    return wanted if wanted in shown or not shown else shown[0]


def shipping_title(
    title: str, paths: Sequence[str], added: Sequence[str], config: Mapping[str, Any]
) -> str:
    """`title` with the type of `release_type` in place of its type when `hidden_type_problem`
    refuses it, and `title` with no space at its ends otherwise (#5974). The scope and the summary
    stay."""
    kept = title.strip()
    found = _TITLE.match(kept)
    if found is None or hidden_type_problem(kept, paths, config) is None:
        return kept
    return f"{release_type(added, config)}{kept[found.end('type') :]}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--files", required=True, type=Path)
    args = parser.parse_args(argv)
    from devops_cli.core.repo import find_repo_root

    config = json.loads((find_repo_root() / RELEASE_CONFIG_PATH).read_text(encoding="utf-8"))
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
