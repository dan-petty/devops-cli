"""Dynamic package introspection and library contract extraction.

Inspects installed Python distributions, modules, classes, and callables
to extract standardized API signatures, parameter requirements, and symbol indices.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import inspect
import pkgutil
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from devops_cli.exceptions.ai import LibraryNotFoundError
from devops_cli.models.library import (
    ClassSignature,
    FunctionSignature,
    LibraryContract,
    ModuleContract,
    ParameterSignature,
)


def _format_annotation(ann: Any) -> str:
    """Format a type annotation into a clean string representation."""
    if ann is inspect.Signature.empty or ann is inspect.Parameter.empty:
        return "Any"
    if isinstance(ann, str):
        return ann
    try:
        formatted = inspect.formatannotation(ann)
        return formatted.removeprefix("typing.")
    except Exception:
        return getattr(ann, "__name__", str(ann))


def _format_default(val: Any) -> str:
    """Format a parameter default value into its string representation."""
    try:
        return repr(val)
    except Exception:
        return str(val)


def _extract_parameter(param: inspect.Parameter) -> ParameterSignature:
    """Extract a ParameterSignature from an inspect.Parameter object."""
    has_default = param.default is not inspect.Parameter.empty
    is_var = param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    is_required = not has_default and not is_var

    return ParameterSignature(
        name=param.name,
        annotation=_format_annotation(param.annotation),
        default=None if not has_default else _format_default(param.default),
        has_default=has_default,
        kind=param.kind.name,
        is_required=is_required,
    )


def extract_function_signature(fn: Any) -> FunctionSignature:
    """Extract a standardized FunctionSignature from any callable or method."""
    name = getattr(fn, "__name__", str(fn))
    qualname = getattr(fn, "__qualname__", name)
    docstring = inspect.getdoc(fn)
    is_async = inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn)
    is_generator = inspect.isgeneratorfunction(fn) or inspect.isasyncgenfunction(fn)

    try:
        sig = inspect.signature(fn)
        ret_ann = _format_annotation(sig.return_annotation)
        params = [_extract_parameter(p) for p in sig.parameters.values()]
    except ValueError, TypeError:
        ret_ann = "Any"
        params = []

    return FunctionSignature(
        name=name,
        qualname=qualname,
        parameters=params,
        return_annotation=ret_ann,
        docstring=docstring,
        is_async=is_async,
        is_generator=is_generator,
    )


def _extract_methods_and_props(
    cls: type,
) -> tuple[dict[str, FunctionSignature], list[str]]:
    """Extract public methods and property names from a class."""
    methods: dict[str, FunctionSignature] = {}
    properties: list[str] = []

    for member_name, member_val in inspect.getmembers(cls):
        if member_name.startswith("_") and member_name != "__init__":
            continue
        if isinstance(member_val, property):
            properties.append(member_name)
        elif inspect.isfunction(member_val) or inspect.isroutine(member_val):
            try:
                methods[member_name] = extract_function_signature(member_val)
            except Exception:
                continue

    return methods, properties


def extract_class_signature(cls: type) -> ClassSignature:
    """Extract a standardized ClassSignature from a Python class definition."""
    name = cls.__name__
    qualname = getattr(cls, "__qualname__", name)
    bases = [b.__name__ for b in cls.__bases__ if b is not object]
    docstring = inspect.getdoc(cls)
    methods, properties = _extract_methods_and_props(cls)

    return ClassSignature(
        name=name,
        qualname=qualname,
        bases=bases,
        docstring=docstring,
        methods=methods,
        properties=properties,
    )


def _is_symbol_in_scope(val: Any, mod_name: str, has_exports: bool) -> bool:
    """Predicate indicating whether a symbol belongs to the module's scope."""
    return has_exports or getattr(val, "__module__", "").startswith(mod_name)


def _process_module_symbol(
    name: str,
    val: Any,
    mod_name: str,
    has_exports: bool,
    functions: dict[str, FunctionSignature],
    classes: dict[str, ClassSignature],
    constants: dict[str, str],
) -> None:
    """Classify and register a single module symbol into appropriate registry."""
    if inspect.isclass(val) and _is_symbol_in_scope(val, mod_name, has_exports):
        classes[name] = extract_class_signature(val)
    elif (inspect.isfunction(val) or inspect.isroutine(val)) and _is_symbol_in_scope(
        val, mod_name, has_exports
    ):
        functions[name] = extract_function_signature(val)
    elif name.isupper() and not callable(val):
        constants[name] = str(val)[:100]


