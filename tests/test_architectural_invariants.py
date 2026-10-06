"""Test-first specification for architectural and stylistic invariants in devops-cli."""

from __future__ import annotations

import ast
import re
import tomllib
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pathspec
import pytest

from devops_cli.config.constants import (
    CONST_BLIND_EXCEPTION_TYPES,
    CONST_C901_SUPPRESSION,
    CONST_COMPLEXITY_CAP_ROOTS,
    CONST_COMPLEXITY_LINT_RULES,
    CONST_GITIGNORE_FILENAME,
    CONST_GITIGNORE_PATTERN_STYLE,
    CONST_RUFF_C901_SUPPRESSION_COMMENT,
    CONST_RUFF_CONFIG_FILE_NAMES,
    CONST_RUFF_EXCLUDE,
    CONST_RUFF_FILE_EXEMPTION,
    CONST_RUFF_IGNORE_FILE_NAMES,
    CONST_RUFF_LINT_KEYS,
    CONST_RUFF_MCCABE_KEYS,
    CONST_RUFF_PER_FILE_IGNORE_KEYS,
    CONST_RUFF_SOURCE_SUFFIXES,
    CONST_RUFF_TOP_LEVEL_KEYS,
    CONST_SUPPRESSION_LINT_RULES,
    CONST_TEST_ASSERTION_LINT_RULES,
)
from devops_cli.config.defaults import DEFAULT_C901_SUPPRESSION_CEILING, DEFAULT_MAX_COMPLEXITY
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


def test_no_module_runs_python_in_process() -> None:
    """Name every source module that calls the `exec` or `eval` builtin; there must be none.

    Code run by `exec` in this process is not contained by an AST check or a trimmed
    `__builtins__`: a script handed `typing` reaches `os` through `typing.sys.modules`, and one
    handed `asyncio` starts processes. The two harness capabilities that ran model-written
    scripts this way were deleted rather than patched (#947). Model code that has to run
    belongs in the host sandbox (bwrap) instead.
    """
    src = Path(__file__).resolve().parents[1] / "src" / "devops_cli"
    texts = {path: path.read_text(encoding="utf-8") for path in src.rglob("*.py")}
    callers = sorted(
        {
            path.relative_to(src).as_posix()
            for path, text in texts.items()
            if "exec(" in text or "eval(" in text
            for node in ast.walk(ast.parse(text, filename=str(path)))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("exec", "eval")
        }
    )

    assert tuple(callers) == ()


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


def _record_import_edges(
    mod: str,
    py_file: Path,
    module_files: dict[str, Path],
    graph: dict[str, set[str]],
) -> None:
    """Add one module's import edges to the dependency graph.

    Extracted from the caller so the walk does not sit six blocks deep. AGENTS.md caps
    nesting at 5, and the commit-time sentinel added in #443 enforces it across every
    staged Python file -- including this one, which predated the gate.
    """
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    pkg_parts = list(py_file.relative_to(Path("src")).parent.parts)
    for node in tree.body:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Import):
                _resolve_import_edge(sub, mod, module_files, graph)
            elif isinstance(sub, ast.ImportFrom):
                _resolve_import_from_edge(sub, mod, pkg_parts, module_files, graph)


@dataclass
class _TarjanState:
    graph: dict[str, set[str]]
    index: int = 0
    indices: dict[str, int] = field(default_factory=dict)
    lowlinks: dict[str, int] = field(default_factory=dict)
    on_stack: set[str] = field(default_factory=set)
    stack: list[str] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)


def _strongconnect(state: _TarjanState, v: str) -> None:
    state.indices[v] = state.index
    state.lowlinks[v] = state.index
    state.index += 1
    state.stack.append(v)
    state.on_stack.add(v)

    for w in state.graph.get(v, ()):
        if w not in state.indices:
            _strongconnect(state, w)
            state.lowlinks[v] = min(state.lowlinks[v], state.lowlinks[w])
        elif w in state.on_stack:
            state.lowlinks[v] = min(state.lowlinks[v], state.indices[w])

    if state.lowlinks[v] == state.indices[v]:
        scc: list[str] = []
        while True:
            w = state.stack.pop()
            state.on_stack.remove(w)
            scc.append(w)
            if w == v:
                break
        if len(scc) > 1:
            state.cycles.append(scc)


def _import_cycles(root: Path) -> list[list[str]]:
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
        _record_import_edges(mod, py_file, module_files, graph)

    state = _TarjanState(graph=graph)
    for node in module_files:
        if node not in state.indices:
            _strongconnect(state, node)
    return state.cycles


def test_no_circular_imports_in_decoupled_subsystems() -> None:
    """Ensure decoupled subsystems (k8s commands, output, ai.review, config) have zero circular imports."""
    subsystems = [
        Path("src/devops_cli/commands/k8s"),
        Path("src/devops_cli/output"),
        Path("src/devops_cli/ai/review"),
        Path("src/devops_cli/config"),
    ]
    for root in subsystems:
        cycles = _import_cycles(root)
        assert not cycles, f"Import cycles detected in {root}: {cycles}"


