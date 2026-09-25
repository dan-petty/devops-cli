"""Defect template well-formedness sweep across sample repositories (#556).

Sweeps synthetic defect templates over the fetched sample repositories, verifying that:
1. Each mutation remains syntactically well-formed according to language checkers;
2. Injections never fall inside block comments or documentation code blocks;
3. Missing external checkers are reported as NOT_RUN, never as passed;
4. Sweep results are recorded in the evaluation run store (Mechanism.TEMPLATE_SWEEP).
"""

from __future__ import annotations

import ast
import shutil
import subprocess
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.ai.ast.engine import TreeSitterEngine, detect_language
from devops_cli.ai.review.defects import (
    TEMPLATES,
    DefectTemplate,
    Site,
    _mask_lines,
)
from devops_cli.ai.review.sample_validation import sample_files
from devops_cli.ai.review.samples import (
    SampleRepository,
    load_sample_catalog,
    samples_dir,
)
from devops_cli.ai.run_store import Mechanism, SavedRun, record_run

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_NOT_RUN = "NOT_RUN"

# Suffixes that use C/C++ syntax checking
_C_SUFFIXES = frozenset({".c", ".h"})
_CPP_SUFFIXES = frozenset({".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx"})
_JS_SUFFIXES = frozenset({".js", ".jsx", ".mjs", ".cjs"})
_TS_SUFFIXES = frozenset({".ts", ".tsx"})
_SHELL_SUFFIXES = frozenset({".sh", ".bash", ".envsh"})
_HCL_SUFFIXES = frozenset({".tf", ".hcl"})
_YAML_SUFFIXES = frozenset({".yaml", ".yml"})


class CheckResult(BaseModel):
    """Result of checking a mutated file for syntax validity."""

    checker: str
    status: str
    error: str | None = None


class SiteVerification(BaseModel):
    """Result of validating one candidate injection site."""

    template: str
    sample: str
    category: str
    file: str
    line: int
    checker: str
    status: str
    error: str | None = None
    in_comment: bool = False


class TemplateSweepReport(BaseModel):
    """Aggregated report of a defect template well-formedness sweep."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    samples_checked: int = 0
    files_checked: int = 0
    total_sites: int = 0
    sites_per_template: dict[str, int] = Field(default_factory=dict)
    sites_per_category: dict[str, int] = Field(default_factory=dict)
    checkers_run: dict[str, int] = Field(default_factory=dict)
    checkers_not_run: dict[str, int] = Field(default_factory=dict)
    parse_failures: list[dict[str, Any]] = Field(default_factory=list)
    comment_collisions: list[dict[str, Any]] = Field(default_factory=list)
    passed: bool = True


def _is_only_missing_include(error: str | None) -> bool:
    """Check if compiler failed only due to missing #include header files."""
    if not error:
        return False
    lines = [line.strip() for line in error.strip().splitlines() if line.strip()]
    return len(lines) > 0 and all(
        "No such file or directory" in line or "compilation terminated" in line
        for line in lines
    )


def _run_cmd_checker(
    cmd: list[str], input_bytes: bytes, checker_name: str
) -> CheckResult:
    """Run an external CLI command with stdin bytes as syntax checker."""
    binary = shutil.which(cmd[0])
    if not binary:
        return CheckResult(
            checker=checker_name, status=STATUS_NOT_RUN, error=f"{cmd[0]} not installed"
        )
    full_cmd = [binary, *cmd[1:]]
    try:
        proc = subprocess.run(
            full_cmd, input=input_bytes, capture_output=True, timeout=10, check=False
        )
        if proc.returncode == 0:
            return CheckResult(checker=checker_name, status=STATUS_PASS)
        err = (proc.stderr or proc.stdout).decode(errors="replace").strip()
        if _is_only_missing_include(err):
            return CheckResult(
                checker=checker_name, status=STATUS_NOT_RUN, error=err[:256]
            )
        return CheckResult(checker=checker_name, status=STATUS_FAIL, error=err[:256])
    except (subprocess.TimeoutExpired, OSError) as exc:
        return CheckResult(
            checker=checker_name, status=STATUS_FAIL, error=str(exc)[:256]
        )


