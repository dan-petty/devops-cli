"""Tests for defect template well-formedness sweep (#556).

Verifies syntax checking across languages, honest NOT_RUN reporting for missing checkers,
comment collision detection, candidate site sweeping, run store persistence, regression gating,
and CLI template subcommands.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from devops_cli.ai.review.defects import Site, select_templates
from devops_cli.ai.review.samples import SampleCategory, SampleRepository
from devops_cli.ai.review.template_sweep import (
    STATUS_FAIL,
    STATUS_NOT_RUN,
    STATUS_PASS,
    SiteVerification,
    TemplateSweepReport,
    _check_c,
    _check_cpp,
    _check_hcl,
    _check_node_js,
    _check_python,
    _check_shell,
    _check_tree_sitter,
    _check_yaml,
    _record_verification,
    _run_cmd_checker,
    apply_mutation,
    check_syntax,
    is_inside_comment,
    save_sweep_run,
    sweep_templates,
)
from devops_cli.ai.run_store import (
    Mechanism,
    RegressionTolerances,
    check_regression,
    compare_runs,
    extract_metrics,
    load_runs,
    new_run,
)
from devops_cli.main import app

cli = CliRunner(env={"COLUMNS": "250", "NO_COLOR": "1", "TERM": "dumb"})


@pytest.fixture
def run_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate data directory for run store tests."""
    data_dir = tmp_path / ".data"
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(data_dir))
    return data_dir


def test_python_syntax_checker() -> None:
    """Verify python syntax checking passes valid AST and fails syntax errors."""
    valid = _check_python("def foo():\n    return 42\n")
    invalid = _check_python("def foo(\n    return 42\n")

    assert (
        valid.status,
        valid.checker,
        valid.error,
        invalid.status,
        invalid.checker,
        bool(invalid.error),
    ) == (STATUS_PASS, "python-ast", None, STATUS_FAIL, "python-ast", True)


def test_yaml_syntax_checker() -> None:
    """Verify YAML syntax checker handles valid documents and syntax errors."""
    valid = _check_yaml("name: test\nversion: 1.0\nitems:\n  - a\n  - b\n")
    invalid = _check_yaml("name: [test\nversion: 1.0\n")

    assert (
        valid.status,
        valid.checker,
        invalid.status,
        invalid.checker,
        bool(invalid.error),
    ) == (STATUS_PASS, "PyYAML", STATUS_FAIL, "PyYAML", True)


def test_hcl_syntax_checker() -> None:
    """Verify HCL syntax checker handles valid and invalid configuration blocks."""
    valid = _check_hcl('resource "aws_s3_bucket" "b" {\n  bucket = "my-bucket"\n}\n')
    invalid = _check_hcl('resource "aws_s3_bucket" "b" {\n  bucket = \n')

    assert (
        valid.status,
        valid.checker,
        invalid.status,
        invalid.checker,
        bool(invalid.error),
    ) == (STATUS_PASS, "python-hcl2", STATUS_FAIL, "python-hcl2", True)


