"""Test-first specification for architectural and stylistic invariants in devops-cli."""

from __future__ import annotations

import ast
import importlib.util
import io
import re
import subprocess
import tokenize
import tomllib
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from graphlib import CycleError
from pathlib import Path, PurePosixPath
from typing import Any, Final

import pathspec
import pytest

from devops_cli.config.constants import (
    CONST_AST_GREP_SCAN_ARGS,
    CONST_CONFTEST_FILENAME,
    CONST_DOCS_CLASS_HAND_WRITTEN,
    CONST_DOCS_INVENTORY,
    CONST_GITIGNORE_FILENAME,
    CONST_GITIGNORE_PATTERN_STYLE,
    CONST_PRESENCE_CHECK_NAMES,
    CONST_PYTHON_FILE_SUFFIX,
    CONST_SOURCE_ROOT_DIR,
    CONST_TEST_FILE_PREFIX,
    CONST_TESTS_ROOT_DIR,
)
from devops_cli.core.import_graph import (
    build_import_graph,
    import_cycle_violations,
    interface_layer_violations,
    is_type_checking_guard,
    module_name,
    verify_acyclic_imports,
)
from devops_cli.core.repo import list_repo_files
from devops_cli.exceptions.base import DevOpsCLIError
from tests.support.paths import FIXTURES, GOLDEN, REPO_ROOT, TESTS_ROOT
from tests.support.trees import (
    parse_count,
    parse_python_file,
    parse_source_trees,
)

CONST_BLIND_EXCEPTION_TYPES: Final[frozenset[str]] = frozenset({"Exception", "BaseException"})
CONST_TEST_ASSERTION_LINT_RULES: Final[frozenset[str]] = frozenset(
    {"B011", "B015", "B017", "B018", "PT011", "PT015", "PT017", "PT018", "RUF043"}
)
CONST_SUPPRESSION_LINT_RULES: Final[frozenset[str]] = frozenset({"PGH003", "RUF100"})
CONST_RUFF_PER_FILE_IGNORE_KEYS: Final[tuple[str, ...]] = (
    "per-file-ignores",
    "extend-per-file-ignores",
)
CONST_COMPLEXITY_CAP_ROOTS: Final[tuple[str, ...]] = ("src", "tests")
CONST_RUFF_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi", ".ipynb"})
CONST_RUFF_IGNORE_FILE_NAMES: Final[frozenset[str]] = frozenset(
    {CONST_GITIGNORE_FILENAME, ".ignore"}
)
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
CONST_AST_GREP_SCAN_ROOTS: Final[tuple[str, ...]] = ("src", "tests")
CONST_NET_CONSTRUCT_RULES: Final[tuple[str, ...]] = (
    "net-address-list",
    "net-bracket-affix",
    "net-cidr-build",
    "net-domain-list",
    "net-domain-suffix",
    "net-hostport",
    "net-ip-literal",
    "net-localhost-fallback",
    "net-normalise",
    "net-port-table",
    "net-pre-flight-resolve",
    "net-raw-http-client",
    "net-scheme-affix",
    "net-scheme-in",
    "net-url-build",
)
CONST_TEST_CONSTRUCT_RULES: Final[tuple[str, ...]] = (
    "test-elapsed-upper-bound",
    "test-function-has-assertion",
    "test-pytest-raises-checks-error",
)
# The review and scanner packages, which take the working directory from the command layer (#2098).
CONST_REVIEW_CWD_READ_FILES: Final[tuple[str, ...]] = (
    "src/devops_cli/ai/review/**",
    "src/devops_cli/review/**",
    "src/devops_cli/security/**",
)
CONST_AST_GREP_RULE_FILES: Final[dict[str, tuple[str, ...]]] = {
    **dict.fromkeys(CONST_NET_CONSTRUCT_RULES, ("src/**",)),
    **dict.fromkeys(CONST_TEST_CONSTRUCT_RULES, ("tests/**",)),
    "review-cwd-read": CONST_REVIEW_CWD_READ_FILES,
}
CONST_BANNED_HAND_ROLLED_APIS: Final[tuple[str, ...]] = (
    "socket.inet_aton",
    "socket.inet_ntoa",
    "socket.inet_pton",
    "socket.inet_ntop",
)

