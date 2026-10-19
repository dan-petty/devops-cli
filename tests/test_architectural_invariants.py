"""Test-first specification for architectural and stylistic invariants in devops-cli."""

from __future__ import annotations

import ast
import io
import re
import tokenize
import tomllib
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from graphlib import CycleError
from pathlib import Path
from typing import Any

import pathspec
import pytest

from devops_cli.config.constants import (
    CONST_AST_GREP_IGNORE_COMMENT_RE,
    CONST_AST_GREP_NET_RULE_ID_RE,
    CONST_BLIND_EXCEPTION_TYPES,
    CONST_C901_SUPPRESSION,
    CONST_COMPLEXITY_CAP_ROOTS,
    CONST_COMPLEXITY_LINT_RULES,
    CONST_FILE_DIRECTIVE_COMMENT_RE,
    CONST_GITIGNORE_FILENAME,
    CONST_GITIGNORE_PATTERN_STYLE,
    CONST_NOQA_COMMENT_RE,
    CONST_NOQA_RULE_CODE_RE,
    CONST_NOSEC_COMMENT_RE,
    CONST_PRAGMA_NO_COVER_COMMENT_RE,
    CONST_PRAGMA_NO_MUTATE_COMMENT_RE,
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
    CONST_SUPPRESSION_COMMENT_PREFILTER_RE,
    CONST_SUPPRESSION_KIND_AST_GREP_IGNORE,
    CONST_SUPPRESSION_KIND_COVERAGE_OMIT,
    CONST_SUPPRESSION_KIND_FILE_DIRECTIVE,
    CONST_SUPPRESSION_KIND_MYPY_OVERRIDES,
    CONST_SUPPRESSION_KIND_NOQA_PREFIX,
    CONST_SUPPRESSION_KIND_NOSEC,
    CONST_SUPPRESSION_KIND_PER_FILE_IGNORES,
    CONST_SUPPRESSION_KIND_PRAGMA_NO_COVER,
    CONST_SUPPRESSION_KIND_PRAGMA_NO_MUTATE,
    CONST_SUPPRESSION_KIND_TYPE_IGNORE,
    CONST_SUPPRESSION_KINDS,
    CONST_SUPPRESSION_LINT_RULES,
    CONST_TEST_ASSERTION_LINT_RULES,
    CONST_TYPE_IGNORE_COMMENT_RE,
)
from devops_cli.config.defaults import (
    DEFAULT_C901_SUPPRESSION_CEILING,
    DEFAULT_MAX_COMPLEXITY,
    DEFAULT_MAX_NESTING_DEPTH,
    DEFAULT_NET_CONSTRUCT_SUPPRESSION_CEILING,
    DEFAULT_SUPPRESSION_CEILINGS,
)
from devops_cli.core.code_metrics import measure_tree
from devops_cli.core.import_graph import (
    build_import_graph,
    import_cycle_violations,
    interface_layer_violations,
    verify_acyclic_imports,
)
from devops_cli.exceptions.base import DevOpsCLIError
from tests.support.paths import FIXTURES, GOLDEN, REPO_ROOT, TESTS_ROOT


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


def _parse_src() -> dict[Path, ast.Module]:
    """Parse every module under src/devops_cli once, for the whole-tree invariants."""
    src = REPO_ROOT / "src" / "devops_cli"
    return {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in sorted(src.rglob("*.py"))
    }


def test_the_source_tree_keeps_its_structural_invariants() -> None:
    """Every function under src/devops_cli nests at most DEFAULT_MAX_NESTING_DEPTH deep,
    the module-level import graph has no cycles, and no module outside `devops_cli.commands.*`
    and `devops_cli.main` imports `devops_cli.commands` (#773, #848).

    The function body is depth 1, as the structural-invariants commit hook counts it. This is
    the one test that parses the whole tree: further whole-tree rules belong here, on its parse.
    """
    trees = _parse_src()
    too_deep = [
        f"{path}:{fn.line_number}: {fn.name} nesting {fn.max_nesting_depth}"
        for path, tree in trees.items()
        for fn in measure_tree(tree)
        if fn.max_nesting_depth > DEFAULT_MAX_NESTING_DEPTH
    ]
    assert (
        too_deep,
        import_cycle_violations(trees),
        interface_layer_violations(trees),
    ) == ([], [], [])


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
        raises = [node for node in ast.walk(tree) if isinstance(node, ast.Raise)]
        for node in raises:
            raised = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            exc_name = raised.id if isinstance(raised, ast.Name) else None
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
    src = REPO_ROOT / "src" / "devops_cli"
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