def test_cmd_checker_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify missing external checkers report STATUS_NOT_RUN rather than passing."""
    monkeypatch.setattr("shutil.which", lambda _: None)
    result = _run_cmd_checker(["nonexistent-compiler", "--check"], b"code", "mock-checker")

    assert (result.status, result.checker, result.error) == (
        STATUS_NOT_RUN,
        "mock-checker",
        "nonexistent-compiler not installed",
    )


def test_cmd_checker_execution_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify external CLI checker handles zero exit, non-zero exit, and exceptions."""
    monkeypatch.setattr("shutil.which", lambda cmd: f"/usr/bin/{cmd}")

    def mock_run_success(*args: Any, **kwargs: Any) -> MagicMock:
        return MagicMock(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr("subprocess.run", mock_run_success)
    res_pass = _run_cmd_checker(["gcc", "-fsyntax-only"], b"int x = 0;", "gcc")

    def mock_run_failure(*args: Any, **kwargs: Any) -> MagicMock:
        return MagicMock(returncode=1, stdout=b"", stderr=b"syntax error: unexpected token")

    monkeypatch.setattr("subprocess.run", mock_run_failure)
    res_fail = _run_cmd_checker(["gcc", "-fsyntax-only"], b"int x =", "gcc")

    assert (
        res_pass.status,
        res_fail.status,
        res_fail.error,
    ) == (
        STATUS_PASS,
        STATUS_FAIL,
        "syntax error: unexpected token",
    )


def test_c_cpp_shell_node_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify dispatch for C, C++, shell, and node checkers."""
    monkeypatch.setattr("shutil.which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **k: MagicMock(returncode=0, stdout=b"", stderr=b"")
    )

    c_res = _check_c("int main() { return 0; }")
    cpp_res = _check_cpp("int main() { return 0; }")
    sh_res = _check_shell("echo hello")
    node_res = _check_node_js("const x = 1;")

    assert (
        c_res.checker,
        c_res.status,
        cpp_res.checker,
        cpp_res.status,
        sh_res.checker,
        sh_res.status,
        node_res.checker,
        node_res.status,
    ) == (
        "gcc",
        STATUS_PASS,
        "g++",
        STATUS_PASS,
        "bash",
        STATUS_PASS,
        "node",
        STATUS_PASS,
    )


def test_check_syntax_unsupported_and_special() -> None:
    """Verify check_syntax on special file types and unsupported extensions."""
    docker_res = check_syntax("Dockerfile", "FROM alpine:latest\nRUN echo hello\n")
    md_res = check_syntax("README.md", "# Documentation\nSome text.\n")
    unsupported_res = check_syntax("data.xyz_unknown", "some content")

    assert (
        docker_res.status,
        docker_res.checker,
        md_res.status,
        md_res.checker,
        unsupported_res.status,
        unsupported_res.checker,
    ) == (
        STATUS_PASS,
        "dockerfile",
        STATUS_PASS,
        "markdown",
        STATUS_NOT_RUN,
        "unsupported",
    )


def test_check_tree_sitter_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify tree-sitter checker reports NOT_RUN when native grammar is absent."""
    from devops_cli.ai.ast.engine import TreeSitterEngine

    monkeypatch.setattr(TreeSitterEngine, "_load_native_parser", lambda self, lang: None)
    res = _check_tree_sitter("fn main() {}", "rust")

    assert (res.status, res.checker, res.error) == (
        STATUS_NOT_RUN,
        "tree-sitter",
        "tree-sitter rust not installed",
    )


def test_is_inside_comment_detection() -> None:
    """Verify comment collision detection for line comments, docstrings, and bounds."""
    py_lines = ["# Python comment\n", '"""docstring"""\n', "x = 42\n", "def foo(): pass\n"]
    c_lines = [
        "// C line comment\n",
        "/* C block start\n",
        " * continuation\n",
        " */\n",
        "int x = 1;\n",
    ]
    md_lines = ["<!-- HTML comment -->\n", "# Header\n", "Body text\n"]

    py_comments = [
        is_inside_comment(py_lines, 0, "test.py"),
        is_inside_comment(py_lines, 1, "test.py"),
    ]
    py_code = [
        is_inside_comment(py_lines, 2, "test.py"),
        is_inside_comment(py_lines, 3, "test.py"),
    ]
    c_comments = [is_inside_comment(c_lines, i, "test.c") for i in range(4)]
    c_code = is_inside_comment(c_lines, 4, "test.c")
    md_comment = is_inside_comment(md_lines, 0, "test.md")
    oob_negative = is_inside_comment(py_lines, -1, "test.py")
    oob_exceeded = is_inside_comment(py_lines, 100, "test.py")

    assert (
        py_comments,
        py_code,
        c_comments,
        c_code,
        md_comment,
        oob_negative,
        oob_exceeded,
    ) == (
        [True, True],
        [False, False],
        [True, True, True, True],
        False,
        True,
        False,
        False,
    )


def test_apply_mutation() -> None:
    """Verify apply_mutation correctly replaces target lines."""
    lines = ["a = 1\n", "b = 2\n", "c = 3\n"]
    site = Site(start=1, end=2, replacement=("b = 99\n",), region=(2, 2))
    mutated = apply_mutation(lines, site)

    assert mutated == "a = 1\nb = 99\nc = 3\n"


def test_record_verification_aggregations() -> None:
    """Verify _record_verification updates report totals, collisions, and failures."""
    report = TemplateSweepReport(
        sites_per_template=Counter(),
        sites_per_category=Counter(),
        checkers_run=Counter(),
        checkers_not_run=Counter(),
    )

    clean_v = SiteVerification(
        template="drop-guard",
        sample="sample-py",
        category="library",
        file="src/mod.py",
        line=10,
        checker="python-ast",
        status=STATUS_PASS,
        in_comment=False,
    )
    fail_v = SiteVerification(
        template="drop-guard",
        sample="sample-py",
        category="library",
        file="src/mod.py",
        line=20,
        checker="python-ast",
        status=STATUS_FAIL,
        error="SyntaxError: invalid syntax",
        in_comment=False,
    )
    comment_v = SiteVerification(
        template="invert-condition",
        sample="sample-py",
        category="library",
        file="src/mod.py",
        line=30,
        checker="python-ast",
        status=STATUS_PASS,
        in_comment=True,
    )
    not_run_v = SiteVerification(
        template="drop-guard",
        sample="sample-go",
        category="service",
        file="main.go",
        line=5,
        checker="tree-sitter",
        status=STATUS_NOT_RUN,
        error="tree-sitter go not installed",
        in_comment=False,
    )

    for v in (clean_v, fail_v, comment_v, not_run_v):
        _record_verification(report, v)

    assert (
        report.total_sites,
        report.sites_per_template["drop-guard"],
        report.sites_per_template["invert-condition"],
        report.sites_per_category["library"],
        len(report.parse_failures),
        len(report.comment_collisions),
        report.checkers_run["python-ast"],
        report.checkers_not_run["tree-sitter"],
    ) == (
        4,
        3,
        1,
        3,
        1,
        1,
        3,
        1,
    )


def test_sweep_templates_on_synthetic_samples(tmp_path: Path) -> None:
    """Verify sweep_templates on synthetic sample checkout structures."""
    sample_dir = tmp_path / "mock-python-service"
    sample_dir.mkdir(parents=True)
    src_dir = sample_dir / "src"
    src_dir.mkdir(parents=True)

    py_file = src_dir / "app.py"
    py_file.write_text(
        "async def check_access(user: dict) -> bool:\n    return await auth.verify(user)\n",
        encoding="utf-8",
    )

    sample = SampleRepository(
        name="mock-python-service",
        category=SampleCategory.PYTHON,
        languages=["python"],
        repository="https://example.com/mock-python-service",
        commit="a" * 40,
        license="MIT",
        license_files=["LICENSE"],
        paths=["src"],
    )

    report = sweep_templates(
        samples=[sample],
        templates=select_templates(["drop-await"]),
        root=tmp_path,
    )

    assert (
        report.samples_checked,
        report.files_checked,
        report.total_sites >= 1,
        len(report.parse_failures),
        len(report.comment_collisions),
        report.passed,
    ) == (
        1,
        1,
        True,
        0,
        0,
        True,
    )


def test_sweep_run_store_persistence_and_regression(run_env: Path) -> None:
    """Verify save_sweep_run stores records with TEMPLATE_SWEEP and checks regression."""
    report = TemplateSweepReport(
        files_checked=5,
        total_sites=10,
        sites_per_template={"drop-await": 6, "disable-tls-verify": 4},
        sites_per_category={"python": 10},
        checkers_run={"python-ast": 10},
        checkers_not_run={},
        parse_failures=[],
        comment_collisions=[],
        passed=True,
    )
    samples = [
        SampleRepository(
            name="mock-svc",
            category=SampleCategory.PYTHON,
            languages=["python"],
            repository="https://example.com/mock-svc",
            commit="a" * 40,
            license="MIT",
            license_files=["LICENSE"],
            paths=["src"],
        )
    ]
    templates = select_templates(["drop-await", "disable-tls-verify"])

    saved = save_sweep_run(report, templates, samples)
    (loaded,) = load_runs(Mechanism.TEMPLATE_SWEEP)
    metrics, _ = extract_metrics(loaded)

    assert (
        saved.record.mechanism,
        loaded.run_id,
        metrics["total_sites"],
        metrics["parse_failures"],
        metrics["comment_collisions"],
        metrics["tested_mutations"],
    ) == (
        Mechanism.TEMPLATE_SWEEP,
        saved.record.run_id,
        10.0,
        0.0,
        0.0,
        10.0,
    )

    # Verify regression detection
    regressed_run = new_run(
        Mechanism.TEMPLATE_SWEEP,
        setup=loaded.setup,
        subject=loaded.subject,
        results={
            "total_sites": 10,
            "parse_failures": 1,
            "comment_collisions": 1,
            "tested_mutations": 10,
        },
    )

    comp_pass = compare_runs(loaded, loaded)
    comp_fail = compare_runs(loaded, regressed_run)

    rep_pass = check_regression(comp_pass, RegressionTolerances())
    rep_fail = check_regression(comp_fail, RegressionTolerances())

    assert (
        rep_pass.passed,
        rep_fail.passed,
        [v.metric for v in rep_fail.verdicts if not v.passed],
    ) == (
        True,
        False,
        ["parse_failures", "comment_collisions"],
    )


def test_cli_review_templates_list() -> None:
    """Verify devops review templates list command."""
    res_table = cli.invoke(app, ["review", "templates", "list"])
    res_json = cli.invoke(app, ["review", "templates", "list", "--format", "json"])

    data = json.loads(res_json.stdout)

    assert (
        res_table.exit_code,
        res_json.exit_code,
        isinstance(data, list),
        len(data) > 0,
        "name" in data[0],
        "description" in data[0],
    ) == (
        0,
        0,
        True,
        True,
        True,
        True,
    )


def test_cli_review_templates_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devops review templates check CLI execution with filtering and save."""
    from devops_cli.ai.review.samples import SampleCatalog
    from devops_cli.commands import review as review_commands

    data_dir = tmp_path / ".data"
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(data_dir))
    samples_path = data_dir / "samples"
    sample_dir = samples_path / "mock-python-sample"
    src_dir = sample_dir / "src"
    src_dir.mkdir(parents=True)
    (sample_dir / "LICENSE").write_text("MIT", encoding="utf-8")
    (src_dir / "main.py").write_text(
        "async def fetch():\n    return await client.get()\n", encoding="utf-8"
    )

    sample = SampleRepository(
        name="mock-python-sample",
        category=SampleCategory.PYTHON,
        languages=["python"],
        repository="https://example.com/mock-python-sample",
        commit="a" * 40,
        license="MIT",
        license_files=["LICENSE"],
        paths=["src"],
    )
    catalog = SampleCatalog(about="mock", samples=[sample])
    monkeypatch.setattr(review_commands, "load_sample_catalog", lambda: catalog)
    monkeypatch.setattr(review_commands, "checkout_problems", lambda s, p: [])

    # Test JSON output with save
    res = cli.invoke(
        app,
        [
            "review",
            "templates",
            "check",
            "--sample",
            "mock-python-sample",
            "--template",
            "drop-await",
            "--format",
            "json",
            "--save",
        ],
    )

    # Also test sweep alias with table output and --no-save
    res_alias = cli.invoke(
        app,
        [
            "review",
            "templates",
            "sweep",
            "--sample",
            "mock-python-sample",
            "--template",
            "drop-await",
            "--no-save",
        ],
    )

    assert (
        res.exit_code,
        res_alias.exit_code,
        "samples_checked" in json.loads(res.stdout),
        "total_sites" in json.loads(res.stdout),
    ) == (
        0,
        0,
        True,
        True,
    )


def test_cli_review_templates_check_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify devops review templates check returns exit code 1 on sweep failure."""
    from devops_cli.ai.review.samples import SampleCatalog
    from devops_cli.commands import review as review_commands

    data_dir = tmp_path / ".data"
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(data_dir))
    samples_path = data_dir / "samples"
    sample_dir = samples_path / "mock-broken-sample"
    src_dir = sample_dir / "src"
    src_dir.mkdir(parents=True)
    (sample_dir / "LICENSE").write_text("MIT", encoding="utf-8")
    (src_dir / "main.py").write_text("x = 1\n", encoding="utf-8")

    sample = SampleRepository(
        name="mock-broken-sample",
        category=SampleCategory.PYTHON,
        languages=["python"],
        repository="https://example.com/mock-broken-sample",
        commit="a" * 40,
        license="MIT",
        license_files=["LICENSE"],
        paths=["src"],
    )
    catalog = SampleCatalog(about="mock", samples=[sample])
    monkeypatch.setattr(review_commands, "load_sample_catalog", lambda: catalog)
    monkeypatch.setattr(review_commands, "checkout_problems", lambda s, p: [])

    failing_report = TemplateSweepReport(
        samples_checked=1,
        files_checked=1,
        total_sites=1,
        parse_failures=[
            {
                "template": "t",
                "sample": "s",
                "file": "f",
                "line": 1,
                "checker": "c",
                "error": "err",
            }
        ],
        passed=False,
    )
    monkeypatch.setattr(review_commands, "sweep_templates", lambda **_: failing_report)

    res = cli.invoke(
        app,
        [
            "review",
            "templates",
            "check",
            "--sample",
            "mock-broken-sample",
            "--template",
            "drop-await",
            "--no-save",
        ],
    )

    assert res.exit_code == 1