def test_task_md_is_decommissioned() -> None:
    """Ensure the monolithic docs/agent/task.md index is decommissioned to eliminate merge conflicts."""
    monolithic_index = Path("docs/agent/task.md")
    assert not monolithic_index.exists(), (
        "docs/agent/task.md has been decommissioned in favor of modular per-task files "
        "in docs/agent/tasks/ and native GitHub Projects v2 boards. Do not re-introduce it."
    )


def test_no_stray_scripts_in_project_root() -> None:
    """Ensure no ad-hoc scratch scripts (*.py, *.sh) or stray scripts directories exist in the project root."""
    root = Path(__file__).resolve().parents[1]
    stray_files = sorted(
        f.name for f in root.iterdir() if f.is_file() and f.suffix in {".py", ".sh"}
    )
    assert (stray_files, (root / "scripts").exists()) == (
        [],
        False,
    )


def _dockerfile_build_context_sources(dockerfile: Path) -> set[str]:
    """Extract the repository paths a Dockerfile copies out of its build context.

    Only local sources count: `COPY --from=<image>` pulls from another image, not from
    this repository, so it cannot make the published image stale.
    """
    sources: set[str] = set()
    for raw_line in dockerfile.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.upper().startswith("COPY "):
            continue
        tokens = line.split()[1:]
        if any(token.startswith("--from=") for token in tokens):
            continue
        # The final token is the destination; everything before it is a source.
        sources.update(token.rstrip("/") for token in tokens[:-1] if not token.startswith("--"))
    return sources


def _ci_image_content_paths(workflow: Path, job_name: str = "devcontainer") -> set[str]:
    """Read the IMAGE_CONTENT_PATHS list the CI workflow watches for image changes."""
    import yaml

    document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    for step in document["jobs"][job_name]["steps"]:
        declared = (step.get("env") or {}).get("IMAGE_CONTENT_PATHS")
        if declared:
            return {line.strip() for line in declared.splitlines() if line.strip()}
    raise AssertionError(f"CI {job_name} job declares no IMAGE_CONTENT_PATHS")


@pytest.mark.parametrize(
    ("job_name", "dockerfile_rel"),
    [
        ("devcontainer", ".devcontainer/Dockerfile"),
        ("service-image", "Dockerfile"),
    ],
)
def test_image_path_filter_covers_dockerfile_sources(job_name: str, dockerfile_rel: str) -> None:
    """The CI image-change filter must cover every path baked into the container image.

    The published container image packages devops-cli itself. If a new `COPY` starts
    pulling a path the workflow's change detection does not watch, CI would skip the
    rebuild and publish a stale image while still reporting success.
    """
    repo_root = Path(__file__).resolve().parents[1]
    watched = _ci_image_content_paths(
        repo_root / ".github" / "workflows" / "ci.yml", job_name=job_name
    )
    sources = _dockerfile_build_context_sources(repo_root / dockerfile_rel)

    def _covered(path: str) -> bool:
        return any(path == w or path.startswith(f"{w}/") for w in watched)

    uncovered = sorted(source for source in sources if not _covered(source))
    assert not uncovered, (
        f"The Dockerfile copies {uncovered} into the image, but the CI 'Detect Image "
        f"Content Changes' filter for {job_name} watches only {sorted(watched)}. Changes to those paths "
        f"would skip the rebuild and publish a stale image."
    )

    # The build definition itself must be watched, not just the copied build context.
    assert _covered(dockerfile_rel), (
        f"The CI image-change filter must watch {dockerfile_rel}; a change to the "
        "build recipe alters the image even when no copied source file changes."
    )

    # The workflow fixes the image name, tags, cache source, and builder action version,
    # so a change to it alters what gets published even with identical build inputs.
    assert _covered(".github/workflows/ci.yml"), (
        "The CI image-change filter must watch the workflow that performs the build; "
        "changing the image name, tag, cache source, or builder version alters the "
        "published image without touching any build input."
    )

    # Each filter must also watch .dockerignore
    assert _covered(".dockerignore"), (
        f"The CI image-change filter for {job_name} must watch .dockerignore."
    )


def _find_workflow_runner_mutations(workflow_path: Path, pattern: re.Pattern[str]) -> list[str]:
    """Find commands in workflow run steps that mutate the runner environment (#832)."""
    import yaml

    data = yaml.safe_load(workflow_path.read_text(encoding="utf-8")) or {}
    jobs = data.get("jobs", {}) if isinstance(data, dict) else {}
    mutations: list[str] = []
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps", []):
            run_cmd = step.get("run") if isinstance(step, dict) else None
            if run_cmd and (matches := pattern.findall(str(run_cmd))):
                mutations.append(f"{workflow_path.name}:{job_id}:{sorted(set(matches))}")
    return mutations


def test_workflows_never_mutate_runner_and_devcontainer_installs_bubblewrap() -> None:
    """CI workflows must never mutate runner environment, and bubblewrap is installed in devcontainer (#832)."""
    repo_root = Path(__file__).resolve().parents[1]
    pattern = re.compile(r"\b(apt-get|sudo|sysctl)\b")
    mutations = [
        m
        for path in sorted((repo_root / ".github" / "workflows").glob("*.yml"))
        for m in _find_workflow_runner_mutations(path, pattern)
    ]
    dockerfile_text = (repo_root / ".devcontainer" / "Dockerfile").read_text(encoding="utf-8")
    installs_bwrap = bool(re.search(r"\bbubblewrap\b", dockerfile_text))

    assert (mutations, installs_bwrap) == ([], True)


