"""The package declares the workflow labels, and `.github/labels.yml` declares the labels of the
repository only (ADR 0016, #2910, #4652).

A job that writes a label GitHub does not know creates it with a default color. The package list
keeps the color and the description of each label that the roadmap code reads or writes, and
`devops roadmap onboard --confirm` and `devops gh label sync` create the labels of the package
and of the file.
"""

from __future__ import annotations

import yaml

from devops_cli.config.constants import (
    CONST_ROADMAP_COMMIT_TYPE_LABELS,
    CONST_ROADMAP_CRITICAL_FIX_LABELS,
    CONST_ROADMAP_EPIC_LABEL,
    CONST_ROADMAP_LABELS_PATH,
    CONST_ROADMAP_SOURCE_AGENT_LABEL,
)
from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL
from devops_cli.roadmap.stores.store import FIELD_VALUES, ItemField, field_label
from devops_cli.roadmap.title_labels import declared_label_specs
from devops_cli.roadmap.workflow_labels import (
    LABEL_COLOR_TOKENS,
    WORKFLOW_LABELS,
    WORKFLOW_TYPE_LABELS,
    LabelColor,
)
from tests.support.paths import REPO_ROOT

WORKFLOW_FAMILIES = (
    "type/",
    "status/",
    "priority/",
    "value/",
    "effort/",
    "owner/",
    "review/",
    "plan/",
    "source/",
)


def _file_labels() -> list[dict[str, str]]:
    """The labels that the text of the repository's `.github/labels.yml` holds, as written."""
    return yaml.safe_load((REPO_ROOT / CONST_ROADMAP_LABELS_PATH).read_text("utf-8"))


def test_the_package_declares_every_label_the_roadmap_code_writes() -> None:
    written = {
        *(field_label(field, value) for field, values in FIELD_VALUES.items() for value in values),
        *CONST_ROADMAP_COMMIT_TYPE_LABELS.values(),
        CONST_ROADMAP_EPIC_LABEL,
        *CONST_ROADMAP_CRITICAL_FIX_LABELS,
        CONST_ROADMAP_SOURCE_AGENT_LABEL,
        PLAN_NEEDS_FIX_LABEL,
    }
    assert sorted(written - {spec.name for spec in WORKFLOW_LABELS}) == []


def test_the_owner_labels_are_declared() -> None:
    assert [spec.name for spec in WORKFLOW_LABELS if spec.name.startswith("owner/")] == [
        "owner/service",
        "owner/agent",
        "owner/human",
    ]


def test_the_type_labels_are_the_workflow_types_but_the_epic() -> None:
    assert WORKFLOW_TYPE_LABELS == (
        "type/feature",
        "type/bug",
        "type/security",
        "type/refactor",
        "type/docs",
        "type/infra",
        "type/test",
        "type/chore",
    )


def test_the_labels_file_holds_no_workflow_label() -> None:
    names = [label["name"] for label in _file_labels()]
    assert [name for name in names if name.startswith(WORKFLOW_FAMILIES)] == []
    assert sorted({spec.name for spec in WORKFLOW_LABELS} & set(names)) == []


def test_a_labels_file_gives_the_workflow_labels_then_its_own() -> None:
    text = '- name: scope/cli\n  color: "000000"\n- name: status/new\n  color: "FFFFFF"\n'

    specs = declared_label_specs(text)

    package = {spec.name: spec for spec in WORKFLOW_LABELS}
    assert (
        [spec.name for spec in specs],
        next(spec for spec in specs if spec.name == "status/new"),
    ) == ([*package, "scope/cli"], package["status/new"])


def test_each_label_color_is_a_design_token_color() -> None:
    import json

    tokens = {
        **json.loads(
            (REPO_ROOT / "src/devops_cli/design/tokens-base.json").read_text(encoding="utf-8")
        ),
        **json.loads(
            (REPO_ROOT / "src/devops_cli/design/tokens-light.json").read_text(encoding="utf-8")
        ),
    }
    colors = {spec.color for spec in WORKFLOW_LABELS} | {
        label["color"].upper() for label in _file_labels()
    }
    assert sorted(colors - {color.value for color in LabelColor}) == []
    assert set(LABEL_COLOR_TOKENS) == set(LabelColor)
    assert {
        color: tokens[token].lstrip("#").upper() for color, token in LABEL_COLOR_TOKENS.items()
    } == {color: color.value for color in LabelColor}


def test_each_priority_has_its_own_color() -> None:
    priorities = [spec.color for spec in WORKFLOW_LABELS if spec.name.startswith("priority/")]
    assert len(set(priorities)) == len(priorities) == len(FIELD_VALUES[ItemField.PRIORITY])
