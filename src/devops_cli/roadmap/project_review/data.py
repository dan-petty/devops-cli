"""The data of a project review, `data.json` (#4686): its window, and each fact with its source.

A fact holds its value, its unit, the size of its sample (`n`), the reader that gave it, the
exact query, the time of the read and how the read ended. A fact that has no value says why in
`reason`. The JSON Schema of `ReviewData` is the exported schema of `data.json`, and the command
writes it beside the data as `data.schema.json`.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Final, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

from devops_cli.lang import MESSAGES

SCHEMA_VERSION: Final = 1
DATA_FILENAME: Final = "data.json"
SCHEMA_FILENAME: Final = "data.schema.json"


class WindowKind(StrEnum):
    """What the person named: two version tags, one ISO week, or two times."""

    VERSION = "version"
    WEEK = "week"
    PERIOD = "period"


class FactStatus(StrEnum):
    """How the read of a fact ended."""

    OK = "ok"
    EXPIRED = "expired"
    SKIPPED = "skipped"
    ERROR = "error"


class ReviewWindow(BaseModel):
    """The half-open window of a review: the base commit and the start time are out, and the head
    commit and the end time are in."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: WindowKind = Field(description="Two version tags, one ISO week, or two times.")
    id: str = Field(description="The id of the window, safe for a URL and a key.")
    base_sha: str = Field(description="The base commit. Its changes are out of the window.")
    head_sha: str = Field(description="The head commit. Its changes are in the window.")
    start: AwareDatetime = Field(description="The start time, in UTC. It is out of the window.")
    end: AwareDatetime = Field(description="The end time, in UTC. It is in the window.")
    previous_id: str | None = Field(
        description="The id of the window before, of the same kind and length, or null."
    )


class Fact(BaseModel):
    """One fact of the window, with where and when it was read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(description="The id of the fact, as `<source>.<name>`.")
    value: JsonValue = Field(description="The value: a number, a mapping or a list of rows.")
    unit: str = Field(description="The unit of the value.")
    n: int | None = Field(description="The number of items that give the value, or null.")
    source: str = Field(description="The reader: `git` or `lizard`.")
    query: str = Field(description="The exact command or query that the reader ran.")
    definition: str = Field(description="What the value counts.")
    read_at: AwareDatetime = Field(description="The time of the read.")
    status: FactStatus = Field(description="How the read ended.")
    reason: str = Field(default="", description="Why a fact that is not ok has no value.")

    @model_validator(mode="after")
    def _reason_when_not_ok(self) -> Self:
        if self.status is not FactStatus.OK and not self.reason:
            raise ValueError(MESSAGES.roadmap.review_fact_needs_reason.format(status=self.status))
        return self


class ReviewData(BaseModel):
    """The contents of `data.json`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(default=SCHEMA_VERSION, description="The version of this schema.")
    repo: str = Field(description="The repository, as owner/name.")
    window: ReviewWindow = Field(description="The window of the review.")
    facts: list[Fact] = Field(description="The facts, in the order of their readers.")


def write_review(data: ReviewData, folder: Path) -> Path:
    """Write `data.json` and its JSON Schema into `folder`, and give the path of `data.json`."""
    folder.mkdir(parents=True, exist_ok=True)
    schema = json.dumps(ReviewData.model_json_schema(), indent=2) + "\n"
    (folder / SCHEMA_FILENAME).write_text(schema, encoding="utf-8")
    target = folder / DATA_FILENAME
    target.write_text(data.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return target
