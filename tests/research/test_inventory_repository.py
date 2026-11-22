"""The inventory finds pins of every kind in the real repository."""

from __future__ import annotations

import pytest

from devops_cli.research.inventory import read_inventory
from devops_cli.research.models import ComponentKind
from tests.support.paths import REPO_ROOT

# A tool is a pin outside the repository, which only the watch file names (#4363). The
# repository holds no OpenTofu configuration since the infra repository holds it (#6679), so it
# has no Terraform provider pin; the fixture repository of test_inventory.py holds one.
_NOT_IN_THE_REPOSITORY = frozenset({ComponentKind.TOOL, ComponentKind.TERRAFORM_PROVIDER})


@pytest.mark.parametrize(
    "kind", [kind for kind in ComponentKind if kind not in _NOT_IN_THE_REPOSITORY]
)
def test_the_repository_has_at_least_one_pin_of_each_kind(kind: ComponentKind) -> None:
    summary = read_inventory(REPO_ROOT).summary

    assert summary.by_kind.get(kind.value, 0) > 0


def test_every_pin_of_the_repository_has_a_line_and_a_version_or_a_constraint() -> None:
    components = read_inventory(REPO_ROOT).components

    assert [c for c in components if c.line == 0 or not c.version] == []
