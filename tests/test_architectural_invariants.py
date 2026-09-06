"""Test-first specification for architectural and stylistic invariants in devops-cli."""

from __future__ import annotations

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
        HarnessExecutionError,
        HarnessValidationError,
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

    err = DockerSandboxError("test sandbox error")
    assert err.error_code == "DOCKER_SANDBOX_ERROR"
    assert err.exit_code == 1

    v_err = VaultKeyError("missing key")
    assert v_err.error_code == "VAULT_KEY_ERROR"

    k_err = KubernetesContextError("invalid context")
    assert k_err.error_code == "K8S_CONTEXT_ERROR"


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
    tools_findings = [
        f for f in findings if "FileSystem.get_tools" in f.title or "get_tools" in f.location
    ]
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
