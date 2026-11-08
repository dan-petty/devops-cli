"""Test-first specification for architectural and stylistic invariants in devops-cli."""

from __future__ import annotations

import ast
import io
import re
import subprocess
import tokenize
import tomllib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from graphlib import CycleError
from pathlib import Path, PurePosixPath
from typing import Any, Final

import pytest

from devops_cli.config.constants import (
    CONST_PYTHON_FILE_SUFFIX,
    CONST_SOURCE_ROOT_DIR,
)
from devops_cli.core.import_graph import (
    build_import_graph,
    import_cycle_violations,
    interface_layer_violations,
    verify_acyclic_imports,
)
from devops_cli.core.repo import list_repo_files
from devops_cli.docs.inventory import hand_written_documents
from devops_cli.exceptions.base import DevOpsCLIError
from tests.gate.ruff_selection import ruff_enforces
from tests.support.paths import FIXTURES, GOLDEN, REPO_ROOT, TESTS_ROOT
from tests.support.trees import (
    parse_count,
    parse_python_file,
    parse_source_trees,
)

CONST_SUPPRESSION_LINT_RULES: Final[frozenset[str]] = frozenset({"PGH003", "RUF100"})
CONST_RUFF_PER_FILE_IGNORE_KEYS: Final[tuple[str, ...]] = (
    "per-file-ignores",
    "extend-per-file-ignores",
)
CONST_COMPLEXITY_CAP_ROOTS: Final[tuple[str, ...]] = ("src", "tests")
CONST_RUFF_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi", ".ipynb"})
CONST_SUPPRESSION_KIND_TYPE_IGNORE: Final[str] = "type: ignore"
CONST_SUPPRESSION_KIND_NOQA_PREFIX: Final[str] = "noqa"
CONST_SUPPRESSION_KIND_NOSEC: Final[str] = "nosec"
CONST_SUPPRESSION_KIND_PRAGMA_NO_COVER: Final[str] = "pragma: no cover"
CONST_SUPPRESSION_KIND_PRAGMA_NO_MUTATE: Final[str] = "pragma: no mutate"
CONST_SUPPRESSION_KIND_FILE_DIRECTIVE: Final[str] = "file-level directive"
CONST_SUPPRESSION_KIND_AST_GREP_IGNORE: Final[str] = "ast-grep-ignore"
CONST_SUPPRESSION_KIND_PER_FILE_IGNORES: Final[str] = "per-file-ignores"
CONST_SUPPRESSION_KIND_MYPY_OVERRIDES: Final[str] = "[[tool.mypy.overrides]]"
CONST_SUPPRESSION_KIND_COVERAGE_OMIT: Final[str] = "coverage omit"
CONST_COMMENT_SUPPRESSION_KINDS: Final[tuple[str, ...]] = (
    CONST_SUPPRESSION_KIND_TYPE_IGNORE,
    CONST_SUPPRESSION_KIND_NOQA_PREFIX,
    CONST_SUPPRESSION_KIND_NOSEC,
    CONST_SUPPRESSION_KIND_PRAGMA_NO_COVER,
    CONST_SUPPRESSION_KIND_PRAGMA_NO_MUTATE,
    CONST_SUPPRESSION_KIND_FILE_DIRECTIVE,
    CONST_SUPPRESSION_KIND_AST_GREP_IGNORE,
)
CONST_PYPROJECT_SUPPRESSION_KINDS: Final[tuple[str, ...]] = (
    CONST_SUPPRESSION_KIND_PER_FILE_IGNORES,
    CONST_SUPPRESSION_KIND_MYPY_OVERRIDES,
    CONST_SUPPRESSION_KIND_COVERAGE_OMIT,
)
CONST_SUPPRESSION_KINDS: Final[tuple[str, ...]] = (
    *CONST_COMMENT_SUPPRESSION_KINDS,
    *CONST_PYPROJECT_SUPPRESSION_KINDS,
)
CONST_SUPPRESSION_COMMENT_PREFILTER_RE: Final[re.Pattern[str]] = re.compile(
    r"#[^\n]*(?:type[^\S\n]*:[^\S\n]*ignore\b|noqa\b|nosec\b"
    r"|pragma[^\S\n]*:[^\S\n]*no[^\S\n]+(?:cover|mutate)\b"
    r"|(?:ruff|flake8|mypy|pyright|pylint|bandit)[^\S\n]*:|ast-grep-ignore\b)",
    re.IGNORECASE,
)
CONST_TYPE_IGNORE_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^\S\n])#[^\S\n]*type[^\S\n]*:[^\S\n]*ignore\b", re.IGNORECASE
)
CONST_NOQA_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^\S\n])#[^\S\n]*noqa(?:[^\S\n]*:[^\S\n]*"
    r"(?P<codes>[A-Z0-9]+(?:(?:[^\S\n]*,[^\S\n]*|[^\S\n]+)[A-Z0-9]+)*)|(?=$|[^\S\n]+#))",
    re.IGNORECASE,
)
CONST_NOQA_RULE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"[A-Z0-9]+")
CONST_NOSEC_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^\S\n])#[^\S\n]*nosec\b", re.IGNORECASE
)
# A `# nosec` in src names its Bandit rules and, after a second `#`, why (#1538). Bandit reads the
# rules up to that `#`, so the reason never reaches its rule list.
CONST_NOSEC_WITH_REASON_RE: Final[re.Pattern[str]] = re.compile(
    r"#[^\S\n]*nosec[^\S\n]+B\d{3}(?:[^\S\n]*,[^\S\n]*B\d{3})*[^\S\n]+#[^\S\n]*\S"
)
CONST_PRAGMA_NO_COVER_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^\S\n])#[^\S\n]*pragma[^\S\n]*:[^\S\n]*no[^\S\n]+cover\b", re.IGNORECASE
)
CONST_PRAGMA_NO_MUTATE_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^\S\n])#[^\S\n]*pragma[^\S\n]*:[^\S\n]*no[^\S\n]+mutate\b", re.IGNORECASE
)
CONST_FILE_DIRECTIVE_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^\S\n])#[^\S\n]*(?:(?:ruff|flake8)[^\S\n]*:[^\S\n]*noqa\b"
    r"|ruff[^\S\n]*:[^\S\n]*(?:file-ignore|disable|ignore)\b"
    r"|(?:mypy|pyright)[^\S\n]*:|(?:pylint|bandit)[^\S\n]*:[^\S\n]*skip-file\b)",
    re.IGNORECASE,
)
CONST_AST_GREP_IGNORE_COMMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[^\S\n])#[^\S\n]*ast-grep-ignore(?:[^\S\n]*:[^\S\n]*(?P<ids>[^\n#]+))?\b",
    re.IGNORECASE,
)
CONST_AST_GREP_RULE_ID_SEPARATOR: Final[str] = ","

