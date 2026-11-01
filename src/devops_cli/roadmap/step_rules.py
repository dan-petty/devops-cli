"""The rules an implement step reads in the checkout, and what the stage job counts for them
(#3097).

`AGENTS.md` holds the rules of every task and routes each kind of task to the document that owns
it. A person in the devcontainer reads it, so the agent of a step reads it too: the message holds
its text, verbatim, under its own heading. For a group, the message also holds the sections of the
documents that `AGENTS.md` routes the group to, when a path that the group names matches a route in
`ROUTES`. A whole document is too large for the step budget, so a route names the sections that
carry the rules for that kind of change.

A test reads the "Where to look" table of `AGENTS.md` and fails when a route names a row that the
table lacks, a document that the row does not link, a missing document, or a missing section. The
step and the stage job call `rules_sections`, so the measure counts what the step reads.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from devops_cli.ai.context_budget import truncate_to_token_limit
from devops_cli.config.constants import (
    CONST_AGENTS_MD_FILENAME,
    CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS,
)
from devops_cli.roadmap.step_files import TaskGroup, section_text

RULES_HEADING: Final[str] = "Rules of the repository (AGENTS.md)"
_LOCATION_MARK: Final[str] = "::"


@dataclass(frozen=True)
class Route:
    """One document for one kind of change. `row` is the "When you" cell of the row of `AGENTS.md`
    that sends a reader to `document`. `patterns` are globs of paths from the root of the
    checkout. `sections` are the headings of the document to give, and none means the start of
    the document."""

    row: str
    patterns: tuple[str, ...]
    document: str
    sections: tuple[str, ...] = ()


ROUTES: Final[tuple[Route, ...]] = (
    Route(
        row="write or change a test",
        patterns=("tests/**",),
        document="docs/TESTING.md",
        sections=("Which change gets a test", "Doubles", "Layout"),
    ),
    Route(
        row="write code: errors, subprocesses, HTTP, models, prompts, constants",
        patterns=("src/**",),
        document="ARCHITECTURE.md",
        sections=(
            "1. Declarative CLI Command Dispatch & OpenTelemetry Instrumentation",
            "2. End-to-End Pydantic Resource Model Interoperability",
            "3. Safe Subprocess Execution & Process Group Management",
            "5. HTTP Connection Management & Security Broker",
        ),
    ),
    Route(
        row="write code: errors, subprocesses, HTTP, models, prompts, constants",
        patterns=("src/**",),
        document="CONTRIBUTING.md",
        sections=("1. Development Philosophy & Core Invariants", "5. Naming"),
    ),
    Route(
        row="handle secrets, egress, private data, sandboxes or telemetry",
        patterns=("src/devops_cli/security/**",),
        document="SECURITY.md",
        sections=("Zero-Trust Security & Egress Safety Principles",),
    ),
    Route(
        row="take an issue to release, or a pull request to merge",
        patterns=("src/devops_cli/roadmap/**",),
        document="docs/ROADMAP_WORKFLOW.md",
        sections=("Purpose", "Labels and record keys", "The stop and retry path"),
    ),
    Route(
        row="change a manifest, the cluster or OpenTofu",
        patterns=("k8s/**",),
        document="k8s/README.md",
        sections=("Stacks Overview", "Directory Structure", "Image Pins"),
    ),
    Route(
        row="change a manifest, the cluster or OpenTofu",
        patterns=("tf/**",),
        document="tf/README.md",
    ),
)


def route_heading(document: str) -> str:
    """The heading of the sections of `document` in the message."""
    return f"# {document} (sections for your group)"


def route_text(source: Path, route: Route) -> str:
    """The text of `route` in the checkout `source`: its sections in the order of the document, or
    the start of the document when the route names none, cut to
    `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens. A document the checkout lacks gives an empty
    text."""
    path = source / route.document
    if not path.is_file():
        return ""
    body = path.read_text(encoding="utf-8")
    titles = frozenset(title.casefold() for title in route.sections)
    text = section_text(body, titles) if titles else body.strip()
    return truncate_to_token_limit(text, CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS)


def _matches(route: Route, paths: set[PurePosixPath]) -> bool:
    return any(path.full_match(pattern) for path in paths for pattern in route.patterns)


def routes_for(group: TaskGroup) -> list[Route]:
    """The routes that a path named by `group` matches, in the order of `ROUTES`. A path is a code
    span of a task, without a `::test` mark and without `./` steps. A span that is no path matches
    no route."""
    paths = {
        PurePosixPath(posixpath.normpath(span.partition(_LOCATION_MARK)[0]))
        for span in group.named_paths
    }
    return [route for route in ROUTES if _matches(route, paths)]


def rules_sections(source: Path, group: TaskGroup) -> list[str]:
    """The sections of the rules for `group`, each under its heading: `AGENTS.md` of the checkout
    first, then the routed sections of each document the checkout holds. A checkout with no
    `AGENTS.md` has no rules, and gives no section."""
    agents = source / CONST_AGENTS_MD_FILENAME
    if not agents.is_file():
        return []
    sections = [f"# {RULES_HEADING}\n\n{agents.read_text(encoding='utf-8').strip()}"]
    for route in routes_for(group):
        text = route_text(source, route)
        if text:
            sections.append(f"{route_heading(route.document)}\n\n{text}")
    return sections
