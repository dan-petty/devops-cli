"""Fakes of the external edges tests stand in for: one module per edge, each with the contract
suite that holds it to the real edge's behaviour (#1312).
"""

from __future__ import annotations

from tests.support.fakes.model import (
    ModelAnswer,
    ModelCall,
    ModelFake,
    deterministic_embedding,
)

__all__ = [
    "ModelAnswer",
    "ModelCall",
    "ModelFake",
    "deterministic_embedding",
]
