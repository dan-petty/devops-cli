"""Test-first specification for architectural and stylistic invariants in devops-cli."""

from __future__ import annotations

import ast
from pathlib import Path

from devops_cli.exceptions.base import DevOpsCLIError


def test_exception_taxonomy_inheritance() -> None:
    """All domain exceptions in devops_cli.exceptions must inherit from DevOpsCLIError."""
    import devops_cli.exceptions as exc_mod

    for name in exc_mod.__all__:
        cls = getattr(exc_mod, name)
        if isinstance(cls, type) and issubclass(cls, Exception):
            assert issubclass(cls, DevOpsCLIError), (
                f"Exception {name} does not inherit from DevOpsCLIError"
            )


def test_domain_specific_exceptions_exist() -> None:
    """Ensure newly established domain exceptions are defined with correct error codes."""
    from devops_cli.exceptions.ai import (
        DocsIngestionError,
        HarnessExecutionError,
        HarnessValidationError,
        LibraryIngestionError,
        LibraryNotFoundError,
        ModelBundleError,
    )
    from devops_cli.exceptions.docker import DockerError, DockerSandboxError
    from devops_cli.exceptions.k8s import (
        ChaosExecutionError,
        KubernetesContextError,
        KubernetesError,
    )
    from devops_cli.exceptions.vault import (
        VaultConfigurationError,
        VaultError,
        VaultKeyError,
        VaultOperationError,
    )

    assert issubclass(DockerSandboxError, DockerError)
    assert issubclass(DockerError, DevOpsCLIError)
    assert issubclass(VaultKeyError, VaultError)
    assert issubclass(VaultConfigurationError, VaultError)
    assert issubclass(VaultOperationError, VaultError)
    assert issubclass(KubernetesContextError, KubernetesError)
    assert issubclass(ChaosExecutionError, KubernetesError)
    assert issubclass(ModelBundleError, DevOpsCLIError)
    assert issubclass(HarnessValidationError, DevOpsCLIError)
    assert issubclass(HarnessExecutionError, DevOpsCLIError)
    assert issubclass(LibraryIngestionError, DevOpsCLIError)
    assert issubclass(LibraryNotFoundError, LibraryIngestionError)
    assert issubclass(DocsIngestionError, DevOpsCLIError)

    lib_err = LibraryIngestionError("library ingest failed")
    assert lib_err.error_code == "LIBRARY_INGESTION_ERROR"
    assert lib_err.exit_code == 1

    lib_nf_err = LibraryNotFoundError("library not found")
    assert lib_nf_err.error_code == "LIBRARY_NOT_FOUND_ERROR"
    assert lib_nf_err.exit_code == 1

    docs_err = DocsIngestionError("docs ingest failed")
    assert docs_err.error_code == "DOCS_INGESTION_ERROR"
    assert docs_err.exit_code == 1

    err = DockerSandboxError("test sandbox error")
    assert err.error_code == "DOCKER_SANDBOX_ERROR"
    assert err.exit_code == 1

    v_err = VaultKeyError("missing key")
    assert v_err.error_code == "VAULT_KEY_ERROR"

    k_err = KubernetesContextError("invalid context")
    assert k_err.error_code == "K8S_CONTEXT_ERROR"

    h_val = HarnessValidationError("invalid harness schema")
    assert h_val.error_code == "HARNESS_VALIDATION_ERROR"
    assert h_val.exit_code == 1

    h_exec = HarnessExecutionError("harness run failed")
    assert h_exec.error_code == "HARNESS_EXECUTION_ERROR"
    assert h_exec.exit_code == 1

    from devops_cli.ai.rag.embeddings import EmbeddingsError
    from devops_cli.exceptions.telemetry import LogfireConfigurationError, TelemetryError

    assert issubclass(TelemetryError, DevOpsCLIError)
    assert issubclass(LogfireConfigurationError, TelemetryError)

    t_err = TelemetryError("telemetry failed")
    assert t_err.error_code == "TELEMETRY_ERROR"
    assert t_err.exit_code == 1

    lf_err = LogfireConfigurationError("logfire config failed")
    assert lf_err.error_code == "LOGFIRE_CONFIG_ERROR"
    assert lf_err.exit_code == 1

    assert issubclass(EmbeddingsError, DevOpsCLIError)
    assert issubclass(EmbeddingsError, RuntimeError)

    from devops_cli.exceptions.sandbox import (
        SandboxError,
        SandboxNotFoundError,
        SandboxPortAllocationError,
        SandboxValidationError,
    )

    assert issubclass(SandboxError, DevOpsCLIError)
    assert issubclass(SandboxValidationError, SandboxError)
    assert issubclass(SandboxPortAllocationError, SandboxError)
    assert issubclass(SandboxNotFoundError, SandboxError)

    sb_err = SandboxError("sandbox failed")
    assert sb_err.error_code == "SANDBOX_ERROR"
    assert sb_err.exit_code == 1

    sb_val_err = SandboxValidationError("invalid mount path")
    assert sb_val_err.error_code == "SANDBOX_VALIDATION_ERROR"

    sb_port_err = SandboxPortAllocationError("port exhausted")
    assert sb_port_err.error_code == "SANDBOX_PORT_ALLOCATION_ERROR"

    sb_nf_err = SandboxNotFoundError("sandbox missing")
    assert sb_nf_err.error_code == "SANDBOX_NOT_FOUND_ERROR"