def _check_python(content: str) -> CheckResult:
    try:
        ast.parse(content)
        return CheckResult(checker="python-ast", status=STATUS_PASS)
    except SyntaxError as exc:
        return CheckResult(
            checker="python-ast", status=STATUS_FAIL, error=str(exc)[:256]
        )


def _c_include_flags(path: Path | str) -> list[str]:
    """Derive compiler -I flags from path and surrounding repository directories."""
    p = Path(path).resolve()
    flags = [f"-I{p.parent}"]
    curr = p.parent
    for _ in range(3):
        if curr == curr.parent:
            break
        flags.append(f"-I{curr}")
        if (curr / "include").is_dir():
            flags.append(f"-I{curr / 'include'}")
        if (curr / "src").is_dir():
            flags.append(f"-I{curr / 'src'}")
        curr = curr.parent
    return list(dict.fromkeys(flags))


def _check_c(content: str, path: Path | str = "code.c") -> CheckResult:
    inc_flags = _c_include_flags(path)
    return _run_cmd_checker(
        ["gcc", "-fsyntax-only", *inc_flags, "-x", "c", "-"],
        content.encode("utf-8"),
        "gcc",
    )


def _check_cpp(content: str, path: Path | str = "code.cpp") -> CheckResult:
    inc_flags = _c_include_flags(path)
    return _run_cmd_checker(
        ["g++", "-std=c++20", "-fsyntax-only", *inc_flags, "-x", "c++", "-"],
        content.encode("utf-8"),
        "g++",
    )


def _check_header(content: str, path: Path | str = "header.h") -> CheckResult:
    res_c = _check_c(content, path)
    if res_c.status == STATUS_PASS:
        return res_c
    res_cpp = _check_cpp(content, path)
    if res_cpp.status == STATUS_PASS:
        return res_cpp
    return res_cpp if res_cpp.status == STATUS_FAIL else res_c


def _check_node_js(content: str) -> CheckResult:
    return _run_cmd_checker(
        ["node", "--input-type=module", "--check"], content.encode("utf-8"), "node"
    )


def _check_shell(content: str) -> CheckResult:
    return _run_cmd_checker(["bash", "-n"], content.encode("utf-8"), "bash")


def _check_hcl(content: str) -> CheckResult:
    try:
        import hcl2

        hcl2.loads(content)
        return CheckResult(checker="python-hcl2", status=STATUS_PASS)
    except ImportError:
        return CheckResult(
            checker="python-hcl2",
            status=STATUS_NOT_RUN,
            error="python-hcl2 not installed",
        )
    except Exception as exc:
        return CheckResult(
            checker="python-hcl2", status=STATUS_FAIL, error=str(exc)[:256]
        )


def _check_yaml(content: str) -> CheckResult:
    try:
        import yaml

        list(yaml.safe_load_all(content))
        return CheckResult(checker="PyYAML", status=STATUS_PASS)
    except ImportError:
        return CheckResult(
            checker="PyYAML", status=STATUS_NOT_RUN, error="PyYAML not installed"
        )
    except Exception as exc:
        return CheckResult(checker="PyYAML", status=STATUS_FAIL, error=str(exc)[:256])


def _check_tree_sitter(content: str, lang: str) -> CheckResult:
    """Check syntax via TreeSitterEngine when native grammar is present."""
    engine = TreeSitterEngine()
    loaded = engine._load_native_parser(lang)
    if loaded is None:
        return CheckResult(
            checker="tree-sitter",
            status=STATUS_NOT_RUN,
            error=f"tree-sitter {lang} not installed",
        )
    parser, _ = loaded
    try:
        tree = parser.parse(content.encode("utf-8"))
        if tree.root_node.has_error:
            return CheckResult(
                checker="tree-sitter",
                status=STATUS_FAIL,
                error="tree-sitter syntax error",
            )
        return CheckResult(checker="tree-sitter", status=STATUS_PASS)
    except Exception as exc:
        return CheckResult(
            checker="tree-sitter", status=STATUS_FAIL, error=str(exc)[:256]
        )


