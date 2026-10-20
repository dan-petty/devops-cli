"""The programs no test starts for real, which the root conftest's `refuse_real_programs` refuses
(#1666).

They are gh, which acts as the developer's own login, and the binary of every scanner the
security scanner registry holds, which fetches rule packs and advisories from a child process the
suite's in-process network block cannot see. They are read from the registry when the run
starts, so a scanner added to it is refused with no list to edit. Building the registry once a
worker has collected its tests took 0.02-0.08 s on 2026-10-20: the conftest has already loaded
the modules it imports.
"""

from __future__ import annotations


def refused_programs() -> frozenset[str]:
    """gh, and the binary of every scanner the security scanner registry holds."""
    from devops_cli.config.constants import CONST_GH_CLI
    from devops_cli.security.registry import ScannerRegistry

    registry = ScannerRegistry(auto_load_defaults=True)
    scanners = [registry.get(name) for name in registry.list_scanners()]
    return frozenset(
        {CONST_GH_CLI, *(scanner.binary_name for scanner in scanners if scanner is not None)}
    )