DEFAULT_C901_SUPPRESSION_CEILING: int = 25
DEFAULT_AST_GREP_SUPPRESSION_CEILING: int = 0
DEFAULT_SUPPRESSION_CEILINGS: dict[str, int] = {
    "src type: ignore": 51,
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


def test_test_model_pytest_collection_disabled() -> None:
    """Ensure TestModel in testing.py disables Pytest collection to avoid PytestCollectionWarning."""
    from devops_cli.ai.agents.testing import TestModel

    assert getattr(TestModel, "__test__", None) is False


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
    hand_written = CONST_DOCS_INVENTORY[CONST_DOCS_CLASS_HAND_WRITTEN]
    paths = [PurePosixPath(path.relative_to(root).as_posix()) for path in list_repo_files(root)]
    scanned = [
        path
        for path in paths
        if path.parts[0] in _TASK_FILES_SCAN_ROOTS
        or any(path.full_match(glob) for glob in hand_written)
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


def _binds_names_only(node: ast.stmt, *, in_class: bool) -> bool:
    """Whether a statement of a module or class body does nothing on import but bind names: a
    docstring, a def, an assignment to names alone, an `if TYPE_CHECKING:` block with no `else`,
    an import at the top level, and `pass` in a class body. A class is checked by its body."""
    match node:
        case ast.Expr(value=ast.Constant(value=str())):
            return True
        case ast.Import() | ast.ImportFrom():
            return not in_class
        case ast.Pass():
            return in_class
        case ast.FunctionDef() | ast.AsyncFunctionDef():
            return True
        case ast.Assign(targets=targets):
            return all(isinstance(target, ast.Name) for target in targets)
        case ast.AnnAssign(target=ast.Name()):
            return True
        case ast.If(test=test, orelse=[]):
            return is_type_checking_guard(test)
    return False


def _acting_statements(body: list[ast.stmt], *, in_class: bool = False) -> Iterator[ast.stmt]:
    """Each statement of a module or class body, nested class bodies included, that does more on
    import than bind names."""
    for node in body:
        if isinstance(node, ast.ClassDef):
            yield from _acting_statements(node.body, in_class=True)
        elif not _binds_names_only(node, in_class=in_class):
            yield node


def _helper_modules(tests_root: Path) -> list[Path]:
    """Every Python file under the tests root that is neither a test module nor a conftest."""
    return sorted(
        path
        for path in tests_root.rglob("*.py")
        if not path.name.startswith(CONST_TEST_FILE_PREFIX) and path.name != CONST_CONFTEST_FILENAME
    )


def _acting_on_import(root: Path, trees: Mapping[Path, ast.Module] | None = None) -> list[str]:
    """`path:line` of each statement of a helper module under `root`'s tests root, at its top
    level or in a class body, that does more on import than bind names."""
    return [
        f"{path.relative_to(root).as_posix()}:{node.lineno}"
        for path in _helper_modules(root / CONST_TESTS_ROOT_DIR)
        for node in _acting_statements(
            (trees[path] if trees and path in trees else parse_python_file(path)).body
        )
    ]


def test_no_helper_module_under_tests_acts_on_import(
    parsed_test_trees: dict[Path, ast.Module],
) -> None:
    """Registration imports every support module into every run, and any helper runs on import
    for whichever test imports it first, so the top level of a helper under `tests/`, and each
    class body in it, holds only docstrings, imports at the top level, defs, classes,
    assignments to names alone and `if TYPE_CHECKING:` blocks with no `else`; the test selector
    then reaches every test such a change can (#1312). What still runs on import unchecked is
    each value bound to a name, each decorator, default argument, base class and metaclass, and
    only the full gate catches what those do to tests that do not import the helper."""
    assert _acting_on_import(REPO_ROOT, trees=parsed_test_trees) == []


_BINDS_NAMES_ONLY = (
    '"""A helper."""\n\nimport os\nfrom typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n'
    "    import sys\n\nVALUE = 1\nCOUNT: int = 2\n"
    '"""The count."""\n\n\ndef read() -> int:\n    return VALUE\n\n\n'
    "async def wait() -> None:\n    pass\n\n\nclass Holder:\n    pass\n\n\n"
    'class Settings:\n    """Settings."""\n\n    LIMIT = 3\n    name: str = "x"\n\n'
    "    if TYPE_CHECKING:\n        size: int\n\n    def read(self) -> int:\n"
    "        return self.LIMIT\n\n    class Inner:\n        pass\n"
)
# Each form that acts on import, with the line within it that the check names.
_ACTS_ON_IMPORT = (
    ("os.getcwd()\n", 0),
    ("os.environ['HOME'] = '/'\n", 0),
    ("os.sep = '/'\n", 0),
    ("VALUE += 1\n", 0),
    ("with open('x'):\n    pass\n", 0),
    ("for item in ():\n    pass\n", 0),
    ("while False:\n    pass\n", 0),
    ("try:\n    pass\nexcept OSError:\n    pass\n", 0),
    ("match VALUE:\n    case _:\n        pass\n", 0),
    ("if VALUE:\n    pass\n", 0),
    ("if TYPE_CHECKING:\n    pass\nelse:\n    pass\n", 0),
    ("del VALUE\n", 0),
    ("global VALUE\n", 0),
    ("FIRST, SECOND = 1, 2\n", 0),
    ("class Patched:\n    LIMIT = 1\n    os.sep = '/'\n", 2),
    ("class Imports:\n    import json\n", 1),
    ("class Nested:\n    class Inner:\n        os.getcwd()\n", 2),
)


def test_a_helper_statement_that_acts_on_import_is_named_with_path_and_line(
    tmp_path: Path,
) -> None:
    """Each form that acts on import, at the top level or in a class body, is reported as
    `path:line` in a helper module, and neither the forms that only bind names nor a test
    module or conftest are (#1312)."""
    start = _BINDS_NAMES_ONLY.count("\n") + 1
    lines = [
        start + sum(form.count("\n") for form, _ in _ACTS_ON_IMPORT[:index]) + offset
        for index, (_, offset) in enumerate(_ACTS_ON_IMPORT)
    ]
    tests_root = tmp_path / CONST_TESTS_ROOT_DIR
    (tests_root / "support").mkdir(parents=True)
    (tests_root / "support" / "helper.py").write_text(
        _BINDS_NAMES_ONLY + "".join(form for form, _ in _ACTS_ON_IMPORT), encoding="utf-8"
    )
    for exempt in ("test_helper.py", CONST_CONFTEST_FILENAME):
        (tests_root / exempt).write_text("import os\n\nos.getcwd()\n", encoding="utf-8")
    assert _acting_on_import(tmp_path) == [f"tests/support/helper.py:{line}" for line in lines]


_SUPPORT_PACKAGE = "tests.support"
_SUPPORT_DIR = Path(*_SUPPORT_PACKAGE.split("."))
# The calls that import a module named by a string, which no import statement shows.
_DYNAMIC_IMPORTS = ("import_module", "__import__")


def _support_packages(root: Path) -> frozenset[str]:
    """`tests.support` and every package under it, by dotted name, from their `__init__.py`."""
    return frozenset(
        module_name(init.relative_to(root), Path())
        for init in (root / _SUPPORT_DIR).rglob("__init__.py")
    )


def _tests_aliases(tree: ast.Module) -> dict[str, str]:
    """Each name an `import` binds to a module of the tests package, with that module's dotted
    name: `import tests.x` and `import tests` bind `tests`, and `import tests.x as y` binds `y`
    to `tests.x`."""
    tests_package = _SUPPORT_PACKAGE.partition(".")[0]
    return {
        alias.asname or tests_package: alias.name if alias.asname else tests_package
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name.partition(".")[0] == tests_package
    }


def _imports_dynamically(func: ast.expr) -> bool:
    """Whether a call imports the module a string names: `importlib.import_module` or
    `__import__`."""
    match func:
        case ast.Attribute(attr=name) | ast.Name(id=name):
            return name in _DYNAMIC_IMPORTS
    return False


def _holds_a_support_package(
    node: ast.AST, package: str, packages: frozenset[str], aliases: dict[str, str]
) -> bool:
    """Whether a node gets hold of `tests.support` or a package under it, through which a module
    could read a module that registration loaded without importing it: by importing the package,
    by reaching it as an attribute of a name bound to the tests package, or by a dynamic import
    of anything under `tests.support`."""
    match node:
        case ast.ImportFrom(module=module, level=level, names=names):
            try:
                base = importlib.util.resolve_name("." * level + (module or ""), package)
            except ImportError, ValueError:
                return False
            return any(f"{base}.{alias.name}" in packages for alias in names)
        case ast.Import(names=names):
            return any(alias.name in packages for alias in names)
        case ast.Attribute(value=ast.Name(id=name), attr=attr):
            return name in aliases and f"{aliases[name]}.{attr}" in packages
        case ast.Call(func=func, args=[ast.Constant(value=str(target)), *_]):
            return _imports_dynamically(func) and target.startswith(_SUPPORT_PACKAGE)
    return False


def _support_package_imports(
    root: Path, exempt: Path, trees: Mapping[Path, ast.Module] | None = None
) -> list[str]:
    """`path:line` of each module under `root`'s tests root, but `exempt`, that gets hold of a
    support package; a module outside `tests/support/` is parsed only if it spells `support`,
    which every such form outside it needs."""
    packages = _support_packages(root)
    found: list[str] = []
    for path in sorted((root / CONST_TESTS_ROOT_DIR).rglob("*.py")):
        relative = path.relative_to(root)
        text = path.read_text(encoding="utf-8")
        spelled = _SUPPORT_DIR.name in text or relative.is_relative_to(_SUPPORT_DIR)
        if relative == exempt or not spelled:
            continue
        tree = trees[path] if trees and path in trees else parse_python_file(path)
        package = ".".join(relative.parent.parts)
        aliases = _tests_aliases(tree)
        found.extend(
            f"{relative.as_posix()}:{node.lineno}"
            for node in ast.walk(tree)
            if _holds_a_support_package(node, package, packages, aliases)
        )
    return sorted(found)


_BOOTSTRAP = Path(CONST_TESTS_ROOT_DIR, "support", "bootstrap.py")


def test_only_bootstrap_imports_the_support_package_itself(
    parsed_test_trees: dict[Path, ast.Module],
) -> None:
    """Registration loads every support module, so a module holding the `tests.support` package,
    or a package under it, could read one through it with no import of its own, which the test
    selector would not see. A module imports from a support module with `from tests.support[.x]
    import ...`, and only `bootstrap`, which registers them, holds a package (#1312)."""
    assert _support_package_imports(REPO_ROOT, _BOOTSTRAP, trees=parsed_test_trees) == []


def test_a_module_that_names_the_support_package_is_named_with_path_and_line(
    tmp_path: Path,
) -> None:
    """Each way to hold `tests.support` or a package under it is reported as `path:line`:
    `from tests import support`, `import tests.support`, a relative import, `support` reached
    as an attribute of `tests` under any name, a subpackage imported by name, and a dynamic
    import by `importlib.import_module` or `__import__`. An import from a support module, and
    `bootstrap`, are not (#1312)."""
    files = {
        "tests/__init__.py": "",
        "tests/support/__init__.py": "",
        "tests/support/fakes/__init__.py": "",
        "tests/support/bootstrap.py": "from tests import support\n",
        "tests/support/builders.py": "from . import fakes\n",
        "tests/test_a.py": "from tests import support\n",
        "tests/test_b.py": "import tests.support\n",
        "tests/test_c.py": "import tests\n\nFIXTURES = tests.support.paths.FIXTURES\n",
        "tests/ai/test_d.py": "from .. import support\n",
        "tests/test_alias.py": "import tests as t\n\nFIXTURES = t.support.paths.FIXTURES\n",
        "tests/test_dotted.py": (
            "import tests.support.paths\n\nFIXTURES = tests.support.paths.FIXTURES\n"
        ),
        "tests/test_fakes.py": "from tests.support import fakes\n\nSESSION = fakes.github\n",
        "tests/test_import_module.py": (
            "import importlib\n\nPATHS = importlib.import_module('tests.support.paths')\n"
        ),
        "tests/test_dunder.py": "PATHS = __import__('tests.support.paths')\n",
        "tests/test_ok.py": (
            "import tests\nfrom tests.support import paths\n"
            "from tests.support.paths import FIXTURES\n\nROOT = tests.__file__\n"
        ),
    }
    for relative, text in files.items():
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text(text, encoding="utf-8")
    assert _support_package_imports(tmp_path, _BOOTSTRAP) == [
        "tests/ai/test_d.py:1",
        "tests/support/builders.py:1",
        "tests/test_a.py:1",
        "tests/test_alias.py:3",
        "tests/test_b.py:1",
        "tests/test_c.py:3",
        "tests/test_dotted.py:3",
        "tests/test_dunder.py:1",
        "tests/test_fakes.py:1",
        "tests/test_import_module.py:3",
    ]


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
        job_ifs.get("Tests & Coverage") in (None, "github.event_name != 'schedule'"),
    ) == (
        ACTIONS_WRITE_ALLOWLIST,
        True,
        True,
        True,
    )


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


def _blind_exception_assertions(
    tests_dir: Path, trees: Mapping[Path, ast.Module] | None = None
) -> list[str]:
    """Report every `file:line` in the suite that expects a root exception type."""
    sites: list[str] = []
    for path in sorted(tests_dir.rglob("test_*.py")):
        tree = trees[path] if trees and path in trees else parse_python_file(path)
        sites.extend(
            f"{path.name}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _expected_exception_name(node) in CONST_BLIND_EXCEPTION_TYPES
        )
    return sites


def _is_bool_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, bool)