_CHECKER_DISPATCH: dict[str, Callable[[str, Path | str], CheckResult]] = {
    ".py": lambda c, p: _check_python(c),
    ".pyi": lambda c, p: _check_python(c),
    ".c": _check_c,
    ".h": _check_header,
    ".cc": _check_cpp,
    ".cpp": _check_cpp,
    ".cxx": _check_cpp,
    ".hh": _check_cpp,
    ".hpp": _check_cpp,
    ".hxx": _check_cpp,
    ".js": lambda c, p: _check_node_js(c),
    ".jsx": lambda c, p: _check_node_js(c),
    ".mjs": lambda c, p: _check_node_js(c),
    ".cjs": lambda c, p: _check_node_js(c),
    ".ts": lambda c, p: _check_tree_sitter(c, "typescript"),
    ".tsx": lambda c, p: _check_tree_sitter(c, "typescript"),
    ".sh": lambda c, p: _check_shell(c),
    ".bash": lambda c, p: _check_shell(c),
    ".envsh": lambda c, p: _check_shell(c),
    ".tf": lambda c, p: _check_hcl(c),
    ".hcl": lambda c, p: _check_hcl(c),
    ".yaml": lambda c, p: _check_yaml(c),
    ".yml": lambda c, p: _check_yaml(c),
    ".go": lambda c, p: _check_tree_sitter(c, "go"),
    ".rs": lambda c, p: _check_tree_sitter(c, "rust"),
    ".java": lambda c, p: _check_tree_sitter(c, "java"),
}


def check_syntax(path: Path | str, content: str) -> CheckResult:
    """Validate mutated file content with the appropriate language checker."""
    suffix = Path(path).suffix.lower()
    name = Path(path).name.lower()

    if name in ("dockerfile", "containerfile"):
        return CheckResult(checker="dockerfile", status=STATUS_PASS)
    if suffix in (".md", ".markdown"):
        return CheckResult(checker="markdown", status=STATUS_PASS)

    checker_fn = _CHECKER_DISPATCH.get(suffix)
    if checker_fn is not None:
        return checker_fn(content, path)

    lang = detect_language(path)
    if lang:
        return _check_tree_sitter(content, lang)
    return CheckResult(
        checker="unsupported", status=STATUS_NOT_RUN, error=f"no checker for {suffix}"
    )


_C_STYLE_COMMENT_SUFFIXES = frozenset(
    {
        ".c",
        ".h",
        ".cc",
        ".cpp",
        ".cxx",
        ".hh",
        ".hpp",
        ".hxx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".mts",
        ".cts",
        ".go",
        ".rs",
        ".java",
        ".cs",
    }
)


def _is_inside_block_marker(
    lines: list[str], start_line: int, open_marker: str, close_marker: str
) -> bool:
    """Check whether a line falls between multi-line block markers."""
    in_block = False
    for idx, line in enumerate(lines[: start_line + 1]):
        stripped = line.strip()
        if in_block:
            if close_marker in stripped:
                in_block = False
        elif (
            open_marker in stripped
            and close_marker not in stripped.split(open_marker, 1)[1]
        ):
            in_block = True
    return in_block


def _is_script_or_config_comment(raw_line: str, name: str, suffix: str) -> bool | None:
    if (
        name in ("dockerfile", "containerfile")
        or suffix in _SHELL_SUFFIXES | _YAML_SUFFIXES
    ):
        return raw_line.startswith("#")
    return None


