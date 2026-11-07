"""Every pin of a repository as one typed list of components (#3896).

The readers parse the files of the repository with a parser for each format. They start no program
and make no request.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from devops_cli.research.container_pins import read_container_pins
from devops_cli.research.k8s_pins import read_k8s_pins
from devops_cli.research.models import Component, Ecosystem, Inventory, InventorySummary
from devops_cli.research.python_pins import read_python_pins
from devops_cli.research.terraform_pins import read_terraform_pins
from devops_cli.research.tool_pins import read_tool_pins
from devops_cli.research.workflow_pins import read_workflow_pins


def summarize(components: list[Component]) -> InventorySummary:
    """The counts of `components` in total and for each kind and ecosystem."""
    by_ecosystem = Counter(component.ecosystem.value for component in components)
    return InventorySummary(
        total=len(components),
        unknown=by_ecosystem[Ecosystem.UNKNOWN.value],
        by_kind=dict(sorted(Counter(component.kind.value for component in components).items())),
        by_ecosystem=dict(sorted(by_ecosystem.items())),
    )


def read_inventory(root: Path) -> Inventory:
    """The inventory of the repository at `root`, ordered by file, then line, then name."""
    components = [
        *read_python_pins(root),
        *read_tool_pins(root),
        *read_container_pins(root),
        *read_workflow_pins(root),
        *read_k8s_pins(root),
        *read_terraform_pins(root),
    ]
    components.sort(key=lambda c: (c.file, c.line, c.name, c.version))
    return Inventory(components=components, summary=summarize(components))
