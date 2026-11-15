"""Record the constants that a plan cites in the facts of its stage eval case (#3390).

The replay of the golden set reads `facts.json` of each case and no git, so a gate that compares a
number of the plan with the staged tree needs the value of the constant at the base commit of the
case. This module reads that value with `staged_constants`, the reader that the stage job uses, and
writes it into the `constants` key of the facts file, beside the other keys of the file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from pydantic import ValidationError

from devops_cli.exceptions import ConfigurationError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage.stage_change import StageProposal, plan_texts
from devops_cli.roadmap.stage.stage_constants import candidate_names, staged_constants
from devops_cli.roadmap.stage.stage_eval_cases import StageCase

# The facts file of a case, which `load_cases` reads beside `case.json`, `issue.txt` and `plan.json`.
_FACTS_FILE: Final[str] = "facts.json"


def record_constants(case: StageCase, source: Path) -> tuple[tuple[str, int], ...]:
    """The name and the value of each constant that the plan of `case` cites, read at the base
    commit of the case in `source`, sorted by name. A plan that the schema refuses raises
    `ConfigurationError` that names the case."""
    try:
        proposal = StageProposal.model_validate(case.plan)
    except ValidationError as exc:
        raise ConfigurationError(
            MESSAGES.roadmap.stage_eval_bad_case.format(name=case.name, reason=exc),
            details={"case": case.name},
        ) from exc
    names = candidate_names(plan_texts(proposal))
    return tuple(sorted(staged_constants(source, case.base_commit, names).items()))


def write_constants(folder: Path, constants: tuple[tuple[str, int], ...]) -> Path:
    """Write `constants` into the `constants` key of the `facts.json` of the case in `folder`, and
    keep every other key, its value and its order. It returns the path of the file."""
    path = folder / _FACTS_FILE
    facts: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    facts["constants"] = [list(pair) for pair in constants]
    path.write_text(json.dumps(facts, indent=1) + "\n", encoding="utf-8")
    return path


__all__ = ["record_constants", "write_constants"]