def _is_doc_or_python_comment(
    lines: list[str], start_line: int, raw_line: str, suffix: str
) -> bool | None:
    if suffix in (".py", ".pyi"):
        if raw_line.startswith(("#", '"""', "'''")):
            return True
        return _is_inside_block_marker(
            lines, start_line, '"""', '"""'
        ) or _is_inside_block_marker(lines, start_line, "'''", "'''")
    if suffix in (".md", ".markdown", ".rst"):
        return raw_line.startswith("<!--") or _is_inside_block_marker(
            lines, start_line, "<!--", "-->"
        )
    return None


def _is_c_style_comment(lines: list[str], start_line: int, suffix: str) -> bool:
    if suffix in _C_STYLE_COMMENT_SUFFIXES:
        from devops_cli.ai.review.defects import _CODE_NOISE

        masked = _mask_lines(lines, _CODE_NOISE, blank_strings=False)
        if start_line < len(masked):
            original_stripped = lines[start_line].strip()
            masked_stripped = masked[start_line].strip()
            if original_stripped and not masked_stripped:
                return True
    return False


def is_inside_comment(lines: list[str], start_line: int, filename: str) -> bool:
    """Detect whether injection line falls inside a block or single-line comment."""
    if not (0 <= start_line < len(lines)):
        return False
    raw_line = lines[start_line].strip()
    path = Path(filename)
    suffix, name = path.suffix.lower(), path.name.lower()

    if (cfg_res := _is_script_or_config_comment(raw_line, name, suffix)) is not None:
        return cfg_res
    if (
        doc_res := _is_doc_or_python_comment(lines, start_line, raw_line, suffix)
    ) is not None:
        return doc_res
    if raw_line.startswith(("//", "/*", "*", "#", "<!--", "--")):
        return True
    return _is_c_style_comment(lines, start_line, suffix)


def apply_mutation(lines: list[str], site: Site) -> str:
    """Apply a candidate site replacement to the original lines."""
    mutated = lines[: site.start] + list(site.replacement) + lines[site.end :]
    return "".join(mutated)


def _verify_site(
    site: Site,
    template: DefectTemplate,
    sample: SampleRepository,
    file_path: Path,
    rel_path: str,
    lines: list[str],
) -> SiteVerification:
    """Check a single injection site for comment collision and syntax well-formedness."""
    in_comment = is_inside_comment(lines, site.start, file_path.name)
    mutated = apply_mutation(lines, site)
    syntax = check_syntax(file_path, mutated)
    if syntax.status == STATUS_FAIL:
        orig_syntax = check_syntax(file_path, "".join(lines))
        if orig_syntax.status == STATUS_FAIL:
            syntax = CheckResult(
                checker=syntax.checker,
                status=STATUS_NOT_RUN,
                error=f"baseline file does not parse with {syntax.checker}",
            )

    return SiteVerification(
        template=template.name,
        sample=sample.name,
        category=sample.category.value,
        file=rel_path,
        line=site.start + 1,
        checker=syntax.checker,
        status=syntax.status,
        error=syntax.error,
        in_comment=in_comment,
    )


def _process_file_sites(
    file_path: Path,
    sample: SampleRepository,
    checkout: Path,
    templates: tuple[DefectTemplate, ...],
) -> list[SiteVerification]:
    """Find and verify all candidate injection sites in one sample file."""
    verifications: list[SiteVerification] = []
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines(
            keepends=True
        )
    except OSError:
        return verifications

    rel = file_path.relative_to(checkout).as_posix()
    for template in templates:
        finder = template.finder_for(file_path.name)
        if finder is None:
            continue
        try:
            sites = finder(lines)
        except Exception:
            continue
        for site in sites:
            verifications.append(
                _verify_site(site, template, sample, file_path, rel, lines)
            )
    return verifications


