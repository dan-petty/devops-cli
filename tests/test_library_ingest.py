"""Unit tests for dynamic package introspection and library contract extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.ai.library.introspector import (
    PackageIntrospector,
    extract_class_signature,
    extract_function_signature,
)
from devops_cli.commands.ai import app as ai_app
from devops_cli.exceptions.ai import LibraryNotFoundError
from devops_cli.models.library import (
    FunctionSignature,
    LibraryContract,
    ModuleContract,
    ParameterSignature,
)

runner = CliRunner()


# --- Sample targets for introspection tests ---


def sample_function(
    req_arg: str,
    opt_arg: int = 42,
    *args: Any,
    kw_only: bool = True,
    **kwargs: Any,
) -> list[str]:
    """Sample docstring headline.

    Longer description of sample function.
    """
    return [req_arg] * opt_arg


async def sample_async_func(x: float = 1.0) -> float:
    """Async sample."""
    return x * 2.0


class SampleBase:
    """Base class doc."""

    base_field: int = 1


class SampleClass(SampleBase):
    """Sample class docstring."""

    def __init__(self, name: str) -> None:
        self.name = name

    def compute(self, factor: float = 2.0) -> float:
        """Compute docstring."""
        return factor * 10

    @property
    def label(self) -> str:
        return self.name


# --- Unit Tests ---


def test_parameter_signature_model() -> None:
    param = ParameterSignature(
        name="timeout",
        annotation="float",
        default="30.0",
        has_default=True,
        kind="KEYWORD_ONLY",
        is_required=False,
    )
    assert param.name == "timeout"
    assert param.has_default is True
    assert param.is_required is False
    assert param.kind == "KEYWORD_ONLY"


def test_function_signature_model() -> None:
    sig = FunctionSignature(
        name="fetch",
        qualname="pkg.module.fetch",
        parameters=[ParameterSignature(name="url", annotation="str")],
        return_annotation="Response",
        docstring="Fetch a URL.",
        is_async=True,
    )
    assert sig.name == "fetch"
    assert sig.is_async is True
    assert len(sig.parameters) == 1
    assert sig.parameters[0].name == "url"


def test_extract_function_signature() -> None:
    sig = extract_function_signature(sample_function)
    assert sig.name == "sample_function"
    assert "Sample docstring headline." in (sig.docstring or "")
    assert sig.return_annotation in ("list[str]", "typing.List[str]")

    param_names = [p.name for p in sig.parameters]
    assert param_names == ["req_arg", "opt_arg", "args", "kw_only", "kwargs"]

    req_p = sig.parameters[0]
    assert req_p.name == "req_arg"
    assert req_p.is_required is True
    assert req_p.has_default is False

    opt_p = sig.parameters[1]
    assert opt_p.name == "opt_arg"
    assert opt_p.has_default is True
    assert opt_p.default == "42"
    assert opt_p.is_required is False


def test_extract_async_function_signature() -> None:
    sig = extract_function_signature(sample_async_func)
    assert sig.name == "sample_async_func"
    assert sig.is_async is True
    assert len(sig.parameters) == 1
    assert sig.parameters[0].default == "1.0"


def test_extract_class_signature() -> None:
    sig = extract_class_signature(SampleClass)
    assert sig.name == "SampleClass"
    assert "Sample class docstring." in (sig.docstring or "")
    assert "SampleBase" in sig.bases
    assert "compute" in sig.methods
    assert "label" in sig.properties

    method_sig = sig.methods["compute"]
    assert method_sig.name == "compute"
    assert len(method_sig.parameters) >= 1


def test_library_contract_serialization_roundtrip(tmp_path: Path) -> None:
    contract = LibraryContract(
        package_name="test-pkg",
        version="1.2.3",
        timestamp="2026-09-09T16:00:00Z",
        modules={
            "test_pkg": ModuleContract(
                name="test_pkg",
                all_exports=["sample_function"],
                functions={"sample_function": extract_function_signature(sample_function)},
                classes={"SampleClass": extract_class_signature(SampleClass)},
            )
        },
        symbols_index={
            "test_pkg.sample_function": "function",
            "test_pkg.SampleClass": "class",
            "test_pkg.SampleClass.compute": "method",
        },
        total_modules=1,
        total_functions=1,
        total_classes=1,
    )

    introspector = PackageIntrospector()
    out_file = introspector.save_to_dir(contract, tmp_path)
    assert out_file.exists()
    assert out_file.name == "test-pkg.json"

    loaded = introspector.load_from_dir("test-pkg", tmp_path)
    assert loaded is not None
    assert loaded.package_name == "test-pkg"
    assert loaded.version == "1.2.3"
    assert "test_pkg" in loaded.modules
    assert "sample_function" in loaded.modules["test_pkg"].functions
    assert "SampleClass" in loaded.modules["test_pkg"].classes


def test_introspect_package_not_found() -> None:
    introspector = PackageIntrospector()
    with pytest.raises(LibraryNotFoundError, match="nonexistent_pkg_xyz_123"):
        introspector.introspect_package("nonexistent_pkg_xyz_123")


def test_introspect_installed_package() -> None:
    introspector = PackageIntrospector()
    contract = introspector.introspect_package("pydantic", max_depth=1)
    assert contract.package_name == "pydantic"
    assert contract.total_modules >= 1
    assert "BaseModel" in contract.symbols_index or contract.total_classes > 0


def test_cli_ai_ingest_library(tmp_path: Path) -> None:
    result = runner.invoke(
        ai_app,
        ["ingest", "library", "pydantic", "--max-depth", "1", "--output-dir", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "pydantic" in result.output
    saved_file = tmp_path / "pydantic.json"
    assert saved_file.exists()


def test_cli_ai_ingest_library_json_format(tmp_path: Path) -> None:
    result = runner.invoke(
        ai_app,
        [
            "ingest",
            "library",
            "pydantic",
            "--max-depth",
            "1",
            "--output-dir",
            str(tmp_path),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    assert '"package_name": "pydantic"' in result.output


def test_cli_ai_ingest_library_failure() -> None:
    result = runner.invoke(
        ai_app,
        ["ingest", "library", "nonexistent_pkg_xyz_999"],
    )
    assert result.exit_code != 0
