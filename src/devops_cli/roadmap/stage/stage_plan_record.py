"""The plan that passes the gates of the stage job, kept as one file for each item (#4064), and the
replies that the gates refuse, kept in a file beside it (#4204).

The file holds the `StageProposal` and the `StageRequest` of the plan, under a key of the input:
the item number, the title, the hashes of the body, the model name, the toolset name and the prompt
version. A rerun or `--confirm` with the same key reads the file and sends the planner no request;
the gates and the review run again on the current commit. The staged commit is no part of the key.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, Final, Self

from pydantic import BaseModel, ConfigDict, ValidationError

from devops_cli.ai.client.models import StructuredOutputValidationError
from devops_cli.ai.schema_reflection import ViolationText
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import (
    CONST_ROADMAP_STAGE_REFUSED_PROBLEM_MAX_CHARS,
    CONST_ROADMAP_STAGE_REFUSED_REPLY_MAX_BYTES,
    CONST_ROADMAP_STAGE_VIOLATIONS_SHOWN,
)
from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.lang import MESSAGES
from devops_cli.output.file_writer import write_json_file
from devops_cli.roadmap.body_hash import body_hashes
from devops_cli.roadmap.stage.stage_change import CHANGE_TASK, StageProposal
from devops_cli.roadmap.stage.stage_request import StageRequest
from devops_cli.roadmap.stage.stage_split import SPLIT_TASK
from devops_cli.roadmap.stage.stage_toolbox import (
    EXTENDED_TOOLS_TASK,
    RESEARCH_TOOLS_TASK,
    TOOLS_TASK,
)
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
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


class RefusedReply(BaseModel):
    """A reply that the checks refused, with the problem that they found. `reply` is None for a
    reply over the size bound, and `reply_bytes` is the size of its JSON text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reply: dict[str, Any] | None
    reply_bytes: int
    problem: str


class RefusedSchemaFailure(BaseModel):
    """A reply that broke the schema past its retries (#4269). It never reached the checks, so
    there is no reply to keep: the record holds the stop reason, the count of violations and the
    text of the first ones, which are masked and cut."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stop_reason: str
    count: int
    violations: list[ViolationText]

    @classmethod
    def of(cls, error: StructuredOutputValidationError) -> Self:
        """The record of the schema failure `error`, with at most
        `CONST_ROADMAP_STAGE_VIOLATIONS_SHOWN` violations."""
        return cls(
            stop_reason=error.stop_reason,
            count=error.violations,
            violations=list(error.violation_texts[:CONST_ROADMAP_STAGE_VIOLATIONS_SHOWN]),
        )


class RefusedRecord(BaseModel):
    """The refused replies of the last failed plan of an item, under the key of its input, and the
    schema failure that ended the plan when a reply broke the schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    replies: list[RefusedReply]
    schema_failure: RefusedSchemaFailure | None = None

    @classmethod
    def of(
        cls,
        key: str,
        refused: Iterable[tuple[Mapping[str, Any], str]],
        schema_failure: StructuredOutputValidationError | None = None,
    ) -> Self:
        """The record of `refused`, each a reply (the dump of the model) and its problem, and of
        `schema_failure`. The problem is masked for secrets and cut, and a reply over the byte
        bound is dropped."""
        replies: list[RefusedReply] = []
        for reply, problem in refused:
            size = len(json.dumps(reply, ensure_ascii=False, separators=(",", ":")).encode())
            kept = dict(reply) if size <= CONST_ROADMAP_STAGE_REFUSED_REPLY_MAX_BYTES else None
            replies.append(
                RefusedReply(
                    reply=kept,
                    reply_bytes=size,
                    problem=mask_secrets(problem)[:CONST_ROADMAP_STAGE_REFUSED_PROBLEM_MAX_CHARS],
                )
            )
        return cls(
            key=key,
            replies=replies,
            schema_failure=RefusedSchemaFailure.of(schema_failure) if schema_failure else None,
        )


def _digest(parts: list[Any]) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()


def prompt_version(toolset: str) -> str:
    """The version of the prompts of the planner: the sha256 of their texts, with the text of the
    extended tools for the toolset `extended` and the research tools for `research`."""
    if toolset == "research":
        names = (*_PROMPTS, EXTENDED_TOOLS_TASK, RESEARCH_TOOLS_TASK)
    elif toolset == "extended":
        names = (*_PROMPTS, EXTENDED_TOOLS_TASK)
    else:
        names = _PROMPTS
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


def refused_record_path(repo: str, number: int, data_dir: Path | str | None = None) -> Path:
    """The refused-reply file of item `number`: `<number>.refused.json` beside its plan file."""
    return plan_record_path(repo, number, data_dir).with_name(f"{number}.refused.json")


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


def write_refused_record(path: Path, record: RefusedRecord) -> None:
    """Write the refused replies atomically, so a stop of the job leaves the old file or the new
    one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_file(path, record.model_dump(mode="json"), indent=2, atomic=True)


def delete_refused_record(path: Path) -> None:
    """Delete the refused-reply file of an item; a file that is not there is not an error."""
    path.unlink(missing_ok=True)