def _is_review_finding_import(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.ImportFrom)
        and bool(node.module and node.module.startswith("devops_cli.review"))
        and any(alias.name == "Finding" for alias in node.names)
    )


def _find_review_finding_callers(src: Path, texts: dict[Path, str]) -> list[str]:
    callers: list[str] = []
    for path, text in texts.items():
        if "Finding(" not in text:
            continue
        rel = path.relative_to(src).as_posix()
        tree = ast.parse(text, filename=str(path))
        if not any(_is_review_finding_import(node) for node in ast.walk(tree)):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else getattr(node.func, "attr", None)
                )
                if name == "Finding" and rel != "review/admission.py":
                    callers.append(f"{rel}:{node.lineno}")
    return callers


def _find_admission_calls_outside_admit(src: Path) -> list[int]:
    adm_path = src / "review" / "admission.py"
    adm_tree = ast.parse(adm_path.read_text(encoding="utf-8"), filename=str(adm_path))
    calls: list[int] = []
    for node in adm_tree.body:
        if isinstance(node, ast.FunctionDef) and node.name != "admit":
            for sub in ast.walk(node):
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Name)
                    and sub.func.id == "Finding"
                ):
                    calls.append(sub.lineno)
    return calls


def test_finding_is_constructed_only_by_admission() -> None:
    """A frozen review Finding is built only by review/admission.py::admit(). (#871)

    A test asserts that no other module constructs one. The test reads source text
    first and parses only files containing 'Finding(', as test_no_module_runs_python_in_process does.
    """
    from devops_cli.review.finding import Finding

    assert Finding.model_config.get("frozen") is True

    src = REPO_ROOT / "src" / "devops_cli"
    texts = {path: path.read_text(encoding="utf-8") for path in src.rglob("*.py")}
    callers = _find_review_finding_callers(src, texts)
    calls_outside_admit = _find_admission_calls_outside_admit(src)

    assert (tuple(callers), tuple(calls_outside_admit)) == ((), ())


def _parse_fixture_trees(root: Path, files: Mapping[str, str]) -> dict[Path, ast.Module]:
    """Write `files` under `root` and return their parsed AST modules."""
    trees: dict[Path, ast.Module] = {}
    for rel, code in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code, encoding="utf-8")
        trees[path] = ast.parse(code, filename=str(path))
    return trees


def test_package_init_importing_sub_where_sub_imports_from_pkg_reports_no_cycle(
    tmp_path: Path,
) -> None:
    """A package `__init__` doing `from . import sub`, where `sub` does `from pkg import name`,
    reports no cycle; `from pkg import name` resolves to `pkg.name` when `name` is a submodule
    and to the package otherwise (#848).
    """
    trees = _parse_fixture_trees(
        tmp_path,
        {
            "pkg/__init__.py": "from . import sub\n",
            "pkg/sub.py": "from pkg import name\nfrom other import CONST\n",
            "pkg/name.py": "VALUE = 1\n",
            "other/__init__.py": "CONST = 2\n",
        },
    )
    graph = build_import_graph(trees, root=tmp_path)
    assert (
        import_cycle_violations(trees, root=tmp_path),
        graph.edges["pkg"],
        graph.edges["pkg.sub"],
    ) == (
        [],
        {"pkg.sub"},
        {"pkg.name", "other"},
    )


