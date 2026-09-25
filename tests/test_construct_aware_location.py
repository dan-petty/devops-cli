"""Tests for construct-aware finding location validation and AST relocation."""

from __future__ import annotations

import ast
from pathlib import Path

from devops_cli.ai.review.construct_validator import (
    collect_ast_constructs,
    extract_finding_construct_candidates,
    validate_construct_location,
)
from devops_cli.ai.review.verification import _deterministic_pre_verification
from devops_cli.ai.review_schema import Finding, _merge_two_findings

SAMPLE_PYTHON_CODE = '''"""Sample module for construct validation."""

import requests


@app.get("/users")
def get_users():
    """Retrieve users."""
    token = "secret_auth_token"
    res = requests.get("https://example.com/api")
    return res.json()


class PaymentProcessor:
    """Process card payments."""

    @transactional
    def process_charge(self, amount: int):
        validated_amount = amount
        return validated_amount
'''


def test_collect_ast_constructs() -> None:
    """Verify that collect_ast_constructs indexes functions, classes, calls, decorators, and literals."""
    tree = ast.parse(SAMPLE_PYTHON_CODE)
    constructs = collect_ast_constructs(tree)

    kinds = {c.kind for c in constructs}
    names = {c.name for c in constructs}

    assert {"function", "class", "call", "decorator", "assignment", "literal", "symbol"}.issubset(
        kinds
    )
    assert (
        "get_users" in names,
        "PaymentProcessor" in names,
        "requests.get" in names,
        "app.get" in names,
        "secret_auth_token" in names,
    ) == (True, True, True, True, True)


def test_extract_finding_construct_candidates() -> None:
    """Verify that extract_finding_construct_candidates extracts backticks, calls, and symbols."""
    finding = Finding(
        title="Insecure call to `requests.get` in `get_users`",
        location="app.py:10",
        description="The function calls `requests.get` using 'secret_auth_token' without timeout.",
    )
    candidates = extract_finding_construct_candidates(finding)

    assert (
        "requests.get" in candidates,
        "get_users" in candidates,
        "secret_auth_token" in candidates,
    ) == (True, True, True)


def test_construct_in_span_passes_untouched(tmp_path: Path) -> None:
    """Verify that a finding citing the exact line of a named construct passes untouched."""
    py_file = tmp_path / "app.py"
    py_file.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")

    # get_users is defined at line 7
    finding = Finding(
        title="Flaw in `get_users`",
        location=f"{py_file}:7",
        description="Function `get_users` lacks proper error handling.",
    )
    validated = validate_construct_location(finding, py_file)

    assert (
        validated.location,
        validated.relocated_from,
        validated.status,
        validated.reportable,
    ) == (
        f"{py_file}:7",
        None,
        "UNVERIFIED",
        True,
    )


def test_construct_enclosed_in_function_span_passes(tmp_path: Path) -> None:
    """Verify that citing inside a function span that defines or calls the construct passes."""
    py_file = tmp_path / "app.py"
    py_file.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")

    # get_users spans lines 7 to 11; citing line 9 inside get_users passes
    finding = Finding(
        title="Vulnerable logic in `get_users`",
        location=f"{py_file}:9",
        description="Function `get_users` performs token operations without validation.",
    )
    validated = validate_construct_location(finding, py_file)

    assert (
        validated.location,
        validated.relocated_from,
        validated.status,
    ) == (
        f"{py_file}:9",
        None,
        "UNVERIFIED",
    )


def test_construct_mismatch_relocates_finding(tmp_path: Path) -> None:
    """Verify that a finding citing an unrelated line is relocated to the correct construct."""
    py_file = tmp_path / "app.py"
    py_file.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")

    # Citing line 2 (import statement) for requests.get which is at line 10
    finding = Finding(
        title="Unbounded timeout on `requests.get`",
        location=f"{py_file}:2",
        description="Network call `requests.get` has no timeout bound.",
    )
    validated = validate_construct_location(finding, py_file)

    assert (
        validated.location,
        validated.relocated_from,
        validated.status,
        validated.reportable,
    ) == (
        f"{py_file}:10",
        f"{py_file}:2",
        "UNVERIFIED",
        True,
    )


def test_function_definition_mismatch_relocates_span(tmp_path: Path) -> None:
    """Verify that an enclosing construct (function/class) is relocated with its span."""
    py_file = tmp_path / "app.py"
    py_file.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")

    # Citing line 1 for PaymentProcessor which is at lines 14-20
    finding = Finding(
        title="Missing auditing in `PaymentProcessor`",
        location=f"{py_file}:1",
        description="Class `PaymentProcessor` should implement payment auditing.",
    )
    validated = validate_construct_location(finding, py_file)

    assert (
        validated.location,
        validated.relocated_from,
        validated.status,
    ) == (
        f"{py_file}:14-20",
        f"{py_file}:1",
        "UNVERIFIED",
    )


