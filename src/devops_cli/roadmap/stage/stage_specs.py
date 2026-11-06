"""The base specs under `openspec/specs/` as the stage job reads them (#3013).

The model gets the purpose and the requirement names of each capability, so that it can choose the
capability a requirement belongs to. `check_proposal` compares the name of each ADDED requirement
with the names of the base spec of its capability.
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


@dataclass(frozen=True)
class BaseSpec:
    """The purpose of a capability, on one line, and the names of its requirements in file order.
    A spec with no Purpose section has an empty purpose."""

    purpose: str
    requirements: tuple[str, ...]

    def request_entry(self, name: str) -> dict[str, Any]:
        """The entry of the capability `name` in the input of the model."""
        return {"name": name, "purpose": self.purpose, "requirements": list(self.requirements)}


def read_spec(text: str) -> BaseSpec:
    """The purpose and the requirement names of the spec `text`."""
    found = _PURPOSE.search(text)
    purpose = " ".join(found.group(1).split()) if found else ""
    return BaseSpec(purpose, tuple(_REQUIREMENT.findall(text)))


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
