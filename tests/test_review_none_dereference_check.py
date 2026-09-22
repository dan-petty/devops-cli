"""Test suite for invalidating impossible None-dereference findings during verification."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review.verification import (
    _check_none_dereference_hallucination,
    _module_typechecks_clean,
)
from devops_cli.ai.review_schema import Finding


@pytest.fixture(autouse=True)
def clear_typecheck_cache() -> None:
    """The probe is cached on path and mtime; tests must not share verdicts."""
    _module_typechecks_clean.cache_clear()


def _finding(title: str, description: str = "", location: str = "a.py:1-2") -> Finding:
    """Build a candidate finding."""
    return Finding(severity="CRITICAL", location=location, title=title, description=description)


def _typecheck(clean: bool) -> Any:  # type: ignore[valid-type]
    """Patch the type-check probe to report a verdict."""
    return patch("devops_cli.ai.review.verification._module_typechecks_clean", return_value=clean)


@pytest.fixture
def module(tmp_path: Path) -> Path:
    """Provide a Python file for the finding to cite."""
    path = tmp_path / "module.py"
    path.write_text("value: str = ''\n", encoding="utf-8")
    return path


# =============================================================================
# Invalidation
# =============================================================================


def test_a_none_dereference_claim_is_invalidated_when_the_module_typechecks(
    module: Path,
) -> None:
    """The defect this exists for: two such findings shipped as VERIFIED at 0.94 confidence.

    `mypy --strict` rejects exactly this defect, so a module that passes cannot contain it.
    """
    finding = _finding("AttributeError when dashboard.uid is None in _check_identity")
    with _typecheck(True):
        result = _check_none_dereference_hallucination(finding, module)
    assert result is not None
    assert (result.status, result.verified, result.reportable) == ("INVALIDATED", False, False)


def test_the_invalidation_reason_names_the_oracle(module: Path) -> None:
    """A reader should be able to re-run the check that dismissed their finding."""
    with _typecheck(True):
        result = _check_none_dereference_hallucination(
            _finding("NoneType has no attribute"), module
        )
    assert result is not None
    assert "mypy --strict" in result.invalidation_reason


@pytest.mark.parametrize(
    "title",
    [
        "AttributeError when panel.datasource is None",
        "NoneType object has no attribute 'strip'",
        "Possible None dereference in _check_targets",
        "Null pointer when config is none",
    ],
)
def test_each_phrasing_of_the_claim_is_recognised(title: str, module: Path) -> None:
    """Findings describe this defect several ways; recognising one spelling is not enough."""
    with _typecheck(True):
        assert _check_none_dereference_hallucination(_finding(title), module) is not None


def test_the_claim_is_recognised_in_the_description(module: Path) -> None:
    """The title is often a summary; the mechanism is stated in the description."""
    finding = _finding(
        "Unsafe attribute access", "This raises AttributeError when the value is None"
    )
    with _typecheck(True):
        assert _check_none_dereference_hallucination(finding, module) is not None


# =============================================================================
# Non-Interference
# =============================================================================


def test_a_module_that_does_not_typecheck_leaves_the_finding_alone(module: Path) -> None:
    """The oracle only speaks when it is clean.

    If mypy cannot check the module for any reason, nothing has been disproved and the
    finding must reach the model verifier exactly as before.
    """
    with _typecheck(False):
        assert (
            _check_none_dereference_hallucination(_finding("AttributeError on None"), module)
            is None
        )


def test_an_unrelated_finding_is_untouched(module: Path) -> None:
    """A clean type check says nothing about SQL injection or a missing bound."""
    with _typecheck(True):
        result = _check_none_dereference_hallucination(
            _finding("SQL injection via unparameterised query"), module
        )
    assert result is None


def test_a_non_python_file_is_untouched(tmp_path: Path) -> None:
    """mypy decides nothing about YAML."""
    path = tmp_path / "workflow.yml"
    path.write_text("on: push\n", encoding="utf-8")
    with _typecheck(True):
        assert (
            _check_none_dereference_hallucination(_finding("AttributeError on None"), path) is None
        )


def test_a_missing_file_is_untouched(tmp_path: Path) -> None:
    """A finding citing a file that does not exist is a different problem."""
    with _typecheck(True):
        result = _check_none_dereference_hallucination(
            _finding("AttributeError on None"), tmp_path / "absent.py"
        )
    assert result is None


# =============================================================================
# The Probe
# =============================================================================


def test_the_probe_reports_clean_only_on_success() -> None:
    """A non-zero exit means mypy found something, so nothing is disproved."""
    with patch("devops_cli.core.process.run_subprocess", return_value=MagicMock(returncode=1)):
        assert _module_typechecks_clean("/tmp/a.py", 1.0) is False


def test_the_probe_treats_its_own_failure_as_inconclusive() -> None:
    """A missing or hung mypy must not silently invalidate real findings."""
    with patch("devops_cli.core.process.run_subprocess", side_effect=OSError("mypy missing")):
        assert _module_typechecks_clean("/tmp/b.py", 1.0) is False


def test_the_probe_is_cached_per_file_and_modification_time() -> None:
    """Verification examines many findings against the same few files.

    Type checking once per finding would dominate the run.
    """
    with patch(
        "devops_cli.core.process.run_subprocess", return_value=MagicMock(returncode=0)
    ) as run:
        _module_typechecks_clean("/tmp/c.py", 5.0)
        _module_typechecks_clean("/tmp/c.py", 5.0)
        _module_typechecks_clean("/tmp/c.py", 6.0)
    assert run.call_count == 2


def test_the_checker_is_registered_in_the_verification_pipeline() -> None:
    """An unregistered check invalidates nothing.

    Asserted because the whole point is that it runs before the model verifier.
    """
    import inspect

    from devops_cli.ai.review import verification

    source = inspect.getsource(verification._check_code_file_hallucinations)
    assert "_check_none_dereference_hallucination" in source