DEFAULT_C901_SUPPRESSION_CEILING: int = 25
DEFAULT_AST_GREP_SUPPRESSION_CEILING: int = 0
DEFAULT_SUPPRESSION_CEILINGS: dict[str, int] = {
    "src type: ignore": 40,
    "src noqa: C901": DEFAULT_C901_SUPPRESSION_CEILING,
    "src noqa: E402": 2,
    "src noqa: F401": 0,
    "src noqa: SIM115": 1,
    "src noqa: UP036": 1,
    # #1538: `.bandit` skips B603, so the three `# nosec B603` markers went.
    "src nosec": 10,
    "src pragma: no cover": 1,
    "src pragma: no mutate": 0,
    "src file-level directive": 0,
    "src ast-grep-ignore": DEFAULT_AST_GREP_SUPPRESSION_CEILING,
    "tests type: ignore": 79,
    "tests noqa: F401": 3,
    "tests noqa: N803": 1,
    "tests nosec": 17,
    "tests pragma: no cover": 0,
    "tests pragma: no mutate": 0,
    "tests file-level directive": 0,
    "tests ast-grep-ignore": DEFAULT_AST_GREP_SUPPRESSION_CEILING,
    "per-file-ignores": 0,
    "[[tool.mypy.overrides]]": 1,
    "coverage omit": 0,
}


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


def _parse_src() -> dict[Path, ast.Module]:
    """Parse every module under src/devops_cli once, for the whole-tree invariants."""
    return parse_source_trees(REPO_ROOT)


def test_the_source_tree_keeps_its_structural_invariants(
    parsed_source_trees: dict[Path, ast.Module],
) -> None:
    """The module-level import graph under src/devops_cli has no cycles, and no module outside
    `devops_cli.commands.*` and `devops_cli.main` imports `devops_cli.commands` (#773, #848).

    Nesting depth is Ruff's PLR1702 in `ruff check` (#1876). This is the one test that parses the
    whole tree: further whole-tree rules belong here, on its parse.
    """
    trees = parsed_source_trees
    assert (
        import_cycle_violations(trees),
        interface_layer_violations(trees),
    ) == ([], [])


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
        Path("src/devops_cli/ai/harness/skills.py"),
        Path("src/devops_cli/ai/harness/slots.py"),
    ]

    violations: list[str] = []

    for mod_path in modules_to_check:
        assert mod_path.exists(), f"Path {mod_path} does not exist"
        tree = parse_python_file(mod_path)
        raises = [node for node in ast.walk(tree) if isinstance(node, ast.Raise)]
        for node in raises:
            raised = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            exc_name = raised.id if isinstance(raised, ast.Name) else None
            if exc_name in prohibited_exceptions:
                violations.append(f"{mod_path}:{node.lineno} raises bare {exc_name}")

    assert not violations, "Prohibited generic exceptions raised in domain modules:\n" + "\n".join(
        violations
    )