def _is_presence_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Name):
        return node.func.id in CONST_PRESENCE_CHECK_NAMES
    if isinstance(node.func, ast.Attribute):
        return node.func.attr in CONST_PRESENCE_CHECK_NAMES
    return False


def _is_opaque_tuple_assert(node: ast.Assert) -> bool:
    if not isinstance(node.test, ast.Compare):
        return False
    cmp = node.test
    if len(cmp.ops) != 1 or not isinstance(cmp.ops[0], ast.Eq):
        return False
    left, right = cmp.left, cmp.comparators[0]
    if isinstance(left, (ast.Tuple, ast.List)) and isinstance(right, (ast.Tuple, ast.List)):
        for el_l, el_r in zip(left.elts, right.elts, strict=False):
            for el, other in [(el_l, el_r), (el_r, el_l)]:
                if _is_presence_call(el) and _is_bool_literal(other):
                    return True
    return False


def _is_none_comparison(test: ast.Compare) -> bool:
    if len(test.ops) != 1 or not isinstance(test.ops[0], (ast.IsNot, ast.NotEq)):
        return False
    left, right = test.left, test.comparators[0]
    return (isinstance(right, ast.Constant) and right.value is None) or (
        isinstance(left, ast.Constant) and left.value is None
    )


def _is_presence_bool_comparison(test: ast.Compare) -> bool:
    if len(test.ops) != 1:
        return False
    left, right = test.left, test.comparators[0]
    for el, other in [(left, right), (right, left)]:
        if _is_presence_call(el) and _is_bool_literal(other):
            return True
    return False


def _is_presence_pair(elt_a: ast.expr, elt_b: ast.expr) -> bool:
    for el, other in [(elt_a, elt_b), (elt_b, elt_a)]:
        if _is_presence_call(el) and _is_bool_literal(other):
            return True
        if isinstance(el, ast.Compare) and _is_none_comparison(el) and _is_bool_literal(other):
            return True
    return False


def _is_all_presence_tuple_comparison(test: ast.Compare) -> bool:
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    left, right = test.left, test.comparators[0]
    if not (isinstance(left, (ast.Tuple, ast.List)) and isinstance(right, (ast.Tuple, ast.List))):
        return False
    if len(left.elts) == 0 or len(left.elts) != len(right.elts):
        return False
    return all(
        _is_presence_pair(elt_a, elt_b) for elt_a, elt_b in zip(left.elts, right.elts, strict=False)
    )


def _is_presence_check(node: ast.Assert) -> bool:
    test = node.test
    if isinstance(test, ast.Compare):
        return (
            _is_none_comparison(test)
            or _is_presence_bool_comparison(test)
            or _is_all_presence_tuple_comparison(test)
        )
    return _is_presence_call(test) or isinstance(test, (ast.Name, ast.Attribute))


def _classify_test_node(
    item: ast.AST,
    test_funcs: list[ast.FunctionDef | ast.AsyncFunctionDef],
    same_module_helpers: set[str],
) -> None:
    if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return
    if item.name.startswith("test_"):
        test_funcs.append(item)
        return
    if any(isinstance(c, ast.Assert) for c in ast.walk(item)):
        same_module_helpers.add(item.name)


def _collect_test_funcs_and_helpers(
    tree: ast.Module,
) -> tuple[list[ast.FunctionDef | ast.AsyncFunctionDef], set[str]]:
    test_funcs: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    same_module_helpers: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                _classify_test_node(item, test_funcs, same_module_helpers)
        else:
            _classify_test_node(node, test_funcs, same_module_helpers)
    return test_funcs, same_module_helpers


def _scan_test_function(
    path_name: str,
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    same_module_helpers: set[str],
) -> list[str]:
    sites: list[str] = []
    fn_asserts: list[ast.Assert] = []
    delegates = False
    for c in ast.walk(fn):
        if isinstance(c, ast.Assert):
            fn_asserts.append(c)
        elif (
            not delegates
            and isinstance(c, ast.Call)
            and isinstance(c.func, ast.Name)
            and c.func.id in same_module_helpers
        ):
            delegates = True
    for a in fn_asserts:
        if _is_opaque_tuple_assert(a):
            sites.append(f"{path_name}:{a.lineno}")
    if fn_asserts and not delegates and all(_is_presence_check(a) for a in fn_asserts):
        for a in fn_asserts:
            sites.append(f"{path_name}:{a.lineno}")
    return sites


def _opaque_or_presence_assertions(
    tests_dir: Path, trees: Mapping[Path, ast.Module] | None = None
) -> list[str]:
    """Report every `file:line` of an opaque tuple assert or presence-only test in `tests/`."""
    sites: set[str] = set()
    test_paths = (
        [p for p in trees.keys() if p.name.startswith("test_") and p.name.endswith(".py")]
        if trees
        else sorted(tests_dir.rglob("test_*.py"))
    )
    for path in sorted(test_paths):
        tree = trees[path] if trees and path in trees else parse_python_file(path)
        test_funcs, helpers = _collect_test_funcs_and_helpers(tree)
        for fn in test_funcs:
            sites.update(_scan_test_function(path.name, fn, helpers))
    return sorted(sites, key=lambda s: (s.split(":")[0], int(s.split(":")[1])))


def test_no_test_certifies_a_failure_without_checking_it(
    parsed_test_trees: dict[Path, ast.Module],
) -> None:
    """A test must specify expected failures and test values or object identity.

    `pytest.raises(Exception)` is satisfied by an unrelated `TypeError`.
    A test whose assertions check only presence or hide presence calls in tuple equality
    certifies an object exists without verifying its values or behavior.
    Neither defect is visible in review.
    Ruff rules and AST invariant checks prevent these defects.
    """
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lint = config["tool"]["ruff"]["lint"]
    unenforced = sorted(
        rule
        for rule in CONST_TEST_ASSERTION_LINT_RULES
        if not _ruff_enforces(rule, lint["select"], lint.get("ignore", []))
    )

    assert (
        _blind_exception_assertions(REPO_ROOT / "tests", trees=parsed_test_trees),
        _opaque_or_presence_assertions(REPO_ROOT / "tests", trees=parsed_test_trees),
        unenforced,
    ) == ([], [], [])


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


