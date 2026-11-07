"""The base specs under `openspec/specs/` as the stage job reads them (#3013).

The model gets the purpose and the requirement names of each capability, so that it can choose the
capability a requirement belongs to. `check_proposal` compares the name of each ADDED requirement
with the names of the base spec of its capability, and it reads the statement of each base
requirement to refuse a plan that leaves one naming a removed command (#3287).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from pathlib import Path

_SPECS_DIRECTORY: Final[tuple[str, str]] = ("openspec", "specs")
_SPEC_FILE: Final[str] = "spec.md"
_PURPOSE: Final[re.Pattern[str]] = re.compile(r"^## Purpose[ \t]*\n(.*?)(?=^## |\Z)", re.M | re.S)
_REQUIREMENT: Final[re.Pattern[str]] = re.compile(r"^### Requirement:[ \t]*(.+?)[ \t]*$", re.M)
_SCENARIO: Final[str] = "#### Scenario:"


@dataclass(frozen=True)
class BaseSpec:
    """The purpose of a capability, on one line, the names of its requirements in file order and the
    statement of each requirement, as a pair of its name and its text on one line. A spec with no
    Purpose section has an empty purpose. A caller that gives no statements skips the check that
    reads them."""

    purpose: str
    requirements: tuple[str, ...]
    statements: tuple[tuple[str, str], ...] = ()

    def request_entry(self, name: str) -> dict[str, Any]:
        """The entry of the capability `name` in the input of the model."""
        return {"name": name, "purpose": self.purpose, "requirements": list(self.requirements)}


def _statements(text: str) -> tuple[tuple[str, str], ...]:
    """The name and the statement of each requirement of `text`, in file order. A statement runs
    from the heading of its requirement to its first scenario or the next heading, on one line."""
    matches = list(_REQUIREMENT.finditer(text))
    statements: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end() : end].split(_SCENARIO, 1)[0]
        statements.append((match.group(1).strip(), " ".join(block.split())))
    return tuple(statements)


def read_spec(text: str) -> BaseSpec:
    """The purpose, the requirement names and the statement of each requirement of the spec
    `text`."""
    found = _PURPOSE.search(text)
    purpose = " ".join(found.group(1).split()) if found else ""
    statements = _statements(text)
    return BaseSpec(purpose, tuple(name for name, _ in statements), statements)


def read_base_specs(source: Path) -> dict[str, BaseSpec]:
    """The base spec of each folder under `openspec/specs/` of the checkout `source`, by
    capability name. A folder with no `spec.md` has an empty spec."""
    specs = source.joinpath(*_SPECS_DIRECTORY)
    if not specs.is_dir():
        return {}
    return {
        folder.name: read_spec(
            (folder / _SPEC_FILE).read_text(encoding="utf-8")
            if (folder / _SPEC_FILE).is_file()
            else ""
        )
        for folder in sorted(specs.iterdir())
        if folder.is_dir()
    }