def test_absent_construct_invalidates_finding(tmp_path: Path) -> None:
    """Verify that a finding citing a construct absent from the file entirely is invalidated."""
    py_file = tmp_path / "app.py"
    py_file.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")

    finding = Finding(
        title="Insecure deserialization with `pickle.loads`",
        location=f"{py_file}:5",
        description="Untrusted data deserialized with `pickle.loads`.",
    )
    validated = validate_construct_location(finding, py_file)

    assert (
        validated.status,
        validated.verified,
        validated.reportable,
    ) == (
        "INVALIDATED",
        False,
        False,
    )
    assert "Construct 'pickle.loads' cited in finding is absent" in str(
        validated.invalidation_reason
    )


def test_general_finding_without_construct_passes_untouched(tmp_path: Path) -> None:
    """Verify that a high-level finding without specific construct names passes untouched."""
    py_file = tmp_path / "app.py"
    py_file.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")

    finding = Finding(
        title="Architecture warning",
        location=f"{py_file}:1",
        description="Module architecture should adhere to domain separation guidelines.",
    )
    validated = validate_construct_location(finding, py_file)

    assert (
        validated.location,
        validated.relocated_from,
        validated.status,
    ) == (
        f"{py_file}:1",
        None,
        "UNVERIFIED",
    )


def test_non_python_file_passes_untouched(tmp_path: Path) -> None:
    """Verify that non-Python files pass construct validation untouched."""
    yaml_file = tmp_path / "deploy.yaml"
    yaml_file.write_text("apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8")

    finding = Finding(
        title="Missing replica count in `Deployment`",
        location=f"{yaml_file}:1",
        description="Deployment should define replica count.",
    )
    validated = validate_construct_location(finding, yaml_file)

    assert (
        validated.location,
        validated.relocated_from,
        validated.status,
    ) == (
        f"{yaml_file}:1",
        None,
        "UNVERIFIED",
    )


def test_syntax_error_file_passes_untouched(tmp_path: Path) -> None:
    """Verify that files with syntax errors pass construct validation without crashing."""
    broken_file = tmp_path / "broken.py"
    broken_file.write_text("def broken_func(\n", encoding="utf-8")

    finding = Finding(
        title="Defect in `broken_func`",
        location=f"{broken_file}:1",
        description="Function is incomplete.",
    )
    validated = validate_construct_location(finding, broken_file)

    assert (
        validated.location,
        validated.relocated_from,
        validated.status,
    ) == (
        f"{broken_file}:1",
        None,
        "UNVERIFIED",
    )


def test_deterministic_pre_verification_integration(tmp_path: Path) -> None:
    """Verify that _deterministic_pre_verification applies construct location relocation and invalidation."""
    py_file = tmp_path / "app.py"
    py_file.write_text(SAMPLE_PYTHON_CODE, encoding="utf-8")

    # 1. Relocation test through pre_verification
    reloc_finding = Finding(
        title="Unbounded timeout on `requests.get`",
        location="app.py:2",
        description="Call `requests.get` has no timeout.",
    )
    res_reloc = _deterministic_pre_verification(
        reloc_finding, repo_root=tmp_path, target_dir=tmp_path
    )
    assert (
        res_reloc.location,
        res_reloc.relocated_from,
        res_reloc.status,
    ) == (
        "app.py:10",
        "app.py:2",
        "UNVERIFIED",
    )

    # 2. Invalidation test through pre_verification
    absent_finding = Finding(
        title="Insecure deserialization via `yaml.unsafe_load`",
        location="app.py:5",
        description="Call to `yaml.unsafe_load` allows code execution.",
    )
    res_absent = _deterministic_pre_verification(
        absent_finding, repo_root=tmp_path, target_dir=tmp_path
    )
    assert (
        res_absent.status,
        res_absent.verified,
        res_absent.reportable,
    ) == (
        "INVALIDATED",
        False,
        False,
    )


def test_merge_two_findings_preserves_relocated_from() -> None:
    """Verify that merging findings preserves relocated_from attribute."""
    f1 = Finding(
        title="Vulnerability A",
        location="app.py:10",
        relocated_from="app.py:1",
        severity="HIGH",
    )
    f2 = Finding(
        title="Vulnerability A",
        location="app.py:10",
        severity="MEDIUM",
    )
    merged = _merge_two_findings(f1, f2)
    assert (merged.location, merged.relocated_from, merged.severity) == (
        "app.py:10",
        "app.py:1",
        "HIGH",
    )