def test_test_model_pytest_collection_disabled() -> None:
    """Ensure TestModel in testing.py disables Pytest collection to avoid PytestCollectionWarning."""
    from devops_cli.ai.agents.testing import TestModel

    assert getattr(TestModel, "__test__", None) is False


def test_no_excessive_nesting_in_src() -> None:
    """Assert nesting depth <= 5 across all of src/devops_cli."""
    from devops_cli.security.complexity import run_complexity_scan

    src_dir = Path("src/devops_cli")
    assert src_dir.exists(), f"Directory {src_dir} does not exist"
    findings = run_complexity_scan(src_dir, max_complexity=100, max_nesting_depth=5)
    nesting_findings = [f for f in findings if "Excessive Nesting Depth" in f.title]
    assert not nesting_findings, (
        f"Excessive nesting depth found in src/devops_cli: "
        f"{[f'{f.title} at {f.location}' for f in nesting_findings]}"
    )


def test_filesystem_get_tools_complexity() -> None:
    """Ensure FileSystem.get_tools maintains cyclomatic complexity <= 10."""
    from devops_cli.security.complexity import run_complexity_scan

    mod = Path("src/devops_cli/ai/harness/filesystem.py")
    findings = run_complexity_scan(mod, max_complexity=10, max_nesting_depth=5)
    tools_findings = [f for f in findings if "get_tools" in f.title]
    assert not tools_findings, f"FileSystem.get_tools exceeded complexity limit: {tools_findings}"


