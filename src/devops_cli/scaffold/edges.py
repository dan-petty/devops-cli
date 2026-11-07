"""The edges a source module reaches, and the shared fake fixture of each (#3204).

`devops new test` asks the test it writes for the fixture of each edge that the source module
reaches. A module reaches an edge when it imports the seam module of the edge. A test in
`tests/scaffold/` holds every fixture of the table to a fixture that `tests/support/` defines.
"""

from __future__ import annotations

import ast
from typing import Final

# The seam module of an edge and the fixture that installs its fake, in the order a test asks
# for them. A module that imports the seam or a submodule of it reaches the edge.
EDGE_FIXTURES: Final[tuple[tuple[str, str], ...]] = (
    ("devops_cli.core.process", "process_fake"),
    ("devops_cli.github.session", "github_api"),
    ("devops_cli.github.rate_limiter", "github_api"),
    ("devops_cli.k8s.api", "cluster"),
    ("devops_cli.docker.engine", "docker_daemon"),
    ("devops_cli.http.entry", "web"),
    ("devops_cli.http.egress", "dns"),
    ("devops_cli.config.os_keyring", "keyring_store"),
    ("devops_cli.security.tool_executor", "tool_executor_fake"),
    ("devops_cli.roadmap.stores.store", "roadmap_store"),
    ("devops_cli.openspec.tool", "openspec_fake"),
    ("devops_cli.ai.mcp.dispatcher", "mcp_dispatcher"),
    ("devops_cli.valkey.client", "valkey"),
    ("devops_cli.ai.rag.qdrant", "qdrant"),
    ("devops_cli.ai.rag.embeddings", "embedder"),
)


def _imported_modules(source: str) -> set[str]:
    """The modules a source text imports, and each `from` name as a submodule candidate."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def edge_fixtures(source: str) -> list[str]:
    """The fixtures of the edges that a source text reaches, each once, in table order."""
    modules = _imported_modules(source)
    fixtures: list[str] = []
    for seam, fixture in EDGE_FIXTURES:
        reached = any(module == seam or module.startswith(f"{seam}.") for module in modules)
        if reached and fixture not in fixtures:
            fixtures.append(fixture)
    return fixtures
