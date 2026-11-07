"""`extract_function_signature` and `extract_class_signature`: what a signature records (#1329)."""

from __future__ import annotations

from typing import Any

from devops_cli.ai.library.introspector import extract_class_signature, extract_function_signature


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


def test_a_function_signature_lists_its_parameters_in_order() -> None:
    sig = extract_function_signature(sample_function)

    assert (
        sig.name,
        [p.name for p in sig.parameters],
        sig.return_annotation in ("list[str]", "typing.List[str]"),
        "Sample docstring headline." in (sig.docstring or ""),
    ) == ("sample_function", ["req_arg", "opt_arg", "args", "kw_only", "kwargs"], True, True)


def test_a_parameter_records_whether_it_has_a_default() -> None:
    required, optional = extract_function_signature(sample_function).parameters[:2]

    assert (
        (required.is_required, required.has_default),
        (optional.is_required, optional.has_default, optional.default),
    ) == ((True, False), (False, True, "42"))


def test_an_async_function_is_marked_async() -> None:
    sig = extract_function_signature(sample_async_func)

    assert (sig.name, sig.is_async, [p.default for p in sig.parameters]) == (
        "sample_async_func",
        True,
        ["1.0"],
    )


def test_a_class_signature_records_bases_methods_and_properties() -> None:
    sig = extract_class_signature(SampleClass)

    assert (
        sig.name,
        "Sample class docstring." in (sig.docstring or ""),
        "SampleBase" in sig.bases,
        "__init__" in sig.methods,
        "label" in sig.properties,
        sig.methods["compute"].parameters[-1].default,
    ) == ("SampleClass", True, True, True, True, "2.0")