def test_no_bare_generic_exceptions_in_refactored_modules() -> None:
    """Ensure refactored domain modules do not raise bare ValueError, RuntimeError, or TypeError."""
    import ast

    prohibited_exceptions = {"ValueError", "RuntimeError", "TypeError"}

    modules_to_check = [
        Path("src/devops_cli/docker/sandbox.py"),
        Path("src/devops_cli/k8s/chaos_runner.py"),
        Path("src/devops_cli/commands/k8s/cluster_context.py"),
        Path("src/devops_cli/commands/vault.py"),
        Path("src/devops_cli/security/vault_broker.py"),
        Path("src/devops_cli/ai/model_bundler.py"),
        Path("src/devops_cli/ai/durable.py"),
        Path("src/devops_cli/ai/harness/skills.py"),
        Path("src/devops_cli/ai/harness/workflow.py"),
        Path("src/devops_cli/ai/harness/planning.py"),
        Path("src/devops_cli/ai/harness/shell.py"),
        Path("src/devops_cli/ai/harness/memory.py"),
        Path("src/devops_cli/ai/harness/os_access.py"),
        Path("src/devops_cli/ai/harness/compaction.py"),
        Path("src/devops_cli/ai/harness/slots.py"),
    ]

    violations: list[str] = []

    for mod_path in modules_to_check:
        assert mod_path.exists(), f"Path {mod_path} does not exist"
        tree = ast.parse(mod_path.read_text(encoding="utf-8"), filename=str(mod_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and node.exc is not None:
                exc_name = None
                if isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
                    exc_name = node.exc.func.id
                elif isinstance(node.exc, ast.Name):
                    exc_name = node.exc.id

                if exc_name in prohibited_exceptions:
                    violations.append(f"{mod_path}:{node.lineno} raises bare {exc_name}")

    assert not violations, "Prohibited generic exceptions raised in domain modules:\n" + "\n".join(
        violations
    )


def _resolve_import_edge(
    sub: ast.Import,
    mod: str,
    module_files: dict[str, Path],
    graph: dict[str, set[str]],
) -> None:
    for alias in sub.names:
        name = alias.name
        while name and name not in module_files and "." in name:
            name = name.rsplit(".", 1)[0]
        if name in module_files and name != mod:
            graph[mod].add(name)


def _resolve_import_from_edge(
    sub: ast.ImportFrom,
    mod: str,
    pkg_parts: list[str],
    module_files: dict[str, Path],
    graph: dict[str, set[str]],
) -> None:
    target = None
    if sub.level > 0:
        level = sub.level - 1
        base = pkg_parts[: len(pkg_parts) - level] if level <= len(pkg_parts) else []
        parts = base + (sub.module.split(".") if sub.module else [])
        target = ".".join(parts)
    elif sub.module:
        target = sub.module

    if not target:
        return

    base_target = target
    while base_target and base_target not in module_files and "." in base_target:
        base_target = base_target.rsplit(".", 1)[0]
    if base_target in module_files and base_target != mod:
        graph[mod].add(base_target)

    for alias in sub.names:
        child_mod = f"{target}.{alias.name}"
        if child_mod in module_files and child_mod != mod:
            graph[mod].add(child_mod)


def test_no_circular_imports_in_decoupled_subsystems() -> None:
    """Ensure decoupled subsystems (k8s commands, output, ai.review, config) have zero circular imports."""
    from collections import defaultdict

    subsystems = [
        Path("src/devops_cli/commands/k8s"),
        Path("src/devops_cli/output"),
        Path("src/devops_cli/ai/review"),
        Path("src/devops_cli/config"),
    ]

    for root in subsystems:
        assert root.is_dir(), f"Directory {root} does not exist"
        graph: dict[str, set[str]] = defaultdict(set)
        module_files: dict[str, Path] = {}

        for py_file in root.rglob("*.py"):
            rel = py_file.relative_to(Path("src"))
            parts = list(rel.with_suffix("").parts)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            mod = ".".join(parts)
            module_files[mod] = py_file

        for mod, py_file in module_files.items():
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            rel = py_file.relative_to(Path("src"))
            pkg_parts = list(rel.parent.parts)
            for node in tree.body:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Import):
                        _resolve_import_edge(sub, mod, module_files, graph)
                    elif isinstance(sub, ast.ImportFrom):
                        _resolve_import_from_edge(sub, mod, pkg_parts, module_files, graph)

        # Tarjan's SCC
        index = 0
        indices: dict[str, int] = {}
        lowlinks: dict[str, int] = {}
        on_stack: set[str] = set()
        stack: list[str] = []
        cycles: list[list[str]] = []

        def strongconnect(v: str) -> None:
            nonlocal index
            indices[v] = index
            lowlinks[v] = index
            index += 1
            stack.append(v)
            on_stack.add(v)

            for w in graph.get(v, []):
                if w not in indices:
                    strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif w in on_stack:
                    lowlinks[v] = min(lowlinks[v], indices[w])

            if lowlinks[v] == indices[v]:
                scc: list[str] = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == v:
                        break
                if len(scc) > 1:
                    cycles.append(scc)

        for node in list(module_files.keys()):
            if node not in indices:
                strongconnect(node)

        assert not cycles, f"Import cycles detected in {root}: {cycles}"
