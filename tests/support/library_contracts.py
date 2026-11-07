"""A small library contract on disk, for the drift auditor tests (#1329)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.models.library import (
    ClassSignature,
    FunctionSignature,
    LibraryContract,
    ModuleContract,
    ParameterSignature,
)


def write_demo_contract(contracts_dir: Path, package: str = "demolib") -> LibraryContract:
    """Write the contract of `package` to `contracts_dir/<package>.json` and return it.

    The package has `compute(x, *, mode="fast")`, a deprecated `legacy_calc(val)` and a class
    `Client` with the method `connect(host, *, port=8080)`.
    """
    module = ModuleContract(
        name=package,
        functions={
            "compute": FunctionSignature(
                name="compute",
                qualname=f"{package}.compute",
                parameters=[
                    ParameterSignature(name="x", kind="POSITIONAL_OR_KEYWORD"),
                    ParameterSignature(name="mode", kind="KEYWORD_ONLY", default="'fast'"),
                ],
                return_annotation="int",
            ),
            "legacy_calc": FunctionSignature(
                name="legacy_calc",
                qualname=f"{package}.legacy_calc",
                parameters=[ParameterSignature(name="val", kind="POSITIONAL_OR_KEYWORD")],
                docstring="Deprecated: use compute instead.",
            ),
        },
        classes={
            "Client": ClassSignature(
                name="Client",
                qualname=f"{package}.Client",
                methods={
                    "connect": FunctionSignature(
                        name="connect",
                        qualname=f"{package}.Client.connect",
                        parameters=[
                            ParameterSignature(name="host", kind="POSITIONAL_OR_KEYWORD"),
                            ParameterSignature(name="port", kind="KEYWORD_ONLY", default="8080"),
                        ],
                    )
                },
            )
        },
    )
    contract = LibraryContract(
        package_name=package,
        version="1.0.0",
        timestamp="2026-09-09T00:00:00Z",
        modules={package: module},
        symbols_index={
            f"{package}.compute": "function",
            f"{package}.legacy_calc": "function",
            f"{package}.Client": "class",
            f"{package}.Client.connect": "method",
        },
        total_modules=1,
        total_functions=3,
        total_classes=1,
    )
    contracts_dir.mkdir(parents=True, exist_ok=True)
    (contracts_dir / f"{package}.json").write_text(contract.model_dump_json(indent=2))
    return contract


def write_demo_workspace(root: Path, source: str, name: str = "app.py") -> Path:
    """Write one Python file of `source` to `root/workspace` and return that directory."""
    workspace = root / "workspace"
    workspace.mkdir(exist_ok=True)
    (workspace / name).write_text(source, encoding="utf-8")
    return workspace