def test_opaque_and_presence_assertions_fixtures(tmp_path: Path) -> None:
    """The presence and opaque tuple assert invariant reports file:line on acceptance fixtures."""
    code = (
        "def _helper_with_assert() -> None:\n"
        "    assert 1 == 1\n"
        "\n"
        "def test_only_is_not_none() -> None:\n"
        "    assert x is not None\n"
        "\n"
        "def test_only_bare_truthiness() -> None:\n"
        "    assert x\n"
        "\n"
        "def test_only_opaque_tuple() -> None:\n"
        "    assert (isinstance(x, Y),) == (True,)\n"
        "\n"
        "def test_delegates_to_helper() -> None:\n"
        "    _helper_with_assert()\n"
        "\n"
        "def test_does_not_raise() -> None:\n"
        "    pass\n"
        "\n"
        "def test_valid_checks() -> None:\n"
        "    assert x is not None\n"
        "    assert x.value == 42\n"
    )
    test_file = tmp_path / "test_fixtures.py"
    test_file.write_text(code, encoding="utf-8")
    violations = _opaque_or_presence_assertions(tmp_path)
    assert violations == [
        "test_fixtures.py:5",
        "test_fixtures.py:8",
        "test_fixtures.py:11",
    ]


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


def _names_rule(rule: str, code: str) -> bool:
    """Report whether one selector names a rule, by Ruff's prefix matching."""
    return code == "ALL" or rule.startswith(code)


