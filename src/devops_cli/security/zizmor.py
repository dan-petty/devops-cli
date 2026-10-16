"""zizmor, the static analyser for GitHub Actions, over a repository's workflows (#861).

zizmor runs offline and writes its findings as JSON. Each finding names its audit (`ident`), its
severity and confidence, and several locations, of which the one zizmor marks `Primary` is where
the finding is. A finding ignored by an in-source `# zizmor: ignore[...]` comment is left out.
The audits in `CONST_ZIZMOR_BLOCKING_RULES` fail the gate; the others are reported.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from devops_cli.ai.review_schema import DefectClass, Finding
from devops_cli.config.commands import BIN_ZIZMOR, build_zizmor_cmd
from devops_cli.config.constants import CONST_ZIZMOR_BLOCKING_RULES, CONST_ZIZMOR_SEVERITIES
from devops_cli.config.defaults import DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.state import is_dry_run
from devops_cli.exceptions.tools import ToolExecutionError
from devops_cli.lang import MESSAGES


class ZizmorFinding(BaseModel):
    """One zizmor finding at its primary location."""

    model_config = ConfigDict(frozen=True)

    rule: str
    description: str
    severity: str
    confidence: str
    path: str
    line: int | None
    url: str = ""

    @property
    def location(self) -> str:
        """`path:line`, or the path alone when zizmor gave no line."""
        return f"{self.path}:{self.line}" if self.line is not None else self.path

    @property
    def blocks(self) -> bool:
        """Whether the finding's audit fails the gate."""
        return self.rule in CONST_ZIZMOR_BLOCKING_RULES

    def as_finding(self) -> Finding:
        """The finding as the scan commands show one."""
        return Finding(
            severity=CONST_ZIZMOR_SEVERITIES.get(self.severity, "INFO"),
            location=self.location,
            title=f"[ZIZMOR:{self.rule}] {self.description}",
            description=f"zizmor {self.rule} ({self.confidence} confidence) at {self.location}",
            fix=self.url or "-",
            confidence_score=None,
            category=DefectClass.SUPPLY_CHAIN.value,
        )


def _primary(locations: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    """The location zizmor marks `Primary`, else the first."""
    return next(
        (loc for loc in locations if loc.get("symbolic", {}).get("kind") == "Primary"),
        locations[0] if locations else {},
    )


def _parse_one(item: Mapping[str, Any]) -> ZizmorFinding:
    location = _primary(item.get("locations") or [])
    key = location.get("symbolic", {}).get("key", {}).get("Local", {})
    start = location.get("concrete", {}).get("location", {}).get("start_point")
    determinations = item.get("determinations") or {}
    return ZizmorFinding(
        rule=str(item.get("ident", "")),
        description=str(item.get("desc", "")),
        severity=str(determinations.get("severity", "")),
        confidence=str(determinations.get("confidence", "")),
        path=str(key.get("verbatim_path", "")),
        line=int(start["row"]) + 1 if start else None,
        url=str(item.get("url", "")),
    )


def parse_zizmor_json(data: Sequence[Mapping[str, Any]]) -> list[ZizmorFinding]:
    """Every finding zizmor did not ignore, at its primary location."""
    return [_parse_one(item) for item in data if not item.get("ignored")]


def run_zizmor(target: Path) -> list[ZizmorFinding]:
    """Audit the workflows under `target` offline. A run that fails, or writes no JSON, raises:
    it is never read as a clean result."""
    if is_dry_run():
        return []
    proc = run_subprocess(
        build_zizmor_cmd(target), quiet=True, timeout=DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS
    )
    detail = (proc.stderr or proc.stdout or "").strip()[:256]
    if proc.returncode != 0:
        raise ToolExecutionError(
            MESSAGES.scan.zizmor_failed.format(code=proc.returncode, detail=detail),
            tool_name=BIN_ZIZMOR,
            details={"exit_code": proc.returncode},
        )
    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise ToolExecutionError(
            MESSAGES.scan.zizmor_failed.format(code=proc.returncode, detail=detail),
            tool_name=BIN_ZIZMOR,
        ) from exc
    return parse_zizmor_json(data if isinstance(data, list) else [])


__all__ = ["ZizmorFinding", "parse_zizmor_json", "run_zizmor"]
