"""`.github/labels.yml` declares the label of every value of every field of a roadmap Item
(ADR 0016, #2910).

A job that writes a label GitHub does not know creates it with a default color. The file keeps
the color and the description of each label in step with the code, and `devops gh labels sync`
creates the labels the file declares.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.config.constants import CONST_ROADMAP_LABELS_PATH
from devops_cli.roadmap.store import FIELD_VALUES, field_label
from devops_cli.roadmap.title_labels import declared_label_names

ROOT = Path(__file__).resolve().parents[2]


def test_the_labels_file_declares_the_label_of_every_value_of_every_field() -> None:
    declared = set(declared_label_names((ROOT / CONST_ROADMAP_LABELS_PATH).read_text("utf-8")))
    wanted = {
        field_label(field, value) for field, values in FIELD_VALUES.items() for value in values
    }
    assert sorted(wanted - declared) == []


def test_the_owner_labels_are_declared() -> None:
    declared = declared_label_names((ROOT / CONST_ROADMAP_LABELS_PATH).read_text("utf-8"))
    assert [name for name in declared if name.startswith("owner/")] == [
        "owner/service",
        "owner/agent",
        "owner/human",
    ]