def _ignore_file_escapes(
    project: Path, covered: Sequence[Path], sources: Sequence[Path]
) -> list[str]:
    """Report an ignore file that drops a covered source from the walk of the construct gate.

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


def _sgconfig_escapes(project: Path) -> list[str]:
    """Report unlisted keys, modified ruleDirs, or extra sgconfig.yml files (#1107)."""
    sgconfig = project / "sgconfig.yml"
    if not sgconfig.is_file():
        return ["sgconfig.yml: missing"]
    import yaml

    try:
        raw = yaml.safe_load(sgconfig.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return [f"[sgconfig.yml] malformed: {exc}"]
    unlisted = [
        f"[sgconfig.yml] {k}: outside the allowlist"
        for k in sorted(set(raw.keys()) - {"ruleDirs", "testConfigs"})
    ]
    rule_dirs = raw.get("ruleDirs")
    rule_dirs_escape = (
        []
        if rule_dirs == [".ast-grep/rules"]
        else [f"[sgconfig.yml] ruleDirs: {rule_dirs}, not ['.ast-grep/rules']"]
    )
    seconds = [
        f"{name}: a second sgconfig.yml"
        for name in sorted(
            _tracked_paths(project, ":(glob)**/sgconfig.yml", ":(exclude)sgconfig.yml")
        )
    ]
    return [*unlisted, *rule_dirs_escape, *seconds]


def _rule_file_escapes(data: dict[str, Any], rid: str) -> list[str]:
    """Check rule properties: severity must be error, files must name the tree the rule holds,
    and ignores may not be set (#1902)."""
    escapes: list[str] = []
    if data.get("severity") != "error":
        escapes.append(f"[{rid}] severity: {data.get('severity')}, not error")
    files = list(CONST_AST_GREP_RULE_FILES.get(rid, ()))
    if files and data.get("files") != files:
        escapes.append(f"[{rid}] files: {data.get('files')}, not {files}")
    if "ignores" in data:
        escapes.append(f"[{rid}] ignores: outside the allowlist")
    return escapes


def _read_rule_files(project: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Read rule definition YAML files from .ast-grep/rules/."""
    import yaml

    rules_dir = project / ".ast-grep" / "rules"
    rule_files = sorted(rules_dir.glob("*.yml")) if rules_dir.is_dir() else []
    rules: dict[str, dict[str, Any]] = {}
    rule_escapes: list[str] = []
    for rf in rule_files:
        try:
            data = yaml.safe_load(rf.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        rid = data.get("id")
        if isinstance(rid, str) and rid:
            rules[rid] = data
            rule_escapes.extend(_rule_file_escapes(data, rid))
    return rules, rule_escapes


def _read_test_files(project: Path) -> dict[str, dict[str, Any]]:
    """Read rule test YAML files from .ast-grep/rule-tests/."""
    import yaml

    tests_dir = project / ".ast-grep" / "rule-tests"
    test_files = sorted(tests_dir.glob("*.yml")) if tests_dir.is_dir() else []
    tests: dict[str, dict[str, Any]] = {}
    for tf in test_files:
        try:
            data = yaml.safe_load(tf.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        tid = data.get("id")
        if isinstance(tid, str) and tid:
            tests[tid] = data
    return tests


def _rule_test_case_escapes(tests: dict[str, dict[str, Any]]) -> list[str]:
    """Verify each ast-grep rule has at least one valid and one invalid case."""
    escapes: list[str] = []
    for rid in sorted(CONST_AST_GREP_RULE_FILES):
        tdata = tests.get(rid)
        if not tdata or not tdata.get("valid"):
            escapes.append(f"[{rid}] has no valid case")
        if not tdata or not tdata.get("invalid"):
            escapes.append(f"[{rid}] has no invalid case")
    return escapes


def _ast_grep_rules_and_tests_escapes(project: Path) -> list[str]:
    """Report missing or unlisted ast-grep rules, severity/filter escapes, or missing test cases."""
    rules, rule_escapes = _read_rule_files(project)
    found_ids = set(rules.keys())
    expected_ids = set(CONST_AST_GREP_RULE_FILES)
    id_escapes = [
        f"{rid}: missing from .ast-grep/rules" for rid in sorted(expected_ids - found_ids)
    ] + [f"[{rid}] outside CONST_AST_GREP_RULE_FILES" for rid in sorted(found_ids - expected_ids)]
    tests = _read_test_files(project)
    return [*id_escapes, *rule_escapes, *_rule_test_case_escapes(tests)]


def _pre_commit_scan_cmd_escapes(project: Path, expected_cmd: list[str]) -> list[str]:
    """Report whether the ast-grep-scan pre-commit hook runs the expected scan command."""
    import yaml

    pre_commit_file = project / ".pre-commit-config.yaml"
    if not pre_commit_file.is_file():
        return []
    try:
        cfg = yaml.safe_load(pre_commit_file.read_text(encoding="utf-8")) or {}
        hooks = [h for r in cfg.get("repos", []) for h in r.get("hooks", [])]
        scan_hook = next((h for h in hooks if h.get("id") == "ast-grep-scan"), None)
        if scan_hook is None:
            return ["ast-grep-scan hook: missing from .pre-commit-config.yaml"]
        entry = scan_hook.get("entry", "").split()
        args = scan_hook.get("args", [])
        cmd = [*entry, *args]
        if cmd != expected_cmd:
            return [f"ast-grep-scan hook cmd: {cmd}, not {expected_cmd}"]
    except Exception as exc:
        return [f"[.pre-commit-config.yaml] malformed: {exc}"]
    return []


def _scan_command_escapes(project: Path) -> list[str]:
    """Report scan commands differing from CONST_AST_GREP_SCAN_ARGS in CI or pre-commit."""
    expected_cmd = ["uv", "run", "ast-grep", *CONST_AST_GREP_SCAN_ARGS]
    from devops_cli.commands.ci import get_check_specs

    specs = {s.name: s for s in get_check_specs()}
    constructs_spec = specs.get("constructs")
    ci_escapes: list[str] = []
    if constructs_spec is None:
        ci_escapes.append("constructs row: missing from get_check_specs()")
    elif constructs_spec.cmd != expected_cmd:
        ci_escapes.append(f"constructs row cmd: {constructs_spec.cmd}, not {expected_cmd}")

    return [*ci_escapes, *_pre_commit_scan_cmd_escapes(project, expected_cmd)]


def _tid251_escapes(lint: Mapping[str, Any]) -> list[str]:
    """Report unenforced TID251, per-file waivers of TID251, or missing banned socket APIs."""
    select = [*lint.get("select", []), *lint.get("extend-select", [])]
    ignore = [*lint.get("ignore", []), *lint.get("extend-ignore", [])]
    rule = "TID251"
    escapes: list[str] = []
    if rule not in select or not _ruff_enforces(rule, select, ignore):
        escapes.append(f"{rule}: not enforced")

    for table in CONST_RUFF_PER_FILE_IGNORE_KEYS:
        for pattern, codes in lint.get(table, {}).items():
            if any(_names_rule(rule, code) for code in codes):
                escapes.append(f"[tool.ruff.lint.{table}] {pattern}: waives {rule}")

    banned = lint.get("flake8-tidy-imports", {}).get("banned-api", {})
    for api in sorted(CONST_BANNED_HAND_ROLLED_APIS):
        if api not in banned:
            escapes.append(f"{api}: missing from flake8-tidy-imports.banned-api")

    return escapes


def _construct_gate_escapes(pyproject: Mapping[str, Any], project: Path) -> list[str]:
    """Report every way a committed file lets a construct past the ast-grep gate (#1107, #1902)."""
    lint = pyproject.get("tool", {}).get("ruff", {}).get("lint", {})
    covered = [project / name for name in _tracked_paths(project, *CONST_AST_GREP_SCAN_ROOTS)]
    sources = [p for p in covered if p.suffix in CONST_RUFF_SOURCE_SUFFIXES]
    return [
        *_sgconfig_escapes(project),
        *_ast_grep_rules_and_tests_escapes(project),
        *_scan_command_escapes(project),
        *_ignore_file_escapes(project, covered, sources),
        *_tid251_escapes(lint),
    ]


# Built here so this file's own text holds no file-level exemption, no C901 marker and no
# Ruff suppression comment naming C901. Ruff honours each spelling below (checked on 0.16.8).
_RUFF_FILE_NOQA = "# " + "ruff" + ": noqa"
_FLAKE8_FILE_NOQA = "# " + "flake8" + ": noqa"
_C901_MARKER = "# " + "noqa: " + "C901"
_RUFF_COMMENT = "# " + "ruff" + ": "
_FORM_FEED, _NO_BREAK_SPACE, _EM_SPACE = "\x0c", "\xa0", "\u2003"


def _edit(table: dict[str, Any], path: Sequence[str], value: object) -> None:
    """Set the key a path names inside nested tables."""
    *parents, key = path
    for name in parents:
        table = table[name]
    table[key] = value


def _complying_construct_gate_pyproject() -> dict[str, Any]:
    """Build, as a fresh dict, a pyproject.toml the construct gate meta-test accepts."""
    lint = {
        "select": ["E", "TID251"],
        "ignore": [],
        "flake8-tidy-imports": {
            "banned-api": {
                api: {"msg": "Parse and format addresses with ipaddress.ip_address."}
                for api in sorted(CONST_BANNED_HAND_ROLLED_APIS)
            }
        },
    }
    return {"tool": {"ruff": {"lint": lint}}}


def _populate_complying_construct_gate_tree(project: Path) -> None:
    """Populate a tmp_path tree with files complying with the construct gate."""
    (project / "sgconfig.yml").write_text(
        "ruleDirs:\n  - .ast-grep/rules\ntestConfigs:\n  - testDir: .ast-grep/rule-tests\n",
        encoding="utf-8",
    )
    (project / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: ast-grep-scan\n"
        f"        entry: uv run ast-grep {' '.join(CONST_AST_GREP_SCAN_ARGS)}\n",
        encoding="utf-8",
    )
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (project / "tests").mkdir(parents=True, exist_ok=True)
    (project / "tests" / "test_app.py").write_text("x = 1\n", encoding="utf-8")
    (project / ".gitignore").write_text("target/\n", encoding="utf-8")

    rules_dir = project / ".ast-grep" / "rules"
    tests_dir = project / ".ast-grep" / "rule-tests"
    rules_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    for rid, files in CONST_AST_GREP_RULE_FILES.items():
        (rules_dir / f"{rid}.yml").write_text(
            f"id: {rid}\nlanguage: python\nseverity: error\nfiles: {list(files)}\nmessage: msg\n"
            "rule:\n  pattern: $X\n",
            encoding="utf-8",
        )
        (tests_dir / f"{rid}-test.yml").write_text(
            f"id: {rid}\nvalid:\n  - 'x = 1'\ninvalid:\n  - 'y = 2'\n",
            encoding="utf-8",
        )


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


_CONSTRUCT_GATE_ESCAPES = [
    pytest.param((), None, {}, [], id="complying"),
    pytest.param(
        (),
        None,
        {
            "sgconfig.yml": (
                "ruleDirs:\n  - .ast-grep/rules\ntestConfigs:\n  - testDir: .ast-grep/rule-tests\n"
                "extraKey: true\n"
            )
        },
        ["[sgconfig.yml] extraKey: outside the allowlist"],
        id="sgconfig-unlisted-key",
    ),
    pytest.param(
        (),
        None,
        {
            "sgconfig.yml": (
                "ruleDirs:\n  - .ast-grep/other\ntestConfigs:\n  - testDir: .ast-grep/rule-tests\n"
            )
        },
        ["[sgconfig.yml] ruleDirs: ['.ast-grep/other'], not ['.ast-grep/rules']"],
        id="sgconfig-ruledirs-modified",
    ),
    pytest.param(
        (),
        None,
        {
            "subdir/sgconfig.yml": "ruleDirs: []\n",
            "subdir/deeper/sgconfig.yml": "ruleDirs: []\n",
        },
        [
            "subdir/deeper/sgconfig.yml: a second sgconfig.yml",
            "subdir/sgconfig.yml: a second sgconfig.yml",
        ],
        id="second-sgconfig",
    ),
    pytest.param(
        (),
        None,
        {".ast-grep/rules/net-port-table.yml": None},
        ["net-port-table: missing from .ast-grep/rules"],
        id="rule-missing",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rules/net-custom.yml": (
                "id: net-custom\nlanguage: python\nseverity: error\nrule:\n  pattern: $X\n"
            )
        },
        ["[net-custom] outside CONST_AST_GREP_RULE_FILES"],
        id="rule-unlisted",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rules/net-port-table.yml": (
                "id: net-port-table\nlanguage: python\nseverity: warning\nfiles: ['src/**']\n"
                "rule:\n  pattern: $X\n"
            )
        },
        ["[net-port-table] severity: warning, not error"],
        id="rule-severity-not-error",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rules/net-port-table.yml": (
                "id: net-port-table\nlanguage: python\nseverity: error\nfiles: [src/ai/**]\n"
                "rule:\n  pattern: $X\n"
            )
        },
        ["[net-port-table] files: ['src/ai/**'], not ['src/**']"],
        id="rule-files-narrowed",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rules/net-port-table.yml": (
                "id: net-port-table\nlanguage: python\nseverity: error\nrule:\n  pattern: $X\n"
            )
        },
        ["[net-port-table] files: None, not ['src/**']"],
        id="rule-files-missing",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rules/test-elapsed-upper-bound.yml": (
                "id: test-elapsed-upper-bound\nlanguage: python\nseverity: error\n"
                "files: ['src/**']\nrule:\n  pattern: $X\n"
            )
        },
        ["[test-elapsed-upper-bound] files: ['src/**'], not ['tests/**']"],
        id="test-rule-files-moved",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rules/net-port-table.yml": (
                "id: net-port-table\nlanguage: python\nseverity: error\nfiles: ['src/**']\n"
                "ignores: [src]\nrule:\n  pattern: $X\n"
            )
        },
        ["[net-port-table] ignores: outside the allowlist"],
        id="rule-ignores-set",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rule-tests/net-port-table-test.yml": "id: net-port-table\ninvalid:\n  - 'x = 1'\n"
        },
        ["[net-port-table] has no valid case"],
        id="rule-no-valid-case",
    ),
    pytest.param(
        (),
        None,
        {
            ".ast-grep/rule-tests/net-port-table-test.yml": "id: net-port-table\nvalid:\n  - 'x = 1'\n"
        },
        ["[net-port-table] has no invalid case"],
        id="rule-no-invalid-case",
    ),
    pytest.param(
        (),
        None,
        {
            ".pre-commit-config.yaml": (
                "repos:\n  - repo: local\n    hooks:\n      - id: ast-grep-scan\n"
                "        entry: uv run ast-grep scan src\n"
            )
        },
        [
            f"ast-grep-scan hook cmd: ['uv', 'run', 'ast-grep', 'scan', 'src'], "
            f"not {['uv', 'run', 'ast-grep', *CONST_AST_GREP_SCAN_ARGS]}"
        ],
        id="precommit-scan-cmd-changed",
    ),
    pytest.param(
        (),
        None,
        {".pre-commit-config.yaml": "repos: []\n"},
        ["ast-grep-scan hook: missing from .pre-commit-config.yaml"],
        id="precommit-scan-hook-missing",
    ),
    pytest.param(
        (),
        None,
        {".gitignore": "src/app.py\n"},
        ["src/app.py: matched by .gitignore"],
        id="ignore-file-hides-source",
    ),
    pytest.param(
        (),
        None,
        {".gitignore": "tests/test_app.py\n"},
        ["tests/test_app.py: matched by .gitignore"],
        id="ignore-file-hides-a-test",
    ),
    pytest.param(
        ("lint", "select"),
        ["E"],
        {},
        ["TID251: not enforced"],
        id="tid251-unselected",
    ),
    pytest.param(
        ("lint", "ignore"),
        ["TID251"],
        {},
        ["TID251: not enforced"],
        id="tid251-ignored",
    ),
    pytest.param(
        ("lint", "per-file-ignores"),
        {"src/*": ["TID251"]},
        {},
        ["[tool.ruff.lint.per-file-ignores] src/*: waives TID251"],
        id="tid251-waived",
    ),
    pytest.param(
        ("lint", "flake8-tidy-imports", "banned-api"),
        {"socket.inet_ntoa": {"msg": "x"}},
        {},
        [
            "socket.inet_aton: missing from flake8-tidy-imports.banned-api",
            "socket.inet_ntop: missing from flake8-tidy-imports.banned-api",
            "socket.inet_pton: missing from flake8-tidy-imports.banned-api",
        ],
        id="banned-api-missing",
    ),
]


