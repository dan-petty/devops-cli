"""The plan that passes the gates of the stage job, kept as one file for each item (#4064).

The file holds the `StageProposal` and the `StageRequest` of the plan, under a key of the input:
the item number, the title, the hashes of the body, the model name, the toolset name and the prompt
version. A rerun or `--confirm` with the same key reads the file and sends the planner no request;
the gates and the review run again on the current commit. The staged commit is no part of the key.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict, ValidationError

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.lang import MESSAGES
from devops_cli.output.file_writer import write_json_file
from devops_cli.roadmap.body_hash import body_hashes
from devops_cli.roadmap.stage.stage_change import CHANGE_TASK, StageProposal
from devops_cli.roadmap.stage.stage_request import StageRequest
from devops_cli.roadmap.stage.stage_split import SPLIT_TASK
from devops_cli.roadmap.stage.stage_toolbox import EXTENDED_TOOLS_TASK, TOOLS_TASK

if TYPE_CHECKING:
    from pathlib import Path

# The prompts of the planner. The version is the hash of their texts, because the code has no other
# version of a prompt.
_PROMPTS: Final[tuple[str, ...]] = (CHANGE_TASK, SPLIT_TASK, TOOLS_TASK)
_STAGE_DIRECTORY: Final[str] = "stage"


class StagePlanRecord(BaseModel):
    """A plan that passed the gates, with the request that the gates read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    proposal: StageProposal
    request: StageRequest


def _digest(parts: list[Any]) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()


def prompt_version(toolset: str) -> str:
    """The version of the prompts of the planner: the sha256 of their texts, with the text of the
    extended tools for the toolset `extended`."""
    names = (*_PROMPTS, EXTENDED_TOOLS_TASK) if toolset == "extended" else _PROMPTS
    return _digest([load_task_prompt(name) for name in names])


def plan_key(
    *, number: int, title: str, body: str, model: str, toolset: str, prompt_version: str
) -> str:
    """The key of a plan: the sha256 of the item number, the title, the two hashes of the body (the
    text of a person and the refine section), the model name, the toolset name and the prompt
    version."""
    outside, inside = body_hashes(body)
    return _digest([number, title, outside, inside, model, toolset, prompt_version])


def plan_record_path(repo: str, number: int, data_dir: Path | str | None = None) -> Path:
    """The file of the plan of item `number`: `roadmap/stage/<owner>/<repo>/<number>.json` under
    the data directory, on the volume that the Service keeps its other files."""
    from devops_cli.roadmap.run import service_state_dir

    owner, name = repo.split("/", 1)
    return service_state_dir(data_dir) / _STAGE_DIRECTORY / owner / name / f"{number}.json"


def _unreadable(path: Path, reason: str) -> RoadmapStageError:
    return RoadmapStageError(
        MESSAGES.roadmap.stage_plan_record_unreadable.format(
            path=path, reason=reason.splitlines()[0][:200]
        ),
        details={"path": str(path)[:256]},
    )


def read_plan_record(path: Path, key: str) -> StagePlanRecord | None:
    """The plan in `path` when its key is `key`, else None. The key is read first: a file of
    another key is a miss whatever else it holds, so a change of the schema does not fail an item
    whose input changed. A file that is no JSON object with a text `key`, or one of this key that
    does not match the record, raises `RoadmapStageError` that names the file."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _unreadable(path, str(exc)) from exc
    if not isinstance(data, dict) or not isinstance(data.get("key"), str):
        raise _unreadable(path, "it holds no JSON object with a key")
    if data["key"] != key:
        return None
    try:
        return StagePlanRecord.model_validate(data)
    except ValidationError as exc:
        raise _unreadable(path, str(exc)) from exc


def write_plan_record(path: Path, record: StagePlanRecord) -> None:
    """Write the plan atomically, so a stop of the job leaves the old file or the new one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_file(path, record.model_dump(mode="json"), indent=2, atomic=True)


def delete_plan_record(path: Path) -> None:
    """Delete the file of a plan; a file that is not there is not an error."""
    path.unlink(missing_ok=True)