def _find_actions_write_permissions(workflow_path: Path) -> set[tuple[str, str]]:
    """Find (workflow_file, job_id) pairs with actions: write permission."""
    import yaml

    data = yaml.safe_load(workflow_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return set()
    results: set[tuple[str, str]] = set()
    top_perms = data.get("permissions")
    top_actions_write = isinstance(top_perms, dict) and top_perms.get("actions") == "write"
    jobs = data.get("jobs", {})
    if isinstance(jobs, dict):
        for job_id, job in jobs.items():
            job_perms = job.get("permissions") if isinstance(job, dict) else None
            job_actions_write = isinstance(job_perms, dict) and job_perms.get("actions") == "write"
            if top_actions_write or job_actions_write:
                results.add((workflow_path.name, str(job_id)))
    elif top_actions_write:
        results.add((workflow_path.name, "*"))
    return results


# No workflow may hold actions: write permission, and ci.yml must admit workflow_dispatch (#984, #1217).
ACTIONS_WRITE_ALLOWLIST: frozenset[tuple[str, str]] = frozenset()


def test_only_update_prs_holds_actions_write_permission_and_ci_dispatches() -> None:
    """No workflow may hold actions: write, and ci.yml must admit workflow_dispatch (#984, #1217)."""
    import yaml

    repo_root = Path(__file__).resolve().parents[1]
    workflows_dir = repo_root / ".github" / "workflows"

    actions_write_jobs = {
        perm
        for wf in sorted(workflows_dir.glob("*.yml"))
        for perm in _find_actions_write_permissions(wf)
    }

    ci_path = workflows_dir / "ci.yml"
    ci_data = yaml.safe_load(ci_path.read_text(encoding="utf-8")) or {}
    assert isinstance(ci_data, dict), "ci.yml must parse as a mapping"
    on_triggers = ci_data.get("on") or ci_data.get(True) or {}
    ci_jobs = ci_data.get("jobs", {})

    job_ifs = {
        str(j.get("name")): j.get("if")
        for j in ci_jobs.values()
        if isinstance(j, dict) and j.get("name") in ("Static Analysis", "Tests & Coverage")
    }

    assert (
        actions_write_jobs,
        "workflow_dispatch" in on_triggers,
        job_ifs.get("Static Analysis") in (None, "github.event_name != 'schedule'"),
        job_ifs.get("Tests & Coverage") in (None, "github.event_name != 'schedule'"),
    ) == (
        ACTIONS_WRITE_ALLOWLIST,
        True,
        True,
        True,
    )


def _check_copy_from_ref(tokens: list[str], stage_names: set[str]) -> bool:
    """Return True if any --from= reference in COPY is an unpinned non-stage image."""
    for tok in tokens[1:]:
        if tok.startswith("--from="):
            ref = tok.split("=", 1)[1]
            if ref not in stage_names and "@sha256:" not in ref:
                return True
    return False


def _unpinned_dockerfile_images(dockerfile: Path) -> list[str]:
    stage_names: set[str] = set()
    unpinned: list[str] = []
    for raw_line in dockerfile.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        tokens = line.split()
        cmd = tokens[0].upper()
        if cmd == "FROM":
            if len(tokens) >= 4 and tokens[2].upper() == "AS":
                stage_names.add(tokens[3])
            if "@sha256:" not in tokens[1]:
                unpinned.append(line)
        elif cmd == "COPY" and _check_copy_from_ref(tokens, stage_names):
            unpinned.append(line)
    return unpinned


def test_service_dockerfile_base_images_pinned_by_digest() -> None:
    """Every FROM and COPY --from= image in Dockerfile carries @sha256: (stage names exempt)."""
    repo_root = Path(__file__).resolve().parents[1]
    unpinned = _unpinned_dockerfile_images(repo_root / "Dockerfile")
    assert unpinned == []


def _expected_exception_name(call: ast.Call) -> str | None:
    """Name the exception type a `pytest.raises` call expects, when it is a plain name."""
    is_raises = isinstance(call.func, ast.Attribute) and call.func.attr == "raises"
    expected = call.args[0] if (is_raises and call.args) else None
    return expected.id if isinstance(expected, ast.Name) else None


def _ruff_enforces(rule: str, select: Sequence[str], ignore: Sequence[str]) -> bool:
    """Report whether Ruff would actually run one rule under a given configuration.

    Ruff selects and ignores by *prefix*, resolving the longest match, so comparing codes
    as literal strings is wrong in both directions. With `ignore = ["B"]` Ruff suppresses
    B017 entirely while a set-difference still reports it enforced -- a test that certifies
    the very rule it is meant to pin. With `select = ["B"]`, the family-level spelling this
    release schedules, the set difference reports B017 missing although Ruff runs it.

    `ALL` selects everything, so it is the least specific match: any explicit ignore beats
    it. A tie goes to ignore, matching Ruff's own resolution.
    """

    def specificity(prefixes: Sequence[str]) -> int | None:
        matches = [len(p) for p in prefixes if p == "ALL" or rule.startswith(p)]
        widened = [
            0 if p == "ALL" else len(p) for p in prefixes if p == "ALL" or rule.startswith(p)
        ]
        return max(widened) if matches else None

    selected = specificity(select)
    if selected is None:
        return False
    ignored = specificity(ignore)
    return ignored is None or ignored < selected


def _blind_exception_assertions(tests_dir: Path) -> list[str]:
    """Report every `file:line` in the suite that expects a root exception type."""
    sites: list[str] = []
    for path in sorted(tests_dir.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        sites.extend(
            f"{path.name}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _expected_exception_name(node) in CONST_BLIND_EXCEPTION_TYPES
        )
    return sites


def test_no_test_certifies_a_failure_without_checking_it() -> None:
    """A test that expects a failure must say which failure, and Ruff must keep it saying so.

    `pytest.raises(Exception)` is satisfied by a `TypeError` an unrelated refactor
    introduced, so it keeps reporting green through the very regression it exists to catch.
    An unescaped `match=` pattern is the same defect in miniature: `"missing 'metadata.name'"`
    accepts any character where the dots are, so the assertion is weaker than it reads.
    Neither is visible in review -- both read as correct tests -- so the Ruff rules that
    catch them are pinned here beside the scan, and dropping either rule fails this test.
    """
    repo_root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    lint = config["tool"]["ruff"]["lint"]
    unenforced = sorted(
        rule
        for rule in CONST_TEST_ASSERTION_LINT_RULES
        if not _ruff_enforces(rule, lint["select"], lint.get("ignore", []))
    )

    assert (_blind_exception_assertions(repo_root / "tests"), unenforced) == ([], [])


def test_rule_enforcement_matches_ruffs_prefix_resolution() -> None:
    """Ruff selects and ignores by prefix, resolving the longest match.

    The first version of the invariant above compared codes as literal strings, so
    `select = ["B"]` — the family-level spelling the adjacent roadmap item schedules for
    this release — made it report B017 unenforced while Ruff runs it.

    Each case here was checked against Ruff itself rather than reasoned about, which
    matters: an adversarial review of this change also claimed `ignore = ["B"]` suppresses
    an explicitly selected B017. Ruff still reports it, because the longer prefix wins.
    """
    cases = [
        _ruff_enforces("B017", ["E", "F", "B017"], ["E501"]),
        _ruff_enforces("B017", ["E", "F", "B017"], ["B"]),
        _ruff_enforces("B017", ["E", "F", "B"], []),
        _ruff_enforces("B017", ["E", "F"], []),
    ]
    assert cases == [True, True, True, False]


def test_a_broad_ignore_defeats_a_broad_select() -> None:
    """`ALL` is the least specific selection, so any explicit ignore outranks it."""
    assert (
        _ruff_enforces("RUF043", ["ALL"], ["RUF"]),
        _ruff_enforces("RUF043", ["ALL"], []),
    ) == (False, True)


def test_suppression_lint_rules_enforced() -> None:
    """Rules that audit suppressions (PGH003, RUF100) must remain enforced by Ruff configuration."""
    repo_root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    lint = config["tool"]["ruff"]["lint"]
    unenforced = sorted(
        rule
        for rule in CONST_SUPPRESSION_LINT_RULES
        if not _ruff_enforces(rule, lint["select"], lint.get("ignore", []))
    )
    assert unenforced == []


def test_mypy_ignore_without_code_enabled() -> None:
    """Mypy configuration must enforce ignore-without-code to reject blanket type ignores."""
    repo_root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    enabled = config.get("tool", {}).get("mypy", {}).get("enable_error_code", [])
    assert "ignore-without-code" in enabled


def _unlisted_keys(table: str, keys: Iterable[str], allowed: frozenset[str]) -> list[str]:
    """Name each key of one table that its allowlist does not admit."""
    return [f"[{table}] {key}: outside the allowlist" for key in sorted(set(keys) - allowed)]


def _names_rule(rule: str, code: str) -> bool:
    """Report whether one selector names a rule, by Ruff's prefix matching."""
    return code == "ALL" or rule.startswith(code)


def _lint_escapes(lint: Mapping[str, Any]) -> list[str]:
    """Report an unenforced cap rule, a per-file waiver of one, or a moved complexity limit.

    A cap rule counts as enforced only when `select` names it by its own code. Ruff redirects
    some prefixes before it weighs them (`C9` reads as `C90`), so `C90` selected with `C9`
    ignored turns C901 off while `_ruff_enforces`, ranking by length, calls it on. Only the same
    code can tie an exact code, and `_ruff_enforces` gives that tie to ignore, as Ruff does.
    """
    select = [*lint.get("select", []), *lint.get("extend-select", [])]
    ignore = [*lint.get("ignore", []), *lint.get("extend-ignore", [])]
    rules = sorted(CONST_COMPLEXITY_LINT_RULES)
    unenforced = [
        f"{rule}: not enforced"
        for rule in rules
        if rule not in select or not _ruff_enforces(rule, select, ignore)
    ]
    waived = [
        f"[tool.ruff.lint.{table}] {pattern}: waives {rule}"
        for table in CONST_RUFF_PER_FILE_IGNORE_KEYS
        for pattern, codes in lint.get(table, {}).items()
        for rule in rules
        if any(_names_rule(rule, code) for code in codes)
    ]
    mccabe = lint.get("mccabe", {})
    cap = mccabe.get("max-complexity")
    raised = f"[tool.ruff.lint.mccabe] max-complexity: {cap}, not {DEFAULT_MAX_COMPLEXITY}"
    return [
        *_unlisted_keys("tool.ruff.lint", lint, CONST_RUFF_LINT_KEYS),
        *unenforced,
        *waived,
        *_unlisted_keys("tool.ruff.lint.mccabe", mccabe, CONST_RUFF_MCCABE_KEYS),
        *([] if cap == DEFAULT_MAX_COMPLEXITY else [raised]),
    ]


def _covered_files(project: Path) -> list[Path]:
    """List every file under the roots the complexity cap covers."""
    return sorted(
        path
        for root in CONST_COMPLEXITY_CAP_ROOTS
        for path in (project / root).rglob("*")
        if path.is_file()
    )


_SOURCE_ESCAPES = (
    (CONST_RUFF_FILE_EXEMPTION, "file-level noqa"),
    (CONST_RUFF_C901_SUPPRESSION_COMMENT, "a ruff suppression comment naming C901"),
)


def _source_escapes(project: Path, sources: Iterable[Path]) -> list[str]:
    """Report each source that exempts itself, or hides C901 behind a comment no marker counts."""
    texts = {
        path.relative_to(project).as_posix(): path.read_text(encoding="utf-8") for path in sources
    }
    return [
        f"{name}: {escape}"
        for name, text in texts.items()
        for pattern, escape in _SOURCE_ESCAPES
        if pattern.search(text)
    ]


def _ignore_file_escapes(
    project: Path, covered: Sequence[Path], sources: Sequence[Path]
) -> list[str]:
    """Report an ignore file that drops a covered source from Ruff's walk of the project.

    The root `.gitignore` is the project's own and stays, so only a source it matches is an
    escape; an ignore file under a covered root, or a root `.ignore`, is one by being there.
    """
    gitignore = project / CONST_GITIGNORE_FILENAME
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.is_file() else []
    listed = pathspec.PathSpec.from_lines(CONST_GITIGNORE_PATTERN_STYLE, lines)
    nested = [
        f"{path.relative_to(project).as_posix()}: an ignore file under a covered root"
        for path in covered
        if path.name in CONST_RUFF_IGNORE_FILE_NAMES
    ]
    beside = [
        f"{name}: an ignore file beside pyproject.toml"
        for name in sorted(CONST_RUFF_IGNORE_FILE_NAMES - {CONST_GITIGNORE_FILENAME})
        if (project / name).exists()
    ]
    names = [path.relative_to(project).as_posix() for path in sources]
    matched = [
        f"{name}: matched by {CONST_GITIGNORE_FILENAME}"
        for name in names
        if listed.match_file(name)
    ]
    return [*nested, *beside, *matched]


def _tree_escapes(project: Path) -> list[str]:
    """Report a source that suppresses C901 without a marker, or a file that hides one from Ruff."""
    covered = _covered_files(project)
    sources = [path for path in covered if path.suffix in CONST_RUFF_SOURCE_SUFFIXES]
    nested = [
        f"{path.relative_to(project).as_posix()}: a Ruff config under a covered root"
        for path in covered
        if path.name in CONST_RUFF_CONFIG_FILE_NAMES
    ]
    outranking = [
        f"{name}: outranks pyproject.toml"
        for name in sorted(CONST_RUFF_CONFIG_FILE_NAMES - {"pyproject.toml"})
        if (project / name).exists()
    ]
    return [
        *_source_escapes(project, sources),
        *nested,
        *outranking,
        *_ignore_file_escapes(project, covered, sources),
    ]


def _complexity_cap_escapes(pyproject: Mapping[str, Any], project: Path) -> list[str]:
    """Report every way a committed file lets a function past the C901 cap without a marker.

    Keys are checked against allowlists rather than a list of known escapes, so a setting
    Ruff adds later is reported until a reviewed change admits it. `per-file-ignores` stays
    allowed for other rules; an entry covering C901, RUF100 or PGH004 is an escape. Ignore
    files outside the checkout (`.git/info/exclude`, a global gitignore, one above the
    project) differ per machine and never reach the clean checkout GitHub CI lints.
    """
    ruff = pyproject.get("tool", {}).get("ruff", {})
    exclude, expected = ruff.get("exclude"), [*CONST_RUFF_EXCLUDE]
    widened = f"[tool.ruff] exclude: {exclude}, not {expected}"
    return [
        *_unlisted_keys("tool.ruff", ruff, CONST_RUFF_TOP_LEVEL_KEYS),
        *([] if exclude == expected else [widened]),
        *_lint_escapes(ruff.get("lint", {})),
        *_tree_escapes(project),
    ]


def _c901_suppressions(project: Path) -> dict[str, int]:
    """Count the noqa comments naming C901 in each covered file, keyed by its project path.

    A regex over the text, not `tokenize`: tokenizing the tree took 1.2-8.0 s (#586).
    """
    counts = {
        path.relative_to(project).as_posix(): len(
            CONST_C901_SUPPRESSION.findall(path.read_text(encoding="utf-8"))
        )
        for path in _covered_files(project)
        if path.suffix in CONST_RUFF_SOURCE_SUFFIXES
    }
    return {name: count for name, count in counts.items() if count}


def _c901_suppressions_over(project: Path, ceiling: int) -> tuple[int, list[str]]:
    """Return how far the C901 suppressions exceed a ceiling, and the files that carry them."""
    counts = _c901_suppressions(project)
    excess = sum(counts.values()) - ceiling
    return (excess, sorted(counts)) if excess > 0 else (0, [])


_DROP = object()
# Built here so this file's own text holds no file-level exemption, no C901 marker and no
# Ruff suppression comment naming C901. Ruff honours each spelling below (checked on 0.16.8).
_RUFF_FILE_NOQA = "# " + "ruff" + ": noqa"
_FLAKE8_FILE_NOQA = "# " + "flake8" + ": noqa"
_C901_MARKER = "# " + "noqa: " + "C901"
_RUFF_COMMENT = "# " + "ruff" + ": "
_FORM_FEED, _NO_BREAK_SPACE, _EM_SPACE = "\x0c", "\xa0", "\u2003"


def _complying_pyproject() -> dict[str, Any]:
    """Build, as a fresh dict, a pyproject.toml the complexity cap's meta-test accepts."""
    lint = {
        "select": ["E", *sorted(CONST_COMPLEXITY_LINT_RULES)],
        "ignore": ["E501"],
        "mccabe": {"max-complexity": DEFAULT_MAX_COMPLEXITY},
    }
    ruff = {"target-version": "py314", "line-length": 100, "exclude": [*CONST_RUFF_EXCLUDE]}
    return {"tool": {"ruff": {**ruff, "lint": lint}}}


def _edit(table: dict[str, Any], path: Sequence[str], value: object) -> None:
    """Set, or with `_DROP` delete, the key a path names inside nested tables."""
    *parents, key = path
    for name in parents:
        table = table[name]
    if value is _DROP:
        del table[key]
    else:
        table[key] = value


_COMPLEXITY_CAP_ESCAPES = [
    pytest.param((), None, {}, [], id="complying"),
    pytest.param(
        ("per-file-ignores",),
        {"pkg/*": ["C901"]},
        {},
        ["[tool.ruff] per-file-ignores: outside the allowlist"],
        id="top-level-per-file-ignores",
    ),
    pytest.param(
        ("extend-ignore",),
        ["C901"],
        {},
        ["[tool.ruff] extend-ignore: outside the allowlist"],
        id="top-level-extend-ignore",
    ),
    pytest.param(
        ("include",),
        ["src/devops_cli/cli.py"],
        {},
        ["[tool.ruff] include: outside the allowlist"],
        id="include",
    ),
    pytest.param(
        ("extend",),
        "../ruff.toml",
        {},
        ["[tool.ruff] extend: outside the allowlist"],
        id="extend",
    ),
    pytest.param(
        ("extend-exclude",),
        ["src"],
        {},
        ["[tool.ruff] extend-exclude: outside the allowlist"],
        id="extend-exclude",
    ),
    pytest.param(
        ("lint", "exclude"),
        ["src/**"],
        {},
        ["[tool.ruff.lint] exclude: outside the allowlist"],
        id="lint-exclude",
    ),
    pytest.param(
        ("exclude",),
        ["repos", "src"],
        {},
        ["[tool.ruff] exclude: ['repos', 'src'], not ['repos']"],
        id="exclude",
    ),
    pytest.param(
        ("lint", "select"),
        ["E", "PGH004", "RUF100"],
        {},
        ["C901: not enforced"],
        id="c901-unselected",
    ),
    pytest.param(
        ("lint", "ignore"),
        ["E501", "C901"],
        {},
        ["C901: not enforced"],
        id="c901-ignored",
    ),
    pytest.param(
        ("lint", "extend-ignore"),
        ["RUF100"],
        {},
        ["RUF100: not enforced"],
        id="ruf100-extend-ignored",
    ),
    pytest.param(
        ("lint", "select"),
        ["E", "C901", "RUF100"],
        {},
        ["PGH004: not enforced"],
        id="pgh004-unselected",
    ),
    pytest.param(
        ("lint",),
        {
            "select": ["E", "C90", "PGH004", "RUF100"],
            "ignore": ["E501", "C9"],
            "mccabe": {"max-complexity": DEFAULT_MAX_COMPLEXITY},
        },
        {},
        ["C901: not enforced"],
        id="c901-selected-as-c90-and-ignored-as-c9",
    ),
    pytest.param(
        ("lint", "ignore"),
        ["E501", "C9"],
        {},
        [],
        id="c9-ignored-under-an-exact-c901",
    ),
    pytest.param(
        ("lint", "mccabe", "max-complexity"),
        11,
        {},
        ["[tool.ruff.lint.mccabe] max-complexity: 11, not 10"],
        id="max-complexity-raised",
    ),
    pytest.param(
        ("lint", "mccabe", "max-complexity"),
        _DROP,
        {},
        ["[tool.ruff.lint.mccabe] max-complexity: None, not 10"],
        id="max-complexity-missing",
    ),
    pytest.param(
        ("lint", "mccabe", "ignore-names"),
        ["main"],
        {},
        ["[tool.ruff.lint.mccabe] ignore-names: outside the allowlist"],
        id="mccabe-extra-key",
    ),
    pytest.param(
        ("lint", "per-file-ignores"),
        {"tests/*": ["C9"]},
        {},
        ["[tool.ruff.lint.per-file-ignores] tests/*: waives C901"],
        id="per-file-ignores",
    ),
    pytest.param(
        ("lint", "extend-per-file-ignores"),
        {"src/*": ["ALL"]},
        {},
        [
            "[tool.ruff.lint.extend-per-file-ignores] src/*: waives C901",
            "[tool.ruff.lint.extend-per-file-ignores] src/*: waives PGH004",
            "[tool.ruff.lint.extend-per-file-ignores] src/*: waives RUF100",
        ],
        id="extend-per-file-ignores",
    ),
    pytest.param(
        ("lint", "per-file-ignores"),
        {"src/*": ["PGH"]},
        {},
        ["[tool.ruff.lint.per-file-ignores] src/*: waives PGH004"],
        id="per-file-ignores-blanket-noqa",
    ),
    pytest.param(
        (),
        None,
        {"src/pkg/mod.py": f"{_RUFF_FILE_NOQA}\n"},
        ["src/pkg/mod.py: file-level noqa"],
        id="ruff-file-noqa",
    ),
    pytest.param(
        (),
        None,
        {"src/mod.py": f"{_RUFF_FILE_NOQA}: C901\n"},
        ["src/mod.py: file-level noqa"],
        id="ruff-file-noqa-naming-c901",
    ),
    pytest.param(
        (),
        None,
        {"tests/test_mod.py": f"{_FLAKE8_FILE_NOQA}\n"},
        ["tests/test_mod.py: file-level noqa"],
        id="flake8-file-noqa",
    ),
    pytest.param(
        (),
        None,
        {"src/mod.py": f"#{_FORM_FEED}{_RUFF_FILE_NOQA[2:]}: C901\n"},
        ["src/mod.py: file-level noqa"],
        id="ruff-file-noqa-after-a-form-feed",
    ),
    pytest.param(
        (),
        None,
        {"tests/test_mod.py": f"#{_NO_BREAK_SPACE}{_FLAKE8_FILE_NOQA[2:]}\n"},
        ["tests/test_mod.py: file-level noqa"],
        id="flake8-file-noqa-after-a-no-break-space",
    ),
    pytest.param(
        (),
        None,
        {"src/mod.py": f"def f(x):  {_RUFF_COMMENT}ignore[C901]\n    return x\n"},
        ["src/mod.py: a ruff suppression comment naming C901"],
        id="ruff-ignore-naming-c901",
    ),
    pytest.param(
        (),
        None,
        {
            "src/pkg/mod.py": f"{_RUFF_COMMENT}disable[C901]\n"
            "def f(x):\n    return x\n"
            f"{_RUFF_COMMENT}enable[C901]\n"
        },
        ["src/pkg/mod.py: a ruff suppression comment naming C901"],
        id="ruff-disable-enable-pair",
    ),
    pytest.param(
        (),
        None,
        {"tests/test_mod.py": "#" + "ruff:" + "disable[E501,C901]\ndef f(x):\n    return x\n"},
        ["tests/test_mod.py: a ruff suppression comment naming C901"],
        id="ruff-disable-unpaired-unspaced",
    ),
    pytest.param(
        (),
        None,
        {"src/mod.py": f"{_RUFF_COMMENT}file-ignore[C901]\n"},
        ["src/mod.py: a ruff suppression comment naming C901"],
        id="ruff-file-ignore",
    ),
    pytest.param(
        (),
        None,
        {"src/mod.py": f"#{_EM_SPACE}{_RUFF_COMMENT[2:]}{_EM_SPACE}disable[ C901 ]\n"},
        ["src/mod.py: a ruff suppression comment naming C901"],
        id="ruff-disable-after-em-spaces",
    ),
    pytest.param(
        (),
        None,
        {"src/pkg/.ignore": "mod.py\n", "src/pkg/mod.py": ""},
        ["src/pkg/.ignore: an ignore file under a covered root"],
        id="nested-ignore-file",
    ),
    pytest.param(
        (),
        None,
        {"tests/.gitignore": "test_mod.py\n", "tests/test_mod.py": ""},
        ["tests/.gitignore: an ignore file under a covered root"],
        id="nested-gitignore",
    ),
    pytest.param(
        (),
        None,
        {".ignore": "src/mod.py\n", "src/mod.py": ""},
        [".ignore: an ignore file beside pyproject.toml"],
        id="project-ignore-file",
    ),
    pytest.param(
        (),
        None,
        {
            ".gitignore": "__pycache__/\n*.py[cod]\nsrc/pkg/hidden.py\n",
            "src/pkg/hidden.py": "",
            "src/pkg/kept.py": "",
            "src/pkg/__pycache__/kept.cpython-314.pyc": "",
        },
        ["src/pkg/hidden.py: matched by .gitignore"],
        id="project-gitignore-listing-a-source",
    ),
    pytest.param(
        (),
        None,
        {"src/pkg/ruff.toml": ""},
        ["src/pkg/ruff.toml: a Ruff config under a covered root"],
        id="nested-ruff-toml",
    ),
    pytest.param(
        (),
        None,
        {"tests/.ruff.toml": ""},
        ["tests/.ruff.toml: a Ruff config under a covered root"],
        id="nested-dot-ruff-toml",
    ),
    pytest.param(
        (),
        None,
        {"src/pkg/pyproject.toml": ""},
        ["src/pkg/pyproject.toml: a Ruff config under a covered root"],
        id="nested-pyproject-toml",
    ),
    pytest.param(
        (),
        None,
        {"ruff.toml": ""},
        ["ruff.toml: outranks pyproject.toml"],
        id="project-ruff-toml",
    ),
]


@pytest.mark.parametrize(("path", "value", "files", "expected"), _COMPLEXITY_CAP_ESCAPES)
def test_every_complexity_cap_escape_is_reported(
    tmp_path: Path,
    path: Sequence[str],
    value: object,
    files: Mapping[str, str],
    expected: list[str],
) -> None:
    """Each way past the cap, in the configuration or in the tree, is reported by itself.

    Ruff 0.16 still honours the deprecated top-level `per-file-ignores` and `extend-ignore`,
    and `include`, `extend` and `lint.exclude` change which files or which settings apply,
    so the helper allows known keys rather than forbidding known escapes.
    """
    pyproject = _complying_pyproject()
    if path:
        _edit(pyproject["tool"]["ruff"], path, value)
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")

    assert _complexity_cap_escapes(pyproject, tmp_path) == expected


def test_the_complexity_cap_has_no_escape() -> None:
    """Ruff's C901 is the cap of 10 (#586), and only a counted marker takes a function past it.

    `_ruff_enforces` alone reads `select` and `ignore`; a raised `max-complexity`, a
    per-file waiver, a nested config, a file-level exemption, one of Ruff's own bracketed
    suppression comments or an ignore file would each pass it.
    """
    repo_root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    assert _complexity_cap_escapes(pyproject, repo_root) == []


def test_c901_suppressions_stay_under_the_ceiling() -> None:
    """The functions over the cap when Ruff began enforcing it may only become fewer.

    Each carries a C901 marker that RUF100 reports once the function is back under the cap.
    A new marker takes the count past `DEFAULT_C901_SUPPRESSION_CEILING` and fails here.
    """
    repo_root = Path(__file__).resolve().parents[1]
    excess, files = _c901_suppressions_over(repo_root, DEFAULT_C901_SUPPRESSION_CEILING)
    assert (excess, files) == (0, []), (
        f"{excess} more C901 marker(s) than DEFAULT_C901_SUPPRESSION_CEILING allows, "
        f"among these files: {files}. Decompose the function the new marker sits on until "
        "Ruff no longer reports it; do not raise the ceiling."
    )


def test_suppressions_over_the_ceiling_name_their_files(tmp_path: Path) -> None:
    """Both forms `--add-noqa` writes count, once per comment, and the excess names its file."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "over.py").write_text(
        f"def f(x):  {_C901_MARKER}\n    return x\n\n\n"
        f"def do_GET(x):  {_C901_MARKER}, N802\n    return x\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_clean.py").write_text("def g(x):\n    return x\n", "utf-8")

    assert (
        _c901_suppressions(tmp_path),
        _c901_suppressions_over(tmp_path, 1),
        _c901_suppressions_over(tmp_path, 2),
    ) == ({"src/over.py": 2}, (1, ["src/over.py"]), (0, []))


@pytest.mark.parametrize(
    "marker",
    [
        pytest.param(f"#{_FORM_FEED}{_C901_MARKER[2:]}", id="form-feed-after-the-hash"),
        pytest.param(f"#{_NO_BREAK_SPACE}{_C901_MARKER[2:]}", id="no-break-space-after-the-hash"),
        pytest.param(_C901_MARKER.replace(": ", f":{_EM_SPACE}"), id="em-space-after-the-colon"),
        pytest.param(_C901_MARKER.replace(": ", " : E501 "), id="spaced-colon-unseparated-codes"),
    ],
)
def test_every_marker_spelling_ruff_honours_is_counted(tmp_path: Path, marker: str) -> None:
    """Ruff reads any whitespace but a newline inside a noqa comment, so each spelling counts."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mod.py").write_text(f"def f(x):  {marker}\n    return x\n", "utf-8")

    assert _c901_suppressions(tmp_path) == {"src/mod.py": 1}


def test_manifests_by_stack_files_exist() -> None:
    """Every Kubernetes manifest declared in _MANIFESTS_BY_STACK must exist on disk."""
    from devops_cli.commands.k8s.stack_lifecycle import _MANIFESTS_BY_STACK

    missing_manifests = [
        f"{stack_name}:{path}"
        for stack_name, paths in _MANIFESTS_BY_STACK.items()
        for path in paths
        if not (path.exists() or (path.parent / f"{path.stem}.example{path.suffix}").exists())
    ]
    assert missing_manifests == []