@pytest.mark.parametrize("path, value, files, expected", _CONSTRUCT_GATE_ESCAPES)
def test_every_construct_gate_escape_is_reported(
    git_project: Path,
    path: Sequence[str],
    value: object,
    files: Mapping[str, str | None],
    expected: list[str],
) -> None:
    """Every way to bypass the construct gate without detection is reported (#1107, #1902)."""
    _populate_complying_construct_gate_tree(git_project)
    pyproject = _complying_construct_gate_pyproject()
    if path:
        _edit(pyproject["tool"]["ruff"], path, value)
    for name, content in files.items():
        dest = git_project / name
        if content is None:
            if dest.exists():
                dest.unlink()
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
    _track_everything(git_project)

    assert _construct_gate_escapes(pyproject, git_project) == expected


def test_a_second_sgconfig_that_git_does_not_track_is_not_reported(git_project: Path) -> None:
    """Scratch under `.data` and a checkout nested under `.claude/worktrees` hold an `sgconfig.yml` no commit holds (#1787)."""
    _populate_complying_construct_gate_tree(git_project)
    _track_everything(git_project)
    _git_output(git_project, "commit", "--quiet", "--message", "tree")
    scratch = git_project / ".data" / "agent" / "scratch" / "astgrep" / "sgconfig.yml"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    scratch.write_text("ruleDirs: []\n", encoding="utf-8")
    _git_output(
        git_project, "worktree", "add", "--quiet", ".claude/worktrees/nested", "-b", "nested"
    )

    in_working_tree = sorted(
        found.relative_to(git_project).as_posix() for found in git_project.rglob("sgconfig.yml")
    )

    assert (in_working_tree, _sgconfig_escapes(git_project)) == (
        [
            ".claude/worktrees/nested/sgconfig.yml",
            ".data/agent/scratch/astgrep/sgconfig.yml",
            "sgconfig.yml",
        ],
        [],
    )


def test_a_tracked_second_sgconfig_is_named_beside_untracked_ones(git_project: Path) -> None:
    """Only the `sgconfig.yml` a commit would hold is reported; the untracked scratch beside it is not (#1787)."""
    _populate_complying_construct_gate_tree(git_project)
    for tracked in ("subdir/sgconfig.yml", "subdir/deeper/sgconfig.yml"):
        (git_project / tracked).parent.mkdir(parents=True, exist_ok=True)
        (git_project / tracked).write_text("ruleDirs: []\n", encoding="utf-8")
    _track_everything(git_project)
    scratch = git_project / ".data" / "sgconfig.yml"
    scratch.parent.mkdir(exist_ok=True)
    scratch.write_text("ruleDirs: []\n", encoding="utf-8")

    assert _sgconfig_escapes(git_project) == [
        "subdir/deeper/sgconfig.yml: a second sgconfig.yml",
        "subdir/sgconfig.yml: a second sgconfig.yml",
    ]


def test_a_source_that_git_does_not_track_is_not_reported_as_hidden(git_project: Path) -> None:
    """A source file `.gitignore` matches but no commit holds hides nothing from the gate (#1787)."""
    _populate_complying_construct_gate_tree(git_project)
    _track_everything(git_project)
    ignored = git_project / "src" / "target" / "scratch.py"
    ignored.parent.mkdir()
    ignored.write_text("x = 1\n", encoding="utf-8")

    assert _construct_gate_escapes(_complying_construct_gate_pyproject(), git_project) == []


