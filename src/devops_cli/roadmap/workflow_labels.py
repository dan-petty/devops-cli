"""The workflow labels: the labels that the roadmap code reads or writes (#4652).

Each repository that the roadmap jobs serve needs the same workflow labels, so the package
declares them once, with the color and the description of each. `.github/labels.yml` of a
repository declares only its own labels, such as `scope/*`. A reader of that file gets the
workflow labels first, then each label of the file that no workflow label names
(`title_labels.declared_label_specs`). `devops roadmap onboard --confirm` and
`devops gh label sync` create the labels of both sources on GitHub.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Final

from devops_cli.config.constants import CONST_ROADMAP_EPIC_LABEL, CONST_ROADMAP_TYPE_LABEL_PREFIX
from devops_cli.github.labels import LabelSpec


class LabelColor(StrEnum):
    """The colors of the labels: light hex values of the design tokens (#4738), one for each
    meaning. Each comment names the token."""

    PRIORITY_P0 = "B3261E"  # color-status-error
    PRIORITY_P1 = "946200"  # color-status-warn
    PRIORITY_P2 = "0B6E8A"  # color-accent
    PRIORITY_P3 = "5F5F59"  # color-fg-muted
    ADDS_BEHAVIOR = "A463F2"  # color-data-cat-1
    FIXES_DEFECT = "E7298A"  # color-data-cat-2
    KEEPS_BEHAVIOR = "002D9C"  # color-data-cat-3
    STOPS_WORK = "86867F"  # color-border-strong
    RECORD = "DCDCD6"  # color-border


# The design token of each color, so a test can hold the hex value to the token files (#4786).
LABEL_COLOR_TOKENS: Final[dict[LabelColor, str]] = {
    LabelColor.PRIORITY_P0: "color-status-error",
    LabelColor.PRIORITY_P1: "color-status-warn",
    LabelColor.PRIORITY_P2: "color-accent",
    LabelColor.PRIORITY_P3: "color-fg-muted",
    LabelColor.ADDS_BEHAVIOR: "color-data-cat-1",
    LabelColor.FIXES_DEFECT: "color-data-cat-2",
    LabelColor.KEEPS_BEHAVIOR: "color-data-cat-3",
    LabelColor.STOPS_WORK: "color-border-strong",
    LabelColor.RECORD: "color-border",
}


def _label(name: str, color: LabelColor, description: str) -> LabelSpec:
    return LabelSpec(name=name, color=color.value, description=description)


WORKFLOW_LABELS: Final[tuple[LabelSpec, ...]] = (
    _label("type/feature", LabelColor.ADDS_BEHAVIOR, "Type feature: a new function"),
    _label("type/bug", LabelColor.FIXES_DEFECT, "Type bug: the code does not do what it must"),
    _label("type/security", LabelColor.FIXES_DEFECT, "Type security: a vulnerability or a leak"),
    _label(
        "type/refactor", LabelColor.KEEPS_BEHAVIOR, "Type refactor: a new structure, same behavior"
    ),
    _label("type/docs", LabelColor.RECORD, "Type docs: a change to the documents"),
    _label("type/infra", LabelColor.KEEPS_BEHAVIOR, "Type infra: the build, CI, images or cluster"),
    _label("type/test", LabelColor.KEEPS_BEHAVIOR, "Type test: a new or changed test"),
    _label("type/chore", LabelColor.RECORD, "Type chore: maintenance, such as a dependency update"),
    _label(
        CONST_ROADMAP_EPIC_LABEL, LabelColor.RECORD, "Type epic: a tracker; its sub-issues do work"
    ),
    _label("status/new", LabelColor.RECORD, "Status New: the item is not ready yet"),
    _label(
        "status/ready",
        LabelColor.RECORD,
        "Status Ready: problem, acceptance criteria and an answer to each key question",
    ),
    _label(
        "status/planned",
        LabelColor.RECORD,
        "Status Planned: the plan is merged and the item waits for its implementation",
    ),
    _label(
        "status/in-progress", LabelColor.RECORD, "Status In Progress: an owner works on the item"
    ),
    _label(
        "status/in-review",
        LabelColor.RECORD,
        "Status In Review: the pull request of the item is open",
    ),
    _label(
        "status/blocked",
        LabelColor.STOPS_WORK,
        "Status Blocked: a dependency or a stopped job holds the item",
    ),
    _label(
        "priority/p0-critical",
        LabelColor.PRIORITY_P0,
        "Priority P0: a release blocker or a critical defect",
    ),
    _label(
        "priority/p1-high",
        LabelColor.PRIORITY_P1,
        "Priority P1: high-impact work for the next planned milestone",
    ),
    _label("priority/p2-medium", LabelColor.PRIORITY_P2, "Priority P2: standard work"),
    _label("priority/p3-low", LabelColor.PRIORITY_P3, "Priority P3: a small improvement"),
    _label("value/high", LabelColor.RECORD, "Value High: the delivery of the item matters much"),
    _label("value/medium", LabelColor.RECORD, "Value Medium"),
    _label("value/low", LabelColor.RECORD, "Value Low: the delivery of the item matters little"),
    _label("effort/high", LabelColor.RECORD, "Effort High: much work, in one pull request"),
    _label("effort/medium", LabelColor.RECORD, "Effort Medium"),
    _label("effort/low", LabelColor.RECORD, "Effort Low: little work"),
    _label(
        "owner/service",
        LabelColor.RECORD,
        "Owner Service: the roadmap Service works on the item in a Job",
    ),
    _label("owner/agent", LabelColor.RECORD, "Owner Agent: an agentic coder works on the item"),
    _label("owner/human", LabelColor.RECORD, "Owner Human: a person works on the item"),
    _label(
        "needs-split",
        LabelColor.STOPS_WORK,
        "Too big for one pull request; split it before work starts",
    ),
    _label(
        "plan/needs-fix",
        LabelColor.STOPS_WORK,
        "The model review of the plan found an open finding; the plan stays in draft",
    ),
    _label("source/agent", LabelColor.RECORD, "Filed by an agent"),
)
"""The workflow labels, in the order of their families."""

WORKFLOW_TYPE_LABELS: Final[tuple[str, ...]] = tuple(
    spec.name
    for spec in WORKFLOW_LABELS
    if spec.name.startswith(CONST_ROADMAP_TYPE_LABEL_PREFIX)
    and spec.name != CONST_ROADMAP_EPIC_LABEL
)
"""The `type/*` labels that an item may get, `type/epic` aside."""


def with_workflow_labels(specs: Iterable[LabelSpec]) -> list[LabelSpec]:
    """The workflow labels, then each label of `specs` that no workflow label names. A workflow
    label keeps the color and the description of the package."""
    names = {spec.name for spec in WORKFLOW_LABELS}
    return [*WORKFLOW_LABELS, *(spec for spec in specs if spec.name not in names)]


__all__ = ["WORKFLOW_LABELS", "WORKFLOW_TYPE_LABELS", "LabelColor", "with_workflow_labels"]
