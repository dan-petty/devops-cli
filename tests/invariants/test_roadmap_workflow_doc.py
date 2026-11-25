"""The `status/*` and `owner/*` workflow labels that the package declares are the Status and Owner
values of the code (#4652, ADR 0016)."""

from __future__ import annotations

from devops_cli.config.constants import (
    CONST_ROADMAP_OWNER_VALUES,
    CONST_ROADMAP_STATUS_VALUES,
)
from devops_cli.roadmap.stores.store import (
    ItemField,
    field_label,
)
from devops_cli.roadmap.workflow_labels import WORKFLOW_LABELS

LABEL_FAMILIES = ("status/", "owner/")


def _code_labels() -> set[str]:
    """The Status and Owner labels that the code gives."""
    return {
        *(field_label(ItemField.STATUS, value) for value in CONST_ROADMAP_STATUS_VALUES),
        *(field_label(ItemField.OWNER, value) for value in CONST_ROADMAP_OWNER_VALUES),
    }


def _declared_labels() -> set[str]:
    """The Status and Owner workflow labels that the package declares."""
    return {spec.name for spec in WORKFLOW_LABELS if spec.name.startswith(LABEL_FAMILIES)}


def test_the_package_declares_the_status_and_owner_values_of_the_code() -> None:
    assert _declared_labels() == _code_labels()