def test_a_project_that_is_not_a_git_repository_fails_the_check(
    tmp_path: Path, git_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no git repository to name the committed files, the gate fails instead of passing on none (#1787).

    The ceiling stops git at `tmp_path`, so a temporary directory inside a repository is no repository here.
    """
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    _populate_complying_construct_gate_tree(tmp_path)

    with pytest.raises(pytest.fail.Exception, match="git ls-files failed in"):
        _construct_gate_escapes(_complying_construct_gate_pyproject(), tmp_path)


def test_the_construct_gate_has_no_escape() -> None:
    """The ast-grep rules, sgconfig, pre-commit and TID251 gate the constructs with no escape (#1107, #1902)."""
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert _construct_gate_escapes(pyproject, REPO_ROOT) == []


def _missing_stack_lifecycle_paths(
    manifests_by_stack: Mapping[str, Sequence[Path]],
    post_helm_by_stack: Mapping[str, Sequence[Path]],
    k8s_dir: Path,
) -> list[str]:
    """Return stack:path entries missing from _MANIFESTS_BY_STACK or _POST_HELM_BY_STACK."""
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
        _MANIFESTS_BY_STACK,
        _POST_HELM_BY_STACK,
        DEFAULT_K8S_DIR,
    )

    assert (
        _missing_stack_lifecycle_paths(_MANIFESTS_BY_STACK, _POST_HELM_BY_STACK, DEFAULT_K8S_DIR),
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


def test_ai_and_github_package_inits_hold_only_docstrings(
    parsed_source_trees: dict[Path, ast.Module],
) -> None:
    """The six __init__.py files parse to a single docstring expression and nothing else (#1002, #776)."""
    init_paths = [
        REPO_ROOT / "src" / "devops_cli" / "ai" / "__init__.py",
        REPO_ROOT / "src" / "devops_cli" / "ai" / "agents" / "__init__.py",
        REPO_ROOT / "src" / "devops_cli" / "ai" / "mcp" / "__init__.py",
        REPO_ROOT / "src" / "devops_cli" / "config" / "__init__.py",
        REPO_ROOT / "src" / "devops_cli" / "core" / "__init__.py",
        REPO_ROOT / "src" / "devops_cli" / "github" / "__init__.py",
    ]
    failures = []
    for path in init_paths:
        tree = parsed_source_trees.get(path) or parse_python_file(path)
        is_only_docstring = (
            len(tree.body) == 1
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        )
        if not is_only_docstring:
            failures.append(str(path.relative_to(REPO_ROOT)))
    assert failures == []


def test_no_non_submodule_imports_from_ai_and_github_facades(
    parsed_repo_trees: dict[Path, ast.Module],
) -> None:
    """No import from facade packages names anything but a submodule (#1002, #776)."""
    facade_packages = {
        "devops_cli.ai": REPO_ROOT / "src" / "devops_cli" / "ai",
        "devops_cli.ai.agents": REPO_ROOT / "src" / "devops_cli" / "ai" / "agents",
        "devops_cli.ai.mcp": REPO_ROOT / "src" / "devops_cli" / "ai" / "mcp",
        "devops_cli.config": REPO_ROOT / "src" / "devops_cli" / "config",
        "devops_cli.core": REPO_ROOT / "src" / "devops_cli" / "core",
        "devops_cli.github": REPO_ROOT / "src" / "devops_cli" / "github",
    }
    allowed_submodules = {
        pkg_name: _find_package_submodules(pkg_dir) for pkg_name, pkg_dir in facade_packages.items()
    }
    violations: list[str] = []

    for py_file, tree in parsed_repo_trees.items():
        violations.extend(
            _collect_facade_import_violations(
                tree, allowed_submodules, str(py_file.relative_to(REPO_ROOT))
            )
        )

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


_CONTAINER_MUTATING_METHODS: frozenset[str] = frozenset(
    {
        "clear",
        "update",
        "pop",
        "popitem",
        "setdefault",
        "append",
        "extend",
        "insert",
        "remove",
        "add",
        "discard",
    }
)


def _extract_conftest_state_resets(conftest_tree: ast.Module) -> dict[str, tuple[str, ...]]:
    """Extract `_PROCESS_STATE_RESETS` from `tests/conftest.py`'s AST without importing conftest."""
    for stmt in conftest_tree.body:
        if (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.target.id == "_PROCESS_STATE_RESETS"
            and stmt.value is not None
        ):
            raw = ast.literal_eval(stmt.value)
            return {str(k): tuple(str(x) for x in v) for k, v in raw.items()}
    return {}


def _assigned_names(stmt: ast.stmt) -> list[str]:
    """Return top-level variable names bound by an `Assign` or `AnnAssign` statement."""
    if isinstance(stmt, ast.Assign):
        return [target.id for target in stmt.targets if isinstance(target, ast.Name)]
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        return [stmt.target.id]
    return []


def _index_top_level_defs(
    tree: ast.Module,
) -> tuple[
    dict[str, int], dict[str, ast.ClassDef], dict[str, ast.FunctionDef | ast.AsyncFunctionDef]
]:
    """Index top-level variable assignment lines, classes, and functions in `tree`."""
    assigns: dict[str, int] = {}
    classes: dict[str, ast.ClassDef] = {}
    funcs: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for stmt in tree.body:
        for name in _assigned_names(stmt):
            assigns[name] = getattr(stmt, "lineno", 1)
        if isinstance(stmt, ast.ClassDef):
            classes[stmt.name] = stmt
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs[stmt.name] = stmt
    return assigns, classes, funcs


def _find_class_method(
    cls_node: ast.ClassDef | None, method_name: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Return the method AST node named `method_name` on `cls_node`, or None."""
    if cls_node is None:
        return None
    for item in cls_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
            return item
    return None


def _collect_local_callee_specs(
    fn_node: ast.AST,
    classes: Mapping[str, ast.ClassDef],
    funcs: Mapping[str, ast.FunctionDef | ast.AsyncFunctionDef],
) -> list[str]:
    """Return local function or classmethod specs called inside `fn_node`."""
    callees: list[str] = []
    for sub in ast.walk(fn_node):
        if not isinstance(sub, ast.Call):
            continue
        if isinstance(sub.func, ast.Name) and sub.func.id in funcs:
            callees.append(sub.func.id)
        elif (
            isinstance(sub.func, ast.Attribute)
            and isinstance(sub.func.value, ast.Name)
            and sub.func.value.id in classes
        ):
            callees.append(f"{sub.func.value.id}.{sub.func.attr}")
    return callees


def _resolve_reset_nodes(
    registered_resets: Sequence[str],
    classes: Mapping[str, ast.ClassDef],
    funcs: Mapping[str, ast.FunctionDef | ast.AsyncFunctionDef],
) -> list[tuple[str | None, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Resolve registered public reset names and their transitive local helpers to `(cls_name, node)`."""
    resolved: list[tuple[str | None, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    visited: set[str] = set()
    queue = [spec for spec in registered_resets if not spec.split(".")[-1].startswith("_")]
    while queue:
        spec = queue.pop()
        if spec in visited:
            continue
        visited.add(spec)
        if "." in spec:
            cls_name, meth_name = spec.split(".", 1)
            method_node = _find_class_method(classes.get(cls_name), meth_name)
            if method_node is not None:
                resolved.append((cls_name, method_node))
        elif (fn_node := funcs.get(spec)) is not None:
            resolved.append((None, fn_node))
            queue.extend(_collect_local_callee_specs(fn_node, classes, funcs))
    return resolved


def _record_assign_target_reset(
    target: ast.expr,
    cls_name: str | None,
    reset_containers: set[str],
    reset_cls_attrs: set[tuple[str, str]],
) -> None:
    """Record a subscript container reset or class attribute rebind from an assignment target."""
    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
        reset_containers.add(target.value.id)
    elif (
        cls_name is not None
        and isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id in {"cls", cls_name}
    ):
        reset_cls_attrs.add((cls_name, target.attr))


def _record_call_reset(sub: ast.Call, reset_containers: set[str], reset_caches: set[str]) -> None:
    """Record a `cache_clear()` or container-mutating method call inside a reset function."""
    if not (isinstance(sub.func, ast.Attribute) and isinstance(sub.func.value, ast.Name)):
        return
    target_id = sub.func.value.id
    if sub.func.attr == "cache_clear":
        reset_caches.add(target_id)
    elif sub.func.attr in _CONTAINER_MUTATING_METHODS:
        reset_containers.add(target_id)


def _record_assign_reset(
    sub: ast.Assign,
    cls_name: str | None,
    reset_containers: set[str],
    reset_cls_attrs: set[tuple[str, str]],
) -> None:
    """Record container resets or class attribute rebinds across all targets of `sub`."""
    for target in sub.targets:
        _record_assign_target_reset(target, cls_name, reset_containers, reset_cls_attrs)


def _record_node_resets(
    cls_name: str | None,
    rnode: ast.FunctionDef | ast.AsyncFunctionDef,
    reset_globals: set[str],
    reset_containers: set[str],
    reset_caches: set[str],
    reset_cls_attrs: set[tuple[str, str]],
) -> None:
    """Record the globals, containers, caches, and class attributes reset inside `rnode`."""
    for sub in ast.walk(rnode):
        if isinstance(sub, ast.Global):
            reset_globals.update(sub.names)
        if isinstance(sub, ast.Call):
            _record_call_reset(sub, reset_containers, reset_caches)
        if isinstance(sub, ast.Assign):
            _record_assign_reset(sub, cls_name, reset_containers, reset_cls_attrs)


def _decorator_short_name(dec: ast.expr) -> str:
    """Return the bare name of a decorator (`cache`, `lru_cache`, `classmethod`, etc.)."""
    target = dec.func if isinstance(dec, ast.Call) else dec
    if isinstance(target, ast.Name):
        return target.id
    return target.attr if isinstance(target, ast.Attribute) else ""


def _mutated_container_names_in_node(sub: ast.AST) -> list[str]:
    """Return container variable names mutated by `sub` via method call or subscript assignment."""
    if (
        isinstance(sub, ast.Call)
        and isinstance(sub.func, ast.Attribute)
        and isinstance(sub.func.value, ast.Name)
        and sub.func.attr in _CONTAINER_MUTATING_METHODS
    ):
        return [sub.func.value.id]
    if isinstance(sub, (ast.Assign, ast.Delete)):
        return [
            target.value.id
            for target in sub.targets
            if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
        ]
    return []


def _collect_mutated_containers(
    tree: ast.Module, assigns: Mapping[str, int], seen_globals: set[str]
) -> dict[str, int]:
    """Return module-level containers mutated inside functions or methods, mapped to their line."""
    containers: dict[str, int] = {}
    scope_stmts = [
        stmt
        for stmt in tree.body
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    for stmt in scope_stmts:
        for sub in ast.walk(stmt):
            for cname in _mutated_container_names_in_node(sub):
                if cname in assigns and cname not in seen_globals:
                    containers.setdefault(cname, assigns[cname])
    return containers


def _classmethod_rebound_attrs(
    cls_name: str, item: ast.FunctionDef | ast.AsyncFunctionDef
) -> list[tuple[str, int]]:
    """Return `(attr_name, lineno)` for class attributes rebound inside `@classmethod` `item`."""
    if not any(_decorator_short_name(d) == "classmethod" for d in item.decorator_list):
        return []
    found: list[tuple[str, int]] = []
    for sub in ast.walk(item):
        if not isinstance(sub, ast.Assign):
            continue
        for target in sub.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id in {"cls", cls_name}
            ):
                found.append((target.attr, sub.lineno))
    return found


def _collect_classmethod_rebinds(
    classes: Mapping[str, ast.ClassDef],
) -> list[tuple[str, str, int]]:
    """Return `(cls_name, attr_name, lineno)` for every class attribute a `@classmethod` rebinds."""
    rebinds: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str]] = set()
    for cls_name, cls_node in classes.items():
        cls_assigns = _index_top_level_defs(ast.Module(body=cls_node.body, type_ignores=[]))[0]
        methods = [
            item
            for item in cls_node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for method in methods:
            for attr, lineno in _classmethod_rebound_attrs(cls_name, method):
                if (cls_name, attr) not in seen:
                    seen.add((cls_name, attr))
                    rebinds.append((cls_name, attr, cls_assigns.get(attr, lineno)))
    return rebinds


def _collect_global_rebinds(tree: ast.Module, assigns: Mapping[str, int]) -> dict[str, int]:
    """Return module-level names rebound through `global`, mapped to their line number."""
    seen_globals: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            for name in node.names:
                seen_globals.setdefault(name, assigns.get(name, node.lineno))
    return seen_globals


def _collect_cached_functions(tree: ast.Module) -> list[tuple[str, int]]:
    """Return `(func_name, lineno)` for every `@cache` or `@lru_cache` function in `tree`."""
    return [
        (node.name, node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(_decorator_short_name(d) in {"cache", "lru_cache"} for d in node.decorator_list)
    ]


def _find_unreset_process_state(
    rel_path: str, tree: ast.Module, registered_resets: Sequence[str]
) -> list[str]:
    """Return `path:line` violations for any of the 4 process-wide state forms not reset (#1310)."""
    assigns, classes, funcs = _index_top_level_defs(tree)
    reset_globals: set[str] = set()
    reset_containers: set[str] = set()
    reset_caches: set[str] = set()
    reset_cls_attrs: set[tuple[str, str]] = set()
    for cls_name, rnode in _resolve_reset_nodes(registered_resets, classes, funcs):
        _record_node_resets(
            cls_name, rnode, reset_globals, reset_containers, reset_caches, reset_cls_attrs
        )

    seen_globals = _collect_global_rebinds(tree, assigns)
    containers = _collect_mutated_containers(tree, assigns, set(seen_globals))
    return [
        *[
            f"{rel_path}:{lineno}: global {name} is not reset"
            for name, lineno in sorted(seen_globals.items(), key=lambda item: item[1])
            if name not in reset_globals
        ],
        *[
            f"{rel_path}:{lineno}: container {name} is not reset"
            for name, lineno in sorted(containers.items(), key=lambda item: item[1])
            if name not in reset_containers
        ],
        *[
            f"{rel_path}:{lineno}: cached function {name} is not reset"
            for name, lineno in _collect_cached_functions(tree)
            if name not in reset_caches
        ],
        *[
            f"{rel_path}:{lineno}: class attribute {cls_name}.{attr_name} is not reset"
            for cls_name, attr_name, lineno in _collect_classmethod_rebinds(classes)
            if (cls_name, attr_name) not in reset_cls_attrs
        ],
    ]


def _module_name_for_source_path(path: Path) -> str:
    """Return the dotted `devops_cli.*` module name for a file under `src/`."""
    parts = list(path.relative_to(REPO_ROOT / "src").with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def test_every_piece_of_process_wide_state_in_src_is_reset_by_the_floor(
    parsed_source_trees: dict[Path, ast.Module],
    parsed_repo_trees: dict[Path, ast.Module],
) -> None:
    """Every global rebind, mutated module container, cached function, and classmethod singleton in src is reset after each test (#1310)."""
    conftest_tree = parsed_repo_trees[REPO_ROOT / "tests" / "conftest.py"]
    resets_by_module = _extract_conftest_state_resets(conftest_tree)
    violations: list[str] = []
    for path, tree in sorted(parsed_source_trees.items()):
        rel_path = path.relative_to(REPO_ROOT).as_posix()
        module_name = _module_name_for_source_path(path)
        violations.extend(
            _find_unreset_process_state(rel_path, tree, resets_by_module.get(module_name, ()))
        )
    assert violations == []


def test_process_wide_state_invariant_reports_each_unreset_form() -> None:
    """The process-wide state scanner reports `path:line` for each of the four forms when unreset (#1310)."""
    sample = ast.parse(
        "import functools\n"
        "_STATE = None\n"
        "_ITEMS: dict[str, int] = {}\n"
        "def mutate() -> None:\n"
        "    global _STATE\n"
        "    _STATE = 1\n"
        "    _ITEMS['a'] = 2\n"
        "@functools.lru_cache(maxsize=1)\n"
        "def cached_val() -> int:\n"
        "    return 42\n"
        "class Service:\n"
        "    _instance = None\n"
        "    @classmethod\n"
        "    def get(cls) -> object:\n"
        "        cls._instance = object()\n"
        "        return cls._instance\n"
    )
    assert _find_unreset_process_state("src/devops_cli/sample.py", sample, ()) == [
        "src/devops_cli/sample.py:2: global _STATE is not reset",
        "src/devops_cli/sample.py:3: container _ITEMS is not reset",
        "src/devops_cli/sample.py:9: cached function cached_val is not reset",
        "src/devops_cli/sample.py:12: class attribute Service._instance is not reset",
    ]


def test_every_source_and_test_file_is_parsed_at_most_once(
    parsed_repo_trees: dict[Path, ast.Module],
) -> None:
    """Each file under `src/` and `tests/` is parsed at most once per test process (#1749)."""
    multiple_parses = [
        f"{path.name}: parsed {parse_count(path)} times"
        for path in parsed_repo_trees
        if parse_count(path) > 1
    ]
    assert multiple_parses == []