def _extract_module_symbols(
    module: ModuleType,
) -> tuple[dict[str, FunctionSignature], dict[str, ClassSignature], dict[str, str]]:
    """Extract public functions, classes, and constants from a module."""
    mod_name = module.__name__
    all_exports = getattr(module, "__all__", None)
    names = (
        list(all_exports)
        if all_exports is not None
        else [n for n in dir(module) if not n.startswith("_")]
    )
    has_exports = all_exports is not None

    functions: dict[str, FunctionSignature] = {}
    classes: dict[str, ClassSignature] = {}
    constants: dict[str, str] = {}

    for name in names:
        val = getattr(module, name, None)
        if val is not None:
            _process_module_symbol(name, val, mod_name, has_exports, functions, classes, constants)

    return functions, classes, constants


def _discover_submodules(root_module: ModuleType, max_depth: int) -> list[ModuleType]:
    """Discover and import submodules up to max_depth."""
    if max_depth <= 0 or not hasattr(root_module, "__path__"):
        return []

    discovered: list[ModuleType] = []
    prefix = f"{root_module.__name__}."

    for _, sub_name, _ in pkgutil.iter_modules(root_module.__path__, prefix=prefix):
        depth = sub_name.count(".") - root_module.__name__.count(".")
        if depth > max_depth:
            continue
        try:
            sub_mod = importlib.import_module(sub_name)
            discovered.append(sub_mod)
        except Exception:
            continue

    return discovered


def _build_symbols_index(modules: dict[str, ModuleContract]) -> dict[str, str]:
    """Construct a fast symbol lookup index mapping qualified symbols to their kind."""
    index: dict[str, str] = {}
    for mod in modules.values():
        for fn_name in mod.functions:
            index[f"{mod.name}.{fn_name}"] = "function"
            index[fn_name] = "function"
        for cls_name, cls_sig in mod.classes.items():
            index[f"{mod.name}.{cls_name}"] = "class"
            index[cls_name] = "class"
            for m_name in cls_sig.methods:
                index[f"{mod.name}.{cls_name}.{m_name}"] = "method"
                index[f"{cls_name}.{m_name}"] = "method"
        for const_name in mod.constants:
            index[f"{mod.name}.{const_name}"] = "constant"
    return index


class PackageIntrospector:
    """Inspects installed packages to generate structured LibraryContract representations."""

    def introspect_package(
        self,
        package_name: str,
        max_depth: int = 1,
    ) -> LibraryContract:
        """Introspect an installed package distribution and extract its API contract."""
        version = self._resolve_package_version(package_name)
        root_module = self._import_root_module(package_name)

        modules_to_inspect = [root_module]
        modules_to_inspect.extend(_discover_submodules(root_module, max_depth=max_depth))

        extracted_modules: dict[str, ModuleContract] = {}
        for mod in modules_to_inspect:
            funcs, classes, consts = _extract_module_symbols(mod)
            mod_contract = ModuleContract(
                name=mod.__name__,
                docstring=inspect.getdoc(mod),
                all_exports=list(getattr(mod, "__all__", [])),
                functions=funcs,
                classes=classes,
                constants=consts,
                submodules=[
                    m.__name__
                    for m in modules_to_inspect
                    if m.__name__.startswith(f"{mod.__name__}.")
                ],
            )
            extracted_modules[mod.__name__] = mod_contract

        symbols_index = _build_symbols_index(extracted_modules)
        total_functions = sum(
            len(m.functions) + sum(len(c.methods) for c in m.classes.values())
            for m in extracted_modules.values()
        )
        total_classes = sum(len(m.classes) for m in extracted_modules.values())

        return LibraryContract(
            package_name=package_name,
            version=version,
            timestamp=datetime.now(UTC).isoformat(),
            modules=extracted_modules,
            symbols_index=symbols_index,
            total_modules=len(extracted_modules),
            total_functions=total_functions,
            total_classes=total_classes,
        )

    def _resolve_package_version(self, package_name: str) -> str:
        """Resolve installed package distribution semver version."""
        for candidate in (package_name, package_name.replace("-", "_")):
            try:
                return importlib.metadata.version(candidate)
            except importlib.metadata.PackageNotFoundError:
                continue
        return "unknown"

    def _import_root_module(self, package_name: str) -> ModuleType:
        """Import root module for the package distribution."""
        for candidate in (package_name, package_name.replace("-", "_")):
            try:
                return importlib.import_module(candidate)
            except ImportError, ModuleNotFoundError:
                continue
        raise LibraryNotFoundError(
            f"Package '{package_name}' not found or cannot be imported in the current environment"
        )

    def save_to_dir(self, contract: LibraryContract, output_dir: Path | str) -> Path:
        """Serialize and save LibraryContract JSON to output directory."""
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"{contract.package_name}.json"
        file_path.write_text(contract.model_dump_json(indent=2), encoding="utf-8")
        return file_path

    def load_from_dir(self, package_name: str, input_dir: Path | str) -> LibraryContract | None:
        """Load and deserialize LibraryContract from a directory if present."""
        file_path = Path(input_dir) / f"{package_name}.json"
        if not file_path.is_file():
            return None
        try:
            return LibraryContract.model_validate_json(file_path.read_text(encoding="utf-8"))
        except Exception:
            return None
