"""The checks of the chart sources of the Argo CD Applications: the `charts` row of `devops ci`
(#6730).

Each module of `tests/gate/charts_checks` holds functions named `check_*` that read what
`helm template` renders from a chart source, as Argo CD applies it. `tests/gate/charts_render.py`
renders each Application once and shares the render. Helm fetches each chart from its
repository, and the Tempo check starts the Tempo image of the chart with the `docker` command of
the host. So the row needs `helm`, a container engine and the network, and the `k8s` row needs
only `kubectl` and the files of the checkout.
"""

from __future__ import annotations

import tests.gate.charts_checks as charts_checks
from tests.gate.runner import main as run_checks


def main(argv: list[str] | None = None) -> int:
    """Run the checks, and return 1 when one fails."""
    return run_checks("charts", charts_checks)
