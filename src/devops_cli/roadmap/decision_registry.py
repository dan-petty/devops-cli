"""The registry of decision points (ADR 0020): one entry for each point of a workflow.

Each point is defined beside its workflow and imports `decision_point`, so the registry is a module
of its own that imports the points. The points import pydantic_ai, so the settings check the keys
and the modes of `roadmap.decisions` against the light table of `decision_table` (#4501), and a test
keeps that table equal to `REGISTRY`. The catalogue of ADR 0020 gives the points that come later,
each with its own item, and each one also goes into the table.
"""

from __future__ import annotations

from typing import Final

from devops_cli.roadmap.decision_point import Registry
from devops_cli.roadmap.stage.stage_jev_screen import VERIFY_SCREEN

REGISTRY: Final[Registry] = Registry((VERIFY_SCREEN,))

__all__ = ["REGISTRY"]