def test_top_level_mutual_imports_fail_naming_both_modules(tmp_path: Path) -> None:
    """Top-level mutual imports fail `verify_acyclic_imports` and `import_cycle_violations`,
    naming both modules, file:line, the rule, and the fix (#848).
    """
    trees = _parse_fixture_trees(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/alpha.py": "from pkg import beta\n",
            "pkg/beta.py": "from pkg import alpha\n",
        },
    )
    with pytest.raises(CycleError) as exc_info:
        verify_acyclic_imports(trees, root=tmp_path)
    cycle_msg = str(exc_info.value.args[0])
    violations = import_cycle_violations(trees, root=tmp_path)
    assert (
        len(violations) == 1,
        "pkg.alpha" in cycle_msg and "pkg.beta" in cycle_msg,
        "pkg/alpha.py:1" in violations[0] and "pkg/beta.py:1" in violations[0],
        "rule:" in violations[0] and "fix:" in violations[0],
    ) == (True, True, True, True)


def test_mutual_imports_only_in_functions_or_type_checking_add_no_cycle(
    tmp_path: Path,
) -> None:
    """Mutual imports guarded by `TYPE_CHECKING` or inside function bodies add no cycle (#848)."""
    trees = _parse_fixture_trees(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/alpha.py": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n"
                "    from pkg import beta\n"
                "def call_beta() -> None:\n"
                "    import pkg.beta\n"
            ),
            "pkg/beta.py": (
                "import typing\n"
                "if typing.TYPE_CHECKING:\n"
                "    import pkg.alpha\n"
                "async def call_alpha() -> None:\n"
                "    from pkg import alpha\n"
            ),
        },
    )
    graph = build_import_graph(trees, root=tmp_path)
    assert (
        import_cycle_violations(trees, root=tmp_path),
        graph.edges["pkg.alpha"],
        graph.edges["pkg.beta"],
    ) == ([], set(), set())


def test_function_local_import_of_commands_outside_commands_fails_with_file_and_line(
    tmp_path: Path,
) -> None:
    """A function-local import of `devops_cli.commands.x` outside `devops_cli.commands.*` and
    `devops_cli.main` fails with file:line, the rule, and the fix (#848).
    """
    trees = _parse_fixture_trees(
        tmp_path,
        {
            "devops_cli/__init__.py": "",
            "devops_cli/main.py": "from devops_cli.commands import release\n",
            "devops_cli/commands/__init__.py": "",
            "devops_cli/commands/pr.py": "from devops_cli.commands.gh import _resolve_repo\n",
            "devops_cli/core/cli.py": "def load_main() -> None:\n    import devops_cli.main\n",
            "devops_cli/ai/service.py": (
                "def BadLayerReach() -> None:\n"
                "    from devops_cli.commands.ai_ingest import index_libraries\n"
            ),
        },
    )
    violations = interface_layer_violations(trees, root=tmp_path)
    assert (
        len(violations) == 1,
        "devops_cli/ai/service.py:2" in violations[0],
        "devops_cli.commands.ai_ingest" in violations[0],
        "rule:" in violations[0] and "fix:" in violations[0],
    ) == (True, True, True, True)


def test_task_md_is_decommissioned() -> None:
    """Ensure the monolithic docs/agent/task.md index is decommissioned to eliminate merge conflicts."""
    monolithic_index = Path("docs/agent/task.md")
    assert not monolithic_index.exists(), (
        "docs/agent/task.md has been decommissioned in favor of modular per-task files "
        "in docs/agent/tasks/ and native GitHub Projects v2 boards. Do not re-introduce it."
    )


def test_the_support_paths_are_the_repository_root_and_its_test_data_directories() -> None:
    """Every test module reads the repository root and its test data from `tests.support.paths`,
    which finds them from the `tests` package, so a module reads the same paths at any depth
    (#1312)."""
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert (
        pyproject["project"]["name"],
        TESTS_ROOT == REPO_ROOT / "tests",
        FIXTURES.is_dir(),
        GOLDEN.is_dir(),
    ) == ("devops-cli", True, True, True)