def _record_verification(report: TemplateSweepReport, v: SiteVerification) -> None:
    """Update aggregated report statistics with one site verification result."""
    report.total_sites += 1
    report.sites_per_template[v.template] = (
        report.sites_per_template.get(v.template, 0) + 1
    )
    report.sites_per_category[v.category] = (
        report.sites_per_category.get(v.category, 0) + 1
    )

    if v.in_comment:
        report.comment_collisions.append(
            {
                "template": v.template,
                "sample": v.sample,
                "file": v.file,
                "line": v.line,
            }
        )

    if v.status == STATUS_NOT_RUN:
        report.checkers_not_run[v.checker] = (
            report.checkers_not_run.get(v.checker, 0) + 1
        )
    else:
        report.checkers_run[v.checker] = report.checkers_run.get(v.checker, 0) + 1
        if v.status == STATUS_FAIL:
            report.parse_failures.append(
                {
                    "template": v.template,
                    "sample": v.sample,
                    "file": v.file,
                    "line": v.line,
                    "checker": v.checker,
                    "error": v.error,
                }
            )


def _sweep_sample(
    sample: SampleRepository, base_dir: Path, templates: tuple[DefectTemplate, ...]
) -> tuple[list[SiteVerification], int]:
    """Sweep all reviewable files in one sample repository."""
    checkout = base_dir / sample.name
    if not checkout.exists():
        return [], 0
    reviewable_files = sample_files(sample, checkout)
    verifications: list[SiteVerification] = []
    for file_path in reviewable_files:
        verifications.extend(
            _process_file_sites(file_path, sample, checkout, templates)
        )
    return verifications, len(reviewable_files)


def sweep_templates(
    samples: list[SampleRepository] | None = None,
    templates: tuple[DefectTemplate, ...] | None = None,
    root: Path | None = None,
) -> TemplateSweepReport:
    """Execute complete well-formedness sweep across the specified samples and templates."""
    active_samples = samples if samples is not None else load_sample_catalog().samples
    active_templates = templates if templates is not None else TEMPLATES
    base_dir = root or samples_dir()

    report = TemplateSweepReport(
        samples_checked=len(active_samples),
        sites_per_template=Counter(),
        sites_per_category=Counter(),
        checkers_run=Counter(),
        checkers_not_run=Counter(),
    )

    for sample in active_samples:
        results, file_count = _sweep_sample(sample, base_dir, active_templates)
        report.files_checked += file_count
        for v in results:
            _record_verification(report, v)

    report.passed = (
        len(report.parse_failures) == 0 and len(report.comment_collisions) == 0
    )
    return report


def save_sweep_run(
    report: TemplateSweepReport,
    templates: tuple[DefectTemplate, ...],
    samples: list[SampleRepository],
    root: Path | None = None,
) -> SavedRun:
    """Record a template sweep result in the evaluation run store."""
    setup = {
        "templates": [t.name for t in templates],
        "categories": sorted({s.category.value for s in samples}),
        "samples": [s.name for s in samples],
    }
    subject = {
        "target": "sample-catalog",
        "sample_count": len(samples),
        "file_count": report.files_checked,
    }
    results = {
        "total_sites": report.total_sites,
        "parse_failures": len(report.parse_failures),
        "comment_collisions": len(report.comment_collisions),
        "tested_mutations": sum(report.checkers_run.values()),
        "untested_sites": sum(report.checkers_not_run.values()),
        "checkers_run": report.checkers_run,
        "checkers_not_run": report.checkers_not_run,
        "sites_per_template": report.sites_per_template,
        "sites_per_category": report.sites_per_category,
        "passed": report.passed,
    }
    return record_run(
        Mechanism.TEMPLATE_SWEEP, setup=setup, subject=subject, results=results
    )


__all__ = [
    "STATUS_FAIL",
    "STATUS_NOT_RUN",
    "STATUS_PASS",
    "CheckResult",
    "SiteVerification",
    "TemplateSweepReport",
    "apply_mutation",
    "check_syntax",
    "is_inside_comment",
    "save_sweep_run",
    "sweep_templates",
]