def test_no_module_runs_python_in_process(
    parsed_source_trees: dict[Path, ast.Module],
) -> None:
    """Name every source module that calls the `exec` or `eval` builtin; there must be none.

    Code run by `exec` in this process is not contained by an AST check or a trimmed
    `__builtins__`: a script handed `typing` reaches `os` through `typing.sys.modules`, and one
    handed `asyncio` starts processes. The two harness capabilities that ran model-written
    scripts this way were deleted rather than patched (#947). Model code that has to run
    belongs in the host sandbox (bwrap) instead.
    """
    src = REPO_ROOT / "src" / "devops_cli"
    callers = sorted(
        {
            path.relative_to(src).as_posix()
            for path, tree in parsed_source_trees.items()
            for node in ast.walk(tree)
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


def _find_review_finding_callers(
    src: Path,
    texts: dict[Path, str],
    trees: Mapping[Path, ast.Module] | None = None,
) -> list[str]:
    callers: list[str] = []
    for path, text in texts.items():
        if "Finding(" not in text:
            continue
        rel = path.relative_to(src).as_posix()
        tree = trees[path] if trees and path in trees else parse_python_file(path)
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


def _find_admission_calls_outside_admit(
    src: Path,
    trees: Mapping[Path, ast.Module] | None = None,
) -> list[int]:
    adm_path = src / "review" / "admission.py"
    adm_tree = trees[adm_path] if trees and adm_path in trees else parse_python_file(adm_path)
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


def test_finding_is_constructed_only_by_admission(
    parsed_source_trees: dict[Path, ast.Module],
) -> None:
    """A frozen review Finding is built only by review/admission.py::admit(). (#871)

    A test asserts that no other module constructs one. The test reads source text
    first and parses only files containing 'Finding(', as test_no_module_runs_python_in_process does.
    """
    from devops_cli.review.finding import Finding

    assert Finding.model_config.get("frozen") is True

    src = REPO_ROOT / "src" / "devops_cli"
    texts = {path: path.read_text(encoding="utf-8") for path in src.rglob("*.py")}
    callers = _find_review_finding_callers(src, texts, trees=parsed_source_trees)
    calls_outside_admit = _find_admission_calls_outside_admit(src, trees=parsed_source_trees)

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
            "devops_cli/main.py": "from devops_cli.commands import docs\n",
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
        "docs/agent/task.md has been decommissioned in favor of OpenSpec change folders "
        "in openspec/changes/ and native GitHub Projects v2 boards. Do not re-introduce it."
    )


# The directory of the task files, which OpenSpec change folders replaced (#1847, ADR 0010). It is
# built from its parts, so the scan of `tests/` does not find this test. Git history keeps the files.
_TASK_FILES_DIR = PurePosixPath("docs", "agent", "tasks").as_posix()
# The trees that could still send a reader or a program to the task files, beside the hand-written
# documents. The records (the ADRs, the changelog and the archive of past phases) keep their history.
_TASK_FILES_SCAN_ROOTS = ("src", "tests", "k8s", ".github")


def _files_that_name_the_task_files(root: Path) -> list[str]:
    """Each file of the code, the tests, the manifests, the GitHub files and the hand-written
    documents under `root` that names the task files' directory, by repository path."""
    hand_written = {
        PurePosixPath(path.relative_to(root).as_posix()) for path in hand_written_documents(root)
    }
    paths = [PurePosixPath(path.relative_to(root).as_posix()) for path in list_repo_files(root)]
    scanned = [
        path for path in paths if path.parts[0] in _TASK_FILES_SCAN_ROOTS or path in hand_written
    ]
    return sorted(
        path.as_posix()
        for path in scanned
        if _TASK_FILES_DIR.encode() in (root / path).read_bytes()
    )


def test_the_task_files_are_decommissioned() -> None:
    """An OpenSpec change folder is the record of every item (#1847), and the task files that
    merged after that switch are deleted too (#2041). So the directory does not exist, and no
    code, test, manifest, GitHub file or hand-written document names it."""
    assert (
        (REPO_ROOT / _TASK_FILES_DIR).exists(),
        _files_that_name_the_task_files(REPO_ROOT),
    ) == (False, [])


def test_a_file_that_names_the_task_files_is_reported(tmp_path: Path) -> None:
    """Negative control: code and a hand-written document that name the directory are reported,
    and a decision record that names it, and code that does not, are not."""
    files = {
        "src/pkg/readiness.py": f'TASKS = "{_TASK_FILES_DIR}"\n',
        "README.md": f"Write the record in `{_TASK_FILES_DIR}/`.\n",
        "docs/adr/0001-roadmap.md": f"Task files lived in `{_TASK_FILES_DIR}/`.\n",
        "src/pkg/other.py": 'CHANGES = "openspec/changes"\n',
    }
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")

    assert _files_that_name_the_task_files(tmp_path) == ["README.md", "src/pkg/readiness.py"]


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


def _stray_root_scripts(root: Path) -> list[str]:
    """Name the `.py` and `.sh` files that lie directly in `root`; a directory is never one."""
    return sorted(
        entry.name for entry in root.iterdir() if entry.is_file() and entry.suffix in {".py", ".sh"}
    )


def test_no_stray_scripts_in_project_root() -> None:
    """The project root holds no ad-hoc scratch script (`*.py`, `*.sh`)."""
    assert _stray_root_scripts(REPO_ROOT) == []


def test_a_reviewed_scripts_directory_is_no_stray_script(tmp_path: Path) -> None:
    """A committed helper under `scripts/` is not a scratch script in the project root."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "helper.py").write_text("print('ok')\n", encoding="utf-8")
    assert _stray_root_scripts(tmp_path) == []


@pytest.mark.parametrize("name", ["tmp_x.py", "scratch_x.py", "debug_x.py", "test_x.py", "x.sh"])
def test_a_scratch_script_in_the_project_root_is_stray(tmp_path: Path, name: str) -> None:
    """Each scratch pattern of the rule still fails when it lies in the project root."""
    (tmp_path / name).write_text("", encoding="utf-8")
    assert _stray_root_scripts(tmp_path) == [name]


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
        ("runner-image", "Dockerfile"),
        ("mcp-server-image", "Dockerfile"),
    ],
)
def test_image_path_filter_covers_dockerfile_sources(job_name: str, dockerfile_rel: str) -> None:
    """The CI image-change filter must cover every path baked into the container image.

    The container image packages devops-cli itself. If a new `COPY` starts pulling a path
    the workflow's change detection does not watch, CI would skip the image check while
    still reporting success.
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
        f"would skip the image check."
    )

    # The build definition itself must be watched, not just the copied build context.
    assert _covered(dockerfile_rel), (
        f"The CI image-change filter must watch {dockerfile_rel}; a change to the "
        "build recipe alters the image even when no copied source file changes."
    )

    # The workflow fixes the image name, tags, cache source, and builder action version,
    # so a change to it alters the image the check builds even with identical build inputs.
    assert _covered(".github/workflows/ci.yml"), (
        "The CI image-change filter must watch the workflow that performs the build; "
        "changing the image name, tag, cache source, or builder version alters the "
        "image without touching any build input."
    )

    # Each filter must also watch .dockerignore
    assert _covered(".dockerignore"), (
        f"The CI image-change filter for {job_name} must watch .dockerignore."
    )

    # Shared actions build and start the devcontainer image, and their steps alter the check
    # as much as the workflow that calls them (#1895).
    if job_name == "devcontainer":
        assert [
            action
            for action in ("devcontainer-image", "devcontainer-smoke")
            if not _covered(f".github/actions/{action}/action.yml")
        ] == [], "The CI image-change filter for devcontainer must watch the actions it runs."


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
        job_ifs.get("Tests & Coverage")
        in (
            None,
            "github.event_name != 'schedule'",
            "${{ !cancelled() && github.event_name != 'schedule' }}",
        ),
    ) == (
        ACTIONS_WRITE_ALLOWLIST,
        True,
        True,
        True,
    )


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
        ruff_enforces("B017", ["E", "F", "B017"], ["E501"]),
        ruff_enforces("B017", ["E", "F", "B017"], ["B"]),
        ruff_enforces("B017", ["E", "F", "B"], []),
        ruff_enforces("B017", ["E", "F"], []),
    ]
    assert cases == [True, True, True, False]


