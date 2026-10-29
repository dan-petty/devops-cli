"""Fakes of the external edges tests stand in for: one module per edge, each with the contract
suite that holds it to the real edge's behaviour (#1312).
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tests.support.fakes.model import (
        ModelAnswer,
        ModelCall,
        ModelFake,
        deterministic_embedding,
    )
    from tests.support.fakes.process import (
        ProcessAnswer,
        ProcessCall,
        ProcessFake,
    )

__all__ = [
    "ModelAnswer",
    "ModelCall",
    "ModelFake",
    "ProcessAnswer",
    "ProcessCall",
    "ProcessFake",
    "deterministic_embedding",
]

_ATTR_MAP: dict[str, tuple[str, str]] = {
    "ModelAnswer": ("tests.support.fakes.model", "ModelAnswer"),
    "ModelCall": ("tests.support.fakes.model", "ModelCall"),
    "ModelFake": ("tests.support.fakes.model", "ModelFake"),
    "ProcessAnswer": ("tests.support.fakes.process", "ProcessAnswer"),
    "ProcessCall": ("tests.support.fakes.process", "ProcessCall"),
    "ProcessFake": ("tests.support.fakes.process", "ProcessFake"),
    "deterministic_embedding": ("tests.support.fakes.model", "deterministic_embedding"),
}


def __getattr__(name: str) -> Any:
    if name in _ATTR_MAP:
        mod_name, attr = _ATTR_MAP[name]
        val = getattr(importlib.import_module(mod_name), attr)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
