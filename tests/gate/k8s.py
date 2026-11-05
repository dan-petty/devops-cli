"""The checks of the committed Kubernetes manifests: the `k8s` row of `devops ci` (#2164).

Each module of `tests/gate/k8s_checks` holds functions named `check_*` that read what
`kubectl kustomize` renders from the manifests of the repository, as Argo CD applies it.
`tests/gate/k8s_render.py` renders a directory once and shares the render, so each application
is rendered once for the whole row, and no pytest worker starts `kubectl`.
"""

from __future__ import annotations

import tests.gate.k8s_checks as k8s_checks
from tests.gate.runner import main as run_checks


def main(argv: list[str] | None = None) -> int:
    """Run the checks, and return 1 when one fails."""
    return run_checks("k8s", k8s_checks)
