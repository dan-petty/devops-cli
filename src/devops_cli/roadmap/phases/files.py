"""The run folder of a phased step, the models of the agent outputs, and their read as data (#6601).

A run has one root folder with three folders:

- `state/`: the state file that `prepare` writes and `publish` reads. The agent phase does not read
  it, and #3700 does not mount it in the agent container.
- `work/`: the clone and the inputs of the agent phase, which `prepare` writes.
- `out/`: the outputs of the agent phase: the patch, `summary.json` and `outcome.json`.

`publish` holds the App key, and the agent can write each file of the run in a run folder that
it shares with `publish`. So `read_run_file` checks the root, the folder and the file with `lstat`,
opens the file with `O_NOFOLLOW | O_NONBLOCK`, refuses a file that is not a regular file, and reads
at most the limit after `fstat`. A link to `/proc/self/environ`, a FIFO or a file over the limit
raises `PhaseOutputError`, whose message names the file and never its text (#3702). `publish` reads
the state file and each output of the agent this way. The models take enums and numbers;
each text of an output is for `publish` to mask and fence before GitHub sees it.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from devops_cli.config.constants import (
    CONST_ROADMAP_PHASE_JSON_MAX_BYTES,
    CONST_ROADMAP_PHASE_OUT_DIR,
    CONST_ROADMAP_PHASE_OUTCOME_FILE,
    CONST_ROADMAP_PHASE_STATE_DIR,
    CONST_ROADMAP_PHASE_SUMMARY_FILE,
    CONST_ROADMAP_PHASE_WORK_DIR,
)
from devops_cli.exceptions.roadmap import PhaseOutputError

# The mode of each folder of the run: only the user of the Job reads or writes it.
_FOLDER_MODE = 0o700
_OPEN_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


@dataclass(frozen=True)
class RunFolders:
    """The root folder of one run and its three folders."""

    root: Path

    @property
    def state(self) -> Path:
        return self.root / CONST_ROADMAP_PHASE_STATE_DIR

    @property
    def work(self) -> Path:
        return self.root / CONST_ROADMAP_PHASE_WORK_DIR

    @property
    def out(self) -> Path:
        return self.root / CONST_ROADMAP_PHASE_OUT_DIR

    def make(self) -> Self:
        """Make the root, `state/` and `work/`, each for the user only, and give the folders. The
        agent phase makes `out/` itself when it writes its outputs (`make_out`)."""
        for folder in (self.root, self.state, self.work):
            folder.mkdir(mode=_FOLDER_MODE, parents=True, exist_ok=True)
        return self

    def make_out(self) -> Path:
        """Make `out/` for the user only and give it. The agent can write the run folder, so the
        outputs go into a folder that is new after the sweep of the leftover processes: a link or
        a FIFO in an `out/` that is there already would turn or hold the write (#6655)."""
        try:
            self.out.mkdir(mode=_FOLDER_MODE)
        except FileExistsError:
            raise PhaseOutputError(
                "The output folder of the run is there before the outputs"
            ) from None
        return self.out


class OutcomeKind(StrEnum):
    """How the agent phase ended (#3702): `done` with a change to publish, `returned` with its
    reason, `question` for the owner, or `stopped` with its reason."""

    DONE = "done"
    RETURNED = "returned"
    QUESTION = "question"
    STOPPED = "stopped"


class OutputModel(BaseModel):
    """An output of the agent phase: frozen, and no key outside the model."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class OutcomeFile(OutputModel):
    """A file that the outcome names, with the reason: both are text of the agent."""

    path: str
    reason: str = ""


class AgentOutcome(OutputModel):
    """`outcome.json`: the kind of the end, the result and the detail as values of the enums of the
    step, the reason, the files that the outcome names, and its counts. The step checks `result`
    and `detail` against its own enums; `reason` and `files` are text that `publish` masks and
    fences."""

    kind: OutcomeKind
    result: str
    detail: str = ""
    reason: str = ""
    files: tuple[OutcomeFile, ...] = ()
    counts: dict[str, int] = Field(default_factory=dict)


class AgentSummary(OutputModel):
    """`summary.json`: the counts of the agent phase."""

    counts: dict[str, int] = Field(default_factory=dict)


def write_json(path: Path, model: BaseModel) -> None:
    """Write `model` as JSON to `path`, for the user only."""
    path.write_text(model.model_dump_json(), encoding="utf-8")
    path.chmod(0o600)


def _plain_folder(path: Path) -> None:
    try:
        held = os.lstat(path)
    except OSError as exc:
        raise PhaseOutputError(f"Cannot read the folder `{path.name}`: {exc.strerror}") from exc
    if not stat.S_ISDIR(held.st_mode):
        raise PhaseOutputError(f"The folder `{path.name}` of the run is not a plain folder")


def read_run_file(folders: RunFolders, folder: Path, name: str, *, limit: int) -> bytes:
    """The bytes of the file `name` of `folder`, a folder of the run, read as data: the root and
    `folder` must be plain folders and the file a regular file of at most `limit` bytes."""
    _plain_folder(folders.root)
    _plain_folder(folder)
    path = folder / name
    try:
        handle = os.open(path, _OPEN_FLAGS)
    except OSError as exc:
        raise PhaseOutputError(f"Cannot open the file `{name}`: {exc.strerror}") from exc
    try:
        held = os.fstat(handle)
        if not stat.S_ISREG(held.st_mode):
            raise PhaseOutputError(f"The file `{name}` is not a regular file")
        if held.st_size > limit:
            raise PhaseOutputError(f"The file `{name}` holds more than {limit} bytes")
        data = os.read(handle, limit + 1)
    finally:
        os.close(handle)
    if len(data) > limit:
        raise PhaseOutputError(f"The file `{name}` holds more than {limit} bytes")
    return data


def read_output(folders: RunFolders, name: str, *, limit: int) -> bytes:
    """The bytes of the output `name` of `out/`, read as data (`read_run_file`)."""
    return read_run_file(folders, folders.out, name, limit=limit)


def _read_model[T: OutputModel](folders: RunFolders, name: str, model: type[T]) -> T:
    data = read_output(folders, name, limit=CONST_ROADMAP_PHASE_JSON_MAX_BYTES)
    try:
        return model.model_validate_json(data)
    except ValidationError as exc:
        raise PhaseOutputError(
            f"The output `{name}` is not of its model: {exc.error_count()} error(s)"
        ) from exc


def read_outcome(folders: RunFolders) -> AgentOutcome:
    """`outcome.json` of the agent phase, read as data."""
    return _read_model(folders, CONST_ROADMAP_PHASE_OUTCOME_FILE, AgentOutcome)


def read_summary(folders: RunFolders) -> AgentSummary:
    """`summary.json` of the agent phase, read as data."""
    return _read_model(folders, CONST_ROADMAP_PHASE_SUMMARY_FILE, AgentSummary)


__all__ = [
    "AgentOutcome",
    "AgentSummary",
    "OutcomeFile",
    "OutcomeKind",
    "RunFolders",
    "read_outcome",
    "read_output",
    "read_run_file",
    "read_summary",
    "write_json",
]