def test_no_stray_scripts_in_project_root() -> None:
    """Ensure no ad-hoc scratch scripts (*.py, *.sh) or stray scripts directories exist in the project root."""
    stray_files = sorted(
        f.name for f in REPO_ROOT.iterdir() if f.is_file() and f.suffix in {".py", ".sh"}
    )
    assert (stray_files, (REPO_ROOT / "scripts").exists()) == (
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
    watched = _ci_image_content_paths(
        REPO_ROOT / ".github" / "workflows" / "ci.yml", job_name=job_name
    )
    sources = _dockerfile_build_context_sources(REPO_ROOT / dockerfile_rel)

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
    pattern = re.compile(r"\b(apt-get|sudo|sysctl)\b")
    mutations = [
        m
        for path in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
        for m in _find_workflow_runner_mutations(path, pattern)
    ]
    dockerfile_text = (REPO_ROOT / ".devcontainer" / "Dockerfile").read_text(encoding="utf-8")
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

    workflows_dir = REPO_ROOT / ".github" / "workflows"

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
    unpinned = _unpinned_dockerfile_images(REPO_ROOT / "Dockerfile")
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
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lint = config["tool"]["ruff"]["lint"]
    unenforced = sorted(
        rule
        for rule in CONST_TEST_ASSERTION_LINT_RULES
        if not _ruff_enforces(rule, lint["select"], lint.get("ignore", []))
    )

    assert (_blind_exception_assertions(REPO_ROOT / "tests"), unenforced) == ([], [])


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
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lint = config["tool"]["ruff"]["lint"]
    unenforced = sorted(
        rule
        for rule in CONST_SUPPRESSION_LINT_RULES
        if not _ruff_enforces(rule, lint["select"], lint.get("ignore", []))
    )
    assert unenforced == []


def test_mypy_ignore_without_code_enabled() -> None:
    """Mypy configuration must enforce ignore-without-code to reject blanket type ignores."""
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
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
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert _complexity_cap_escapes(pyproject, REPO_ROOT) == []


def test_c901_suppressions_stay_under_the_ceiling() -> None:
    """The functions over the cap when Ruff began enforcing it may only become fewer.

    Each carries a C901 marker that RUF100 reports once the function is back under the cap.
    A new marker takes the count past `DEFAULT_C901_SUPPRESSION_CEILING` and fails here.
    """
    excess, files = _c901_suppressions_over(REPO_ROOT, DEFAULT_C901_SUPPRESSION_CEILING)
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


def _inspect_data_path_call(node: ast.Call, rel_path: str) -> str | None:
    func = node.func
    is_path = (isinstance(func, ast.Name) and func.id == "Path") or (
        isinstance(func, ast.Attribute) and func.attr == "Path"
    )
    if not is_path:
        return None
    for arg in node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            if arg.value == ".data" or arg.value.startswith((".data/", "./.data")):
                return f'{rel_path}:{node.lineno}: Path("{arg.value}")'
        if isinstance(arg, ast.Name) and arg.id == "DEFAULT_DATA_DIR":
            return f"{rel_path}:{node.lineno}: Path(DEFAULT_DATA_DIR)"
    return None


def _inspect_data_path_binop(node: ast.BinOp, rel_path: str) -> str | None:
    if isinstance(node.op, ast.Div) and isinstance(node.left, ast.Name):
        if node.left.id == "DEFAULT_DATA_DIR":
            return f"{rel_path}:{node.lineno}: DEFAULT_DATA_DIR / ..."
    return None


def _inspect_data_path_node(node: ast.AST, rel_posix: str) -> str | None:
    if isinstance(node, ast.Call):
        return _inspect_data_path_call(node, rel_posix)
    if isinstance(node, ast.BinOp):
        return _inspect_data_path_binop(node, rel_posix)
    return None


def _file_data_path_violations(py_file: Path, repo_root: Path) -> list[str]:
    rel_posix = py_file.relative_to(repo_root).as_posix()
    if rel_posix == "src/devops_cli/config/defaults.py":
        return []
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    return [
        violation
        for node in ast.walk(tree)
        if (violation := _inspect_data_path_node(node, rel_posix)) is not None
    ]


def test_no_direct_data_dir_path_construction_in_src() -> None:
    """An invariant test fails on any Path built from a .data literal or from DEFAULT_DATA_DIR
    in src/ outside config/defaults.py that does not go through the helper (#1036).
    """
    src_root = REPO_ROOT / "src"
    violations = [
        v
        for py_file in sorted(src_root.rglob("*.py"))
        for v in _file_data_path_violations(py_file, REPO_ROOT)
    ]
    assert violations == [], (
        f"Found direct Path construction from .data literal or DEFAULT_DATA_DIR outside "
        f"config/defaults.py: {violations}. Route through resolve_store_path instead (#1036)."
    )


def test_data_dir_invariant_detects_violations() -> None:
    """Verify AST inspector correctly flags .data literals and DEFAULT_DATA_DIR construction."""
    sample = ast.parse(
        'p1 = Path(".data/k8s")\np2 = DEFAULT_DATA_DIR / "sub"\np3 = Path(DEFAULT_DATA_DIR)\n'
    )
    detected = [
        violation
        for node in ast.walk(sample)
        if (violation := _inspect_data_path_node(node, "sample.py")) is not None
    ]
    assert len(detected) == 3


# mutmut reads a comment holding both as a `no mutate` pragma (`_parse_pragma_token`). They stay
# here, not in src, where a line holding both would itself be one.
_MUTMUT_PRAGMA_MARKERS = ("# pragma:", "no mutate")


def _no_mutate_pragmas(root: Path) -> list[str]:
    """Each `file:line` under `root/src` holding a mutmut `no mutate` pragma."""
    return [
        f"{path.relative_to(root).as_posix()}:{number}"
        for path in sorted((root / "src").rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if all(marker in line for marker in _MUTMUT_PRAGMA_MARKERS)
    ]


def test_no_source_line_exempts_itself_from_mutation() -> None:
    """`devops ci mutate` reports what survives; a pragma under src would hide it (#853)."""
    assert _no_mutate_pragmas(REPO_ROOT) == []


def test_a_no_mutate_pragma_is_reported(tmp_path: Path) -> None:
    """The check names the file and line of a pragma, and passes a line without one."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mod.py").write_text(
        "y = 2  # pragma: no cover\nx = 1  # pragma: no mutate\n", encoding="utf-8"
    )
    assert _no_mutate_pragmas(tmp_path) == ["src/mod.py:2"]


_SIMPLE_COMMENT_SUPPRESSION_PATTERNS = (
    (CONST_TYPE_IGNORE_COMMENT_RE, CONST_SUPPRESSION_KIND_TYPE_IGNORE),
    (CONST_NOSEC_COMMENT_RE, CONST_SUPPRESSION_KIND_NOSEC),
    (CONST_PRAGMA_NO_COVER_COMMENT_RE, CONST_SUPPRESSION_KIND_PRAGMA_NO_COVER),
    (CONST_PRAGMA_NO_MUTATE_COMMENT_RE, CONST_SUPPRESSION_KIND_PRAGMA_NO_MUTATE),
    (CONST_FILE_DIRECTIVE_COMMENT_RE, CONST_SUPPRESSION_KIND_FILE_DIRECTIVE),
)


def _noqa_kinds_from_comment(tree_name: str, comment: str) -> list[str]:
    """Extract per-rule-code noqa suppression kinds from one comment token."""
    kinds: list[str] = []
    for match in CONST_NOQA_COMMENT_RE.finditer(comment):
        raw_codes = match.group("codes")
        if not raw_codes:
            kinds.append(f"{tree_name} {CONST_SUPPRESSION_KIND_NOQA_PREFIX}")
            continue
        for code in CONST_NOQA_RULE_CODE_RE.findall(raw_codes.upper()):
            kinds.append(f"{tree_name} {CONST_SUPPRESSION_KIND_NOQA_PREFIX}: {code}")
    return kinds


def _ast_grep_kinds_from_comment(tree_name: str, comment: str) -> list[str]:
    """Extract one ast-grep-ignore kind per net-* rule id in a src comment token."""
    if tree_name != "src":
        return []
    return [
        f"{tree_name} {CONST_SUPPRESSION_KIND_AST_GREP_IGNORE}"
        for match in CONST_AST_GREP_IGNORE_COMMENT_RE.finditer(comment)
        for _ in CONST_AST_GREP_NET_RULE_ID_RE.findall(match.group("ids") or "")
    ]


def _comment_token_suppressions(tree_name: str, comment: str) -> list[str]:
    """Return all suppression kinds present in a single comment token."""
    simple = [
        f"{tree_name} {kind}"
        for pattern, kind in _SIMPLE_COMMENT_SUPPRESSION_PATTERNS
        for _ in pattern.finditer(comment)
    ]
    return [
        *simple,
        *_noqa_kinds_from_comment(tree_name, comment),
        *_ast_grep_kinds_from_comment(tree_name, comment),
    ]


def _file_comment_suppressions(
    py_file: Path,
    project: Path,
    tree_name: str,
    by_kind: dict[str, dict[str, int]],
) -> None:
    """Tokenize a Python file when its raw text holds candidate markers and count comment tokens."""
    text = py_file.read_text(encoding="utf-8")
    if not CONST_SUPPRESSION_COMMENT_PREFILTER_RE.search(text):
        return
    rel_posix = py_file.relative_to(project).as_posix()
    comments = (
        tok.string
        for tok in tokenize.generate_tokens(io.StringIO(text).readline)
        if tok.type == tokenize.COMMENT
        and CONST_SUPPRESSION_COMMENT_PREFILTER_RE.search(tok.string)
    )
    for comment in comments:
        for kind in _comment_token_suppressions(tree_name, comment):
            by_kind[kind][rel_posix] = by_kind[kind].get(rel_posix, 0) + 1


def _pyproject_per_file_ignores_count(ruff_cfg: Mapping[str, Any]) -> int:
    """Count per-file-ignores entries across top-level and lint Ruff tables."""
    tables = (ruff_cfg, ruff_cfg.get("lint", {}))
    entries = [
        codes
        for table in tables
        if isinstance(table, Mapping)
        for key in CONST_RUFF_PER_FILE_IGNORE_KEYS
        for codes in (table.get(key) or {}).values()
    ]
    return sum(max(len(codes), 1) if isinstance(codes, list) else 1 for codes in entries)


def _pyproject_coverage_omit_count(cov_cfg: Mapping[str, Any]) -> int:
    """Count coverage omit entries across [tool.coverage] and its sub-tables."""
    sections = [cov_cfg, *(v for v in cov_cfg.values() if isinstance(v, Mapping))]
    return sum(len(sec.get("omit", [])) for sec in sections if isinstance(sec.get("omit"), list))


def _pyproject_suppressions(
    pyproject: Mapping[str, Any],
    by_kind: dict[str, dict[str, int]],
) -> None:
    """Record per-file-ignores, mypy overrides, and coverage omit counts from pyproject.toml."""
    tool = pyproject.get("tool", {})
    counts = {
        CONST_SUPPRESSION_KIND_PER_FILE_IGNORES: _pyproject_per_file_ignores_count(
            tool.get("ruff", {})
        ),
        CONST_SUPPRESSION_KIND_MYPY_OVERRIDES: len(tool.get("mypy", {}).get("overrides", [])),
        CONST_SUPPRESSION_KIND_COVERAGE_OMIT: _pyproject_coverage_omit_count(
            tool.get("coverage", {})
        ),
    }
    for kind, count in counts.items():
        if count > 0:
            by_kind[kind]["pyproject.toml"] = count


def _collect_suppressions(
    project: Path,
    pyproject: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, int]]:
    """Collect all comment-token and pyproject.toml suppressions across src and tests (#849)."""
    by_kind: dict[str, dict[str, int]] = defaultdict(dict)
    for tree_name in CONST_COMPLEXITY_CAP_ROOTS:
        tree_root = project / tree_name
        if not tree_root.is_dir():
            continue
        for py_file in sorted(tree_root.rglob("*.py")):
            _file_comment_suppressions(py_file, project, tree_name, by_kind)
    if pyproject is None and (project / "pyproject.toml").is_file():
        pyproject = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))
    if pyproject is not None:
        _pyproject_suppressions(pyproject, by_kind)
    return dict(by_kind)


def _suppression_ceiling_breaches(
    project: Path,
    ceilings: Mapping[str, int] = DEFAULT_SUPPRESSION_CEILINGS,
    pyproject: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return a diagnostic message for each suppression kind whose count exceeds its ceiling (#849)."""
    by_kind = _collect_suppressions(project, pyproject=pyproject)
    breaches: list[str] = []
    for kind in sorted(set(ceilings) | set(by_kind)):
        files = by_kind.get(kind, {})
        total = sum(files.values())
        ceiling = ceilings.get(kind, 0)
        if total > ceiling:
            breaches.append(
                f"{kind}: {total} > ceiling {ceiling} in {sorted(files)}. "
                "Fix the cause, or raise the ceiling in src/devops_cli/config/defaults.py "
                "with a reason recorded in the task file (docs/agent/tasks/)."
            )
    return breaches


def test_suppressions_stay_under_their_ceilings() -> None:
    """Suppression comments in src/ and tests/ and waivers in pyproject.toml may not exceed ceilings (#849)."""
    assert (
        len(CONST_SUPPRESSION_KINDS),
        DEFAULT_SUPPRESSION_CEILINGS["src noqa: C901"],
        DEFAULT_SUPPRESSION_CEILINGS["src ast-grep-ignore"],
    ) == (
        10,
        DEFAULT_C901_SUPPRESSION_CEILING,
        DEFAULT_NET_CONSTRUCT_SUPPRESSION_CEILING,
    )
    breaches = _suppression_ceiling_breaches(REPO_ROOT)
    assert breaches == [], "\n".join(breaches)


def test_adding_a_type_ignore_in_src_fails_naming_kind_ceiling_and_file(tmp_path: Path) -> None:
    """Adding one `# type: ignore` in src fails the ceiling check naming kind, ceiling, and file (#849)."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "mod.py").write_text(
        "x: int = 'a'  # type: ignore[assignment]\ny: int = 'b'  # type: ignore[assignment]\n",
        encoding="utf-8",
    )
    ceilings = {"src type: ignore": 1}
    breaches = _suppression_ceiling_breaches(tmp_path, ceilings=ceilings, pyproject={})
    assert (
        len(breaches) == 1,
        "src type: ignore" in breaches[0],
        "ceiling 1" in breaches[0],
        "src/mod.py" in breaches[0],
        "task file" in breaches[0],
    ) == (True, True, True, True, True)


def test_nanosecond_comment_and_string_literals_are_not_counted(tmp_path: Path) -> None:
    """A comment with 'nanosecond' and string literals holding suppression text are ignored (#849)."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "tracer.py").write_text(
        "# Each interval is a nanosecond long, so points never overlap.\n"
        'literal = "# type: ignore[assignment]  # nosec B108  # pragma: no cover"\n',
        encoding="utf-8",
    )
    assert (
        _collect_suppressions(tmp_path, pyproject={}),
        _suppression_ceiling_breaches(tmp_path, ceilings={}, pyproject={}),
    ) == ({}, [])


def test_removing_a_suppression_keeps_the_ceiling_check_green(tmp_path: Path) -> None:
    """Counts strictly below the ceiling stay green under `count <= ceiling` (#849)."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "mod.py").write_text(
        "x: int = 'a'  # type: ignore[assignment]\n",
        encoding="utf-8",
    )
    assert (
        _suppression_ceiling_breaches(
            tmp_path,
            ceilings={"src type: ignore": 5, "src nosec": 2},
            pyproject={},
        )
        == []
    )


def test_every_comment_and_pyproject_suppression_kind_is_counted(tmp_path: Path) -> None:
    """Verify per-rule noqa, nosec, pragmas, file-level directives, ast-grep-ignore, and pyproject waivers (#849)."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "mod.py").write_text(
        f"{_RUFF_FILE_NOQA}: F401\n"
        "a = 1  # noqa: F401, E402\n"
        "b = 2  # nosec B108\n"
        "c = 3  # pragma: no cover\n"
        "d = 4  # pragma: no mutate\n"
        "e = 5  # ast-grep-ignore: net-url-split, net-host-parse\n",
        encoding="utf-8",
    )
    pyproject = {
        "tool": {
            "ruff": {"lint": {"per-file-ignores": {"tests/*": ["S101", "D100"]}}},
            "mypy": {"overrides": [{"module": "foo.*"}, {"module": "bar.*"}]},
            "coverage": {"run": {"omit": ["src/generated/*"]}},
        }
    }
    collected = _collect_suppressions(tmp_path, pyproject=pyproject)
    assert collected == {
        "src file-level directive": {"src/mod.py": 1},
        "src noqa: F401": {"src/mod.py": 1},
        "src noqa: E402": {"src/mod.py": 1},
        "src nosec": {"src/mod.py": 1},
        "src pragma: no cover": {"src/mod.py": 1},
        "src pragma: no mutate": {"src/mod.py": 1},
        "src ast-grep-ignore": {"src/mod.py": 2},
        "per-file-ignores": {"pyproject.toml": 2},
        "[[tool.mypy.overrides]]": {"pyproject.toml": 2},
        "coverage omit": {"pyproject.toml": 1},
    }


def _find_package_submodules(pkg_dir: Path) -> set[str]:
    """Return all valid Python submodule names inside a package directory."""
    if not pkg_dir.is_dir():
        return set()
    return {
        child.stem if child.is_file() else child.name
        for child in pkg_dir.iterdir()
        if (child.is_file() and child.name.endswith(".py") and child.name != "__init__.py")
        or (child.is_dir() and (child / "__init__.py").exists())
    }


def _collect_facade_import_violations(
    tree: ast.AST,
    allowed_submodules: Mapping[str, set[str]],
    origin: str,
) -> list[str]:
    """Find any ImportFrom node on facade packages importing a non-submodule name."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module not in allowed_submodules:
            continue
        allowed = allowed_submodules[node.module]
        for alias in node.names:
            if alias.name not in allowed:
                violations.append(f"{origin}:{node.lineno}: from {node.module} import {alias.name}")
    return violations


def test_ai_and_github_package_inits_hold_only_docstrings() -> None:
    """The four __init__.py files parse to a single docstring expression and nothing else (#1002)."""
    init_paths = [
        REPO_ROOT / "src" / "devops_cli" / "ai" / "__init__.py",
        REPO_ROOT / "src" / "devops_cli" / "ai" / "agents" / "__init__.py",
        REPO_ROOT / "src" / "devops_cli" / "ai" / "mcp" / "__init__.py",
        REPO_ROOT / "src" / "devops_cli" / "github" / "__init__.py",
    ]
    failures = []
    for path in init_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        is_only_docstring = (
            len(tree.body) == 1
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        )
        if not is_only_docstring:
            failures.append(str(path.relative_to(REPO_ROOT)))
    assert failures == []


def test_no_non_submodule_imports_from_ai_and_github_facades() -> None:
    """No import from devops_cli.ai, devops_cli.ai.agents, devops_cli.ai.mcp, or devops_cli.github names anything but a submodule (#1002)."""
    facade_packages = {
        "devops_cli.ai": REPO_ROOT / "src" / "devops_cli" / "ai",
        "devops_cli.ai.agents": REPO_ROOT / "src" / "devops_cli" / "ai" / "agents",
        "devops_cli.ai.mcp": REPO_ROOT / "src" / "devops_cli" / "ai" / "mcp",
        "devops_cli.github": REPO_ROOT / "src" / "devops_cli" / "github",
    }
    allowed_submodules = {
        pkg_name: _find_package_submodules(pkg_dir) for pkg_name, pkg_dir in facade_packages.items()
    }
    violations: list[str] = []

    for search_dir in (REPO_ROOT / "src", REPO_ROOT / "tests"):
        for py_file in search_dir.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
                violations.extend(
                    _collect_facade_import_violations(
                        tree, allowed_submodules, str(py_file.relative_to(REPO_ROOT))
                    )
                )
            except SyntaxError:
                continue

    fenced_re = re.compile(r"```python\n(.*?)```", re.DOTALL)
    kb_dir = REPO_ROOT / "src" / "devops_cli" / "ai" / "knowledge_base"
    if kb_dir.is_dir():
        for md_file in kb_dir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            for idx, match in enumerate(fenced_re.finditer(content)):
                try:
                    tree = ast.parse(match.group(1))
                    violations.extend(
                        _collect_facade_import_violations(
                            tree,
                            allowed_submodules,
                            f"{md_file.relative_to(REPO_ROOT)} (block {idx + 1})",
                        )
                    )
                except SyntaxError:
                    continue

    assert violations == []
