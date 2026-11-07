"""The inventory finds pins of every kind in the real repository."""

from __future__ import annotations

import pytest

from devops_cli.research.inventory import read_inventory
from devops_cli.research.models import ComponentKind
from tests.support.paths import REPO_ROOT


@pytest.mark.parametrize("kind", list(ComponentKind))
def test_the_repository_has_at_least_one_pin_of_each_kind(kind: ComponentKind) -> None:
    summary = read_inventory(REPO_ROOT).summary

    assert summary.by_kind.get(kind.value, 0) > 0


def test_every_pin_of_the_repository_has_a_line_and_a_version_or_a_constraint() -> None:
    components = read_inventory(REPO_ROOT).components

    assert [c for c in components if c.line == 0 or not c.version] == []