def test_a_broad_ignore_defeats_a_broad_select() -> None:
    """`ALL` is the least specific selection, so any explicit ignore outranks it."""
    assert (
        ruff_enforces("RUF043", ["ALL"], ["RUF"]),
        ruff_enforces("RUF043", ["ALL"], []),
    ) == (False, True)


def test_suppression_lint_rules_enforced() -> None:
    """Rules that audit suppressions (PGH003, RUF100) must remain enforced by Ruff configuration."""
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lint = config["tool"]["ruff"]["lint"]
    unenforced = sorted(
        rule
        for rule in CONST_SUPPRESSION_LINT_RULES
        if not ruff_enforces(rule, lint["select"], lint.get("ignore", []))
    )
    assert unenforced == []


def test_mypy_ignore_without_code_enabled() -> None:
    """Mypy configuration must enforce ignore-without-code to reject blanket type ignores."""
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    enabled = config.get("tool", {}).get("mypy", {}).get("enable_error_code", [])
    assert "ignore-without-code" in enabled


def _git_output(project: Path, *args: str) -> str:
    """Run git in `project` and return what it prints; a git failure ends the test with git's reason."""
    done = subprocess.run(
        ["git", "-C", str(project), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=_GIT_TIMEOUT_SECONDS,
    )
    if done.returncode:
        pytest.fail(
            f"git {args[0]} failed in {project}: {done.stderr.strip()[:256]}", pytrace=False
        )
    return done.stdout


def _tracked_paths(project: Path, *pathspecs: str) -> list[str]:
    """Name the files git tracks under `project` that the pathspecs select, or every one when none is given (#1787)."""
    return [
        name
        for name in _git_output(project, "ls-files", "-z", "--", *pathspecs).split("\0")
        if name
    ]


# Built here so this file's own text holds no file-level exemption, no C901 marker and no
# Ruff suppression comment naming C901. Ruff honours each spelling below (checked on 0.16.8).
_RUFF_FILE_NOQA = "# " + "ruff" + ": noqa"
_FLAKE8_FILE_NOQA = "# " + "flake8" + ": noqa"
_C901_MARKER = "# " + "noqa: " + "C901"
_RUFF_COMMENT = "# " + "ruff" + ": "
_FORM_FEED, _NO_BREAK_SPACE, _EM_SPACE = "\x0c", "\xa0", "\u2003"


@pytest.fixture
def git_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop the variables git sets for a hook, which would point each git call at the committer's repository (#1787)."""
    local_variables = subprocess.run(
        ["git", "rev-parse", "--local-env-vars"],
        capture_output=True,
        text=True,
        check=True,
        timeout=_GIT_TIMEOUT_SECONDS,
    ).stdout.split()
    for name in local_variables:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def git_project(tmp_path: Path, git_environment: None) -> Path:
    """An empty git repository, in which a commit needs neither a signature nor an identity from the host (#1787)."""
    _git_output(tmp_path, "init", "--quiet")
    for key, value in (("user.name", "Test"), ("user.email", "test@example.com")):
        _git_output(tmp_path, "config", key, value)
    _git_output(tmp_path, "config", "commit.gpgsign", "false")
    return tmp_path


def _track_everything(project: Path) -> None:
    """Stage every file under `project`, one `.gitignore` matches too, as a committed tree holds it (#1787)."""
    _git_output(project, "add", "--force", "--all")


@pytest.fixture
def hook_git_variables(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Set the repository variables of a commit hook in a linked worktree, to an empty directory that is returned (#1787).

    A test lists this fixture before `git_project`, so the variables are set when `git_environment` runs.
    """
    hook_directory = tmp_path_factory.mktemp("hook")
    monkeypatch.setenv("GIT_DIR", str(hook_directory / "git-dir"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(hook_directory / "index"))
    return hook_directory


def test_a_git_project_leaves_the_repository_of_a_commit_hook_alone(
    hook_git_variables: Path, git_project: Path
) -> None:
    """A commit hook runs this file, so git in a temporary repository must not write to the repository of the commit (#1787)."""
    (git_project / "tracked.txt").write_text("x\n", encoding="utf-8")
    _track_everything(git_project)

    assert (_tracked_paths(git_project, "tracked.txt"), list(hook_git_variables.iterdir())) == (
        ["tracked.txt"],
        [],
    )


def _missing_stack_lifecycle_paths(
    manifests_by_stack: Mapping[str, Sequence[Path]],
    post_helm_by_stack: Mapping[str, Sequence[Path]],
    k8s_dir: Path,
) -> list[str]:
    """Return stack:path entries missing from MANIFESTS_BY_STACK or POST_HELM_BY_STACK."""
    missing_manifests = [
        f"{stack_name}:{path}"
        for stack_name, paths in manifests_by_stack.items()
        for path in paths
        if not (path.exists() or (path.parent / f"{path.stem}.example{path.suffix}").exists())
    ]
    missing_post_helm = [
        f"{stack_name}:{k8s_dir / path}"
        for stack_name, paths in post_helm_by_stack.items()
        for path in paths
        if not (k8s_dir / path).exists()
    ]
    return [*missing_manifests, *missing_post_helm]


def test_manifests_by_stack_files_exist() -> None:
    """Every Kubernetes manifest or post-Helm path declared in stack_lifecycle must exist on disk."""
    from devops_cli.commands.k8s.stack_lifecycle import (
        DEFAULT_K8S_DIR,
        MANIFESTS_BY_STACK,
        POST_HELM_BY_STACK,
    )

    assert (
        _missing_stack_lifecycle_paths(MANIFESTS_BY_STACK, POST_HELM_BY_STACK, DEFAULT_K8S_DIR),
        _missing_stack_lifecycle_paths(
            {},
            {"llm": (Path("llm", "gateway", "nonexistent-monitor.yaml"),)},
            DEFAULT_K8S_DIR,
        ),
    ) == (
        [],
        [f"llm:{DEFAULT_K8S_DIR / 'llm' / 'gateway' / 'nonexistent-monitor.yaml'}"],
    )


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


def _file_data_path_violations(
    py_file: Path, repo_root: Path, tree: ast.Module | None = None
) -> list[str]:
    rel_posix = py_file.relative_to(repo_root).as_posix()
    if rel_posix == "src/devops_cli/config/defaults.py":
        return []
    parsed = tree or parse_python_file(py_file)
    return [
        violation
        for node in ast.walk(parsed)
        if (violation := _inspect_data_path_node(node, rel_posix)) is not None
    ]


def test_no_direct_data_dir_path_construction_in_src(
    parsed_source_trees: dict[Path, ast.Module],
) -> None:
    """An invariant test fails on any Path built from a .data literal or from DEFAULT_DATA_DIR
    in src/ outside config/defaults.py that does not go through the helper (#1036).
    """
    src_root = REPO_ROOT / "src"
    violations = [
        v
        for py_file in sorted(src_root.rglob("*.py"))
        for v in _file_data_path_violations(
            py_file, REPO_ROOT, tree=parsed_source_trees.get(py_file)
        )
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


_DIRECT_START_FUNCTIONS = frozenset({"run", "Popen", "check_output", "check_call", "call"})


def _starts_git(node: ast.Call) -> bool:
    """Whether the call is a direct start of a program (`subprocess.run` and the like) whose
    argument list begins with `git` or `CONST_GIT_CLI`."""
    func = node.func
    if not (
        isinstance(func, ast.Attribute)
        and func.attr in _DIRECT_START_FUNCTIONS
        and isinstance(func.value, ast.Name)
        and func.value.id == "subprocess"
        and node.args
        and isinstance(node.args[0], ast.List | ast.Tuple)
        and node.args[0].elts
    ):
        return False
    first = node.args[0].elts[0]
    return (isinstance(first, ast.Constant) and first.value == "git") or (
        isinstance(first, ast.Name) and first.id == "CONST_GIT_CLI"
    )


def _git_seam_offenders(trees: Mapping[Path, ast.Module], src: Path) -> list[str]:
    """Each `file:line` of `src` that imports GitPython or starts git by a way other than the
    process runner."""
    offenders: list[str] = []
    for path, tree in sorted(trees.items()):
        rel = path.relative_to(src).as_posix()
        for node in ast.walk(tree):
            line = getattr(node, "lineno", 0)
            if isinstance(node, ast.Import) and any(
                alias.name.split(".")[0] == "git" for alias in node.names
            ):
                offenders.append(f"{rel}:{line} imports GitPython")
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and (node.module or "").split(".")[0] == "git"
            ):
                offenders.append(f"{rel}:{line} imports GitPython")
            elif isinstance(node, ast.Call) and _starts_git(node):
                offenders.append(f"{rel}:{line} starts git outside the process runner")
    return offenders


def test_every_start_of_git_goes_through_the_process_runner(
    parsed_source_trees: dict[Path, ast.Module],
) -> None:
    """No module of `src/` imports GitPython, which starts git through its own `Popen`, or starts
    git with `subprocess` directly. The process runner is the one seam of git, so the git fake sees
    every start (#2146)."""
    src = REPO_ROOT / "src" / "devops_cli"

    assert _git_seam_offenders(parsed_source_trees, src) == []


def test_the_git_seam_check_names_a_gitpython_import_and_a_direct_start(tmp_path: Path) -> None:
    """The check reports `import git`, `from git import`, and a `subprocess` call whose argument
    list begins with git, and not a runner call or a module of devops-cli named git."""
    sources = {
        "a.py": "import git\n",
        "b.py": "from git.exc import GitError\n",
        "c.py": "import subprocess\nsubprocess.run(['git', 'status'])\n",
        "d.py": "import subprocess\nsubprocess.Popen([CONST_GIT_CLI, 'log'])\n",
        "e.py": "from devops_cli.git import operations\nrun_subprocess(['git', 'status'])\n",
        "f.py": "import subprocess\nsubprocess.run(['ls'])\n",
    }
    trees = {tmp_path / name: ast.parse(text) for name, text in sources.items()}

    assert _git_seam_offenders(trees, tmp_path) == [
        "a.py:1 imports GitPython",
        "b.py:1 imports GitPython",
        "c.py:2 starts git outside the process runner",
        "d.py:2 starts git outside the process runner",
    ]


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
    """Extract one ast-grep-ignore kind per rule id that a comment token lists (#1902)."""
    return [
        f"{tree_name} {CONST_SUPPRESSION_KIND_AST_GREP_IGNORE}"
        for match in CONST_AST_GREP_IGNORE_COMMENT_RE.finditer(comment)
        for rule_id in (match.group("ids") or "").split(CONST_AST_GREP_RULE_ID_SEPARATOR)
        if rule_id.strip()
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


_GIT_TIMEOUT_SECONDS = 60
# The suffixes Ruff lints under the scanned roots and `_collect_suppressions` does not read.
_UNSCANNED_RUFF_SUFFIXES = CONST_RUFF_SOURCE_SUFFIXES - {CONST_PYTHON_FILE_SUFFIX}


def _unscanned_tracked_sources(project: Path) -> list[str]:
    """List each tracked file under the scanned roots that Ruff lints and `_collect_suppressions` skips."""
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", *CONST_COMPLEXITY_CAP_ROOTS],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
        timeout=_GIT_TIMEOUT_SECONDS,
    ).stdout.split("\0")
    return [name for name in tracked if Path(name).suffix in _UNSCANNED_RUFF_SUFFIXES]


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
                "with a reason recorded in the proposal of the change "
                "(openspec/changes/<issue>-<slug>/proposal.md)."
            )
    return breaches


def _bare_nosec_markers(project: Path) -> list[str]:
    """Each `# nosec` comment under `src` that does not name its rules and a reason, as
    `<path>:<line>`."""
    bare: list[str] = []
    for py_file in sorted((project / CONST_SOURCE_ROOT_DIR).rglob("*.py")):
        text = py_file.read_text(encoding="utf-8")
        if "nosec" not in text:
            continue
        bare += [
            f"{py_file.relative_to(project).as_posix()}:{tok.start[0]}"
            for tok in tokenize.generate_tokens(io.StringIO(text).readline)
            if tok.type == tokenize.COMMENT
            and CONST_NOSEC_COMMENT_RE.search(tok.string)
            and not CONST_NOSEC_WITH_REASON_RE.search(tok.string)
        ]
    return bare


def test_every_nosec_in_src_names_its_rules_and_a_reason() -> None:
    """A reviewed Bandit finding in the product says which rules it silences and why (#1538)."""
    assert _bare_nosec_markers(REPO_ROOT) == []


@pytest.mark.parametrize(
    ("line", "reported"),
    [
        ('x = "a"  # nosec\n', True),
        ('x = "a"  # nosec B105\n', True),
        ('x = "a"  # nosec B105 # a label, not a credential\n', False),
        ('x = "a"  # nosec B105, B106 # a label, not a credential\n', False),
    ],
)
def test_the_nosec_check_reports_a_marker_without_its_rules_and_a_reason(
    tmp_path: Path, line: str, reported: bool
) -> None:
    (tmp_path / CONST_SOURCE_ROOT_DIR).mkdir()
    (tmp_path / CONST_SOURCE_ROOT_DIR / "mod.py").write_text(line, encoding="utf-8")
    assert bool(_bare_nosec_markers(tmp_path)) is reported


def test_suppressions_stay_under_their_ceilings() -> None:
    """Suppression comments in src/ and tests/ and waivers in pyproject.toml may not exceed ceilings (#849)."""
    assert (
        len(CONST_SUPPRESSION_KINDS),
        DEFAULT_SUPPRESSION_CEILINGS["src noqa: C901"],
        DEFAULT_SUPPRESSION_CEILINGS["src ast-grep-ignore"],
        DEFAULT_SUPPRESSION_CEILINGS["tests ast-grep-ignore"],
    ) == (
        10,
        DEFAULT_C901_SUPPRESSION_CEILING,
        DEFAULT_AST_GREP_SUPPRESSION_CEILING,
        DEFAULT_AST_GREP_SUPPRESSION_CEILING,
    )
    breaches = _suppression_ceiling_breaches(REPO_ROOT)
    assert breaches == [], "\n".join(breaches)


def test_no_tracked_file_under_the_scanned_roots_is_one_the_suppression_scan_skips() -> None:
    """The scan reads `*.py` only, so a tracked stub or notebook under `src` or `tests` forces a decision.

    Ruff lints `.pyi` and `.ipynb` files as well, and the counter that this scan replaced read the
    raw text of all three suffixes. None is tracked, so the scan misses no comment. The first one
    that is added must come with a count of its comments over its raw text, since a notebook is
    JSON and `tokenize` cannot read it.
    """
    assert _unscanned_tracked_sources(REPO_ROOT) == []


def test_a_tracked_stub_or_notebook_under_a_scanned_root_is_named(git_project: Path) -> None:
    """A stub or notebook tracked under `src` or `tests` is named, and a module or a docs file is not."""
    names = ("src/api.pyi", "tests/analysis.ipynb", "src/mod.py", "docs/demo.ipynb")
    for name in names:
        (git_project / name).parent.mkdir(parents=True, exist_ok=True)
        (git_project / name).write_text("", encoding="utf-8")
    _git_output(git_project, "add", "-f", "--", *names)

    assert _unscanned_tracked_sources(git_project) == ["src/api.pyi", "tests/analysis.ipynb"]


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
        "proposal of the change" in breaches[0],
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
    (tmp_path / "tests" / "test_mod.py").write_text(
        "f = 6  # ast-grep-ignore: test-elapsed-upper-bound\n", encoding="utf-8"
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
        "tests ast-grep-ignore": {"tests/test_mod.py": 1},
        "per-file-ignores": {"pyproject.toml": 2},
        "[[tool.mypy.overrides]]": {"pyproject.toml": 2},
        "coverage omit": {"pyproject.toml": 1},
    }


_C901_MARKER_SPELLINGS = {
    "marker-after-a-form-feed": f"#{_FORM_FEED}{_C901_MARKER[2:]}",
    "marker-after-a-no-break-space": f"#{_NO_BREAK_SPACE}{_C901_MARKER[2:]}",
    "marker-after-an-em-space": _C901_MARKER.replace(": ", f":{_EM_SPACE}"),
    "marker-after-a-spaced-colon": _C901_MARKER.replace(": ", " : E501 "),
}
_RUFF_DIRECTIVE_SPELLINGS = {
    "ruff-file-noqa": _RUFF_FILE_NOQA,
    "ruff-file-noqa-naming-c901": f"{_RUFF_FILE_NOQA}: C901",
    "flake8-file-noqa": _FLAKE8_FILE_NOQA,
    "file-noqa-after-a-form-feed": f"#{_FORM_FEED}{_RUFF_FILE_NOQA[2:]}: C901",
    "flake8-noqa-after-a-no-break-space": f"#{_NO_BREAK_SPACE}{_FLAKE8_FILE_NOQA[2:]}",
    "ruff-ignore": f"{_RUFF_COMMENT}ignore[C901]",
    "ruff-disable": f"{_RUFF_COMMENT}disable[C901]",
    "ruff-disable-unspaced": "#" + "ruff:" + "disable[E501,C901]",
    "ruff-file-ignore": f"{_RUFF_COMMENT}file-ignore[C901]",
    "ruff-disable-after-em-spaces": f"#{_EM_SPACE}{_RUFF_COMMENT[2:]}{_EM_SPACE}disable[ C901 ]",
}


@pytest.mark.parametrize(
    ("source", "kind"),
    [
        pytest.param(f"def f(x):  {marker}\n    return x\n", "src noqa: C901", id=name)
        for name, marker in _C901_MARKER_SPELLINGS.items()
    ]
    + [
        pytest.param(f"{line}\ndef f(x):\n    return x\n", "src file-level directive", id=name)
        for name, line in _RUFF_DIRECTIVE_SPELLINGS.items()
    ],
)
def test_every_ruff_suppression_spelling_is_counted(tmp_path: Path, source: str, kind: str) -> None:
    """Ruff reads any whitespace but a newline inside its suppression comments, so each spelling counts.

    The C901 marker counts under its own kind. The comments that hide C901 from a whole file or a
    block, in Ruff's or flake8's spelling, count under the file-level directive kind, whose
    ceiling is 0, so none enters the tree.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mod.py").write_text(source, encoding="utf-8")

    assert _collect_suppressions(tmp_path, pyproject={})[kind] == {"src/mod.py": 1}


def test_every_source_file_is_parsed_at_most_once(
    parsed_source_trees: dict[Path, ast.Module],
) -> None:
    """Each file under `src/` is parsed at most once per test process (#1749)."""
    multiple_parses = [
        f"{path.name}: parsed {parse_count(path)} times"
        for path in parsed_source_trees
        if parse_count(path) > 1
    ]
    assert multiple_parses == []
