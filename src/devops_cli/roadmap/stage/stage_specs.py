"""The base specs under `openspec/specs/` as the stage job reads them (#3013).

The model gets the purpose and the requirement names of each capability, so that it can choose the
capability a requirement belongs to. `openspec list --specs --json` names the capabilities, flat as
`<name>` or nested as `<area>/<name>` (#4622), and the job reads the file of each one. `check_proposal` compares the name of each ADDED requirement
with the names of the base spec of its capability, and it reads the statement of each base
requirement to refuse a plan that leaves one naming a removed command (#3287).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from devops_cli.roadmap.step_files import code_spans

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from devops_cli.openspec.tool import OpenSpecTool

REQUIREMENT_TEXT_MAX_COUNT: Final[int] = 12
"""The maximum number of base requirements that the stage context holds."""

REQUIREMENT_TEXT_MAX_CHARS: Final[int] = 6000
"""The maximum characters of base requirement text that the stage context holds."""

_SPECS_DIRECTORY: Final[tuple[str, str]] = ("openspec", "specs")
_SPEC_FILE: Final[str] = "spec.md"
_PURPOSE: Final[re.Pattern[str]] = re.compile(r"^## Purpose[ \t]*\n(.*?)(?=^## |\Z)", re.M | re.S)
_REQUIREMENT: Final[re.Pattern[str]] = re.compile(r"^### Requirement:[ \t]*(.+?)[ \t]*$", re.M)
_SCENARIO: Final[str] = "#### Scenario:"
_SCENARIO_NAME: Final[re.Pattern[str]] = re.compile(r"^#### Scenario:[ \t]*(.+?)[ \t]*$", re.M)


@dataclass(frozen=True)
class BaseSpec:
    """The purpose of a capability, on one line, the names of its requirements in file order, the
    statement of each requirement, as a pair of its name and its text on one line, and the name of
    each scenario of the spec. A spec with no Purpose section has an empty purpose. A caller that
    gives no statements skips the check that reads them."""

    purpose: str
    requirements: tuple[str, ...]
    statements: tuple[tuple[str, str], ...] = ()
    scenarios: tuple[str, ...] = ()

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
    return BaseSpec(
        purpose,
        tuple(name for name, _ in statements),
        statements,
        tuple(match.group(1) for match in _SCENARIO_NAME.finditer(text)),
    )


def spec_names(tool: OpenSpecTool, source: Path) -> list[str]:
    """The name of each capability that `openspec list --specs --json` finds in the checkout
    `source`, in the order of the tool."""
    listing = tool.read_json(["list", "--specs", "--json"], source)
    return [spec["id"] for spec in listing["specs"]]


def read_base_specs(source: Path, tool: OpenSpecTool | None) -> dict[str, BaseSpec]:
    """The base spec of each capability that OpenSpec finds under `openspec/specs/` of the
    checkout `source`, by capability name. With no OpenSpec, the job knows no base spec, as the
    tool `read_spec` reads none."""
    specs = source.joinpath(*_SPECS_DIRECTORY)
    if tool is None or not specs.is_dir():
        return {}
    return {
        name: read_spec(path.read_text(encoding="utf-8"))
        for name in sorted(spec_names(tool, source))
        if (path := specs / name / _SPEC_FILE).is_file()
    }


def _matches_spans(statement: str, spans: tuple[str, ...]) -> bool:
    statement_folded = statement.casefold()
    return any(span.casefold() in statement_folded for span in spans if span)


def requirement_text(specs: Mapping[str, BaseSpec] | None, *, title: str, body: str) -> str:
    """The bounded requirement text of the base specs that `title` and `body` cite."""
    if not specs:
        return ""
    spans = tuple(dict.fromkeys(code_spans(f"{title}\n{body}")))
    issue_text = f"{title}\n{body}"

    name_matches: list[tuple[str, str, str]] = []
    text_matches: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    for cap_name, spec in specs.items():
        cap_cited = cap_name in issue_text
        for req_name, statement in spec.statements:
            if cap_cited or req_name in issue_text:
                name_matches.append((cap_name, req_name, statement))
                seen.add((cap_name, req_name))

    for cap_name, spec in specs.items():
        for req_name, statement in spec.statements:
            if (cap_name, req_name) not in seen and _matches_spans(statement, spans):
                text_matches.append((cap_name, req_name, statement))
                seen.add((cap_name, req_name))

    all_matches = (name_matches + text_matches)[:REQUIREMENT_TEXT_MAX_COUNT]
    lines: list[str] = []
    current_chars = 0
    for cap_name, req_name, statement in all_matches:
        line = f"- {cap_name}: {req_name}: {statement}"
        extra = len(line) + (1 if lines else 0)
        if current_chars + extra <= REQUIREMENT_TEXT_MAX_CHARS:
            lines.append(line)
            current_chars += extra

    return "\n".join(lines)
