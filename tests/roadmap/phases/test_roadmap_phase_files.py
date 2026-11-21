"""The run folder of a phased step and the read of an agent output as data (#6601).

`publish` holds the App key and reads what the agent phase wrote. A link, a FIFO, a file over its
limit or a folder that is a link must not reach a read that follows it or blocks on it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from devops_cli.exceptions.roadmap import PhaseOutputError
from devops_cli.roadmap.phases.files import (
    AgentOutcome,
    OutcomeKind,
    RunFolders,
    read_outcome,
    read_output,
    write_json,
)

NAME = "outcome.json"


def test_an_output_of_the_agent_phase_is_read_as_bytes(tmp_path: Path) -> None:
    folders = RunFolders(tmp_path).make()
    folders.make_out()
    (folders.out / NAME).write_bytes(b"{}")

    assert read_output(folders, NAME, limit=10) == b"{}"


@pytest.mark.parametrize(
    ("plant", "reason"),
    [
        ("link", "Cannot open the file"),
        ("fifo", "not a regular file"),
        ("large", "more than 10 bytes"),
        ("linked-folder", "not a plain folder"),
        ("missing", "Cannot open the file"),
    ],
)
def test_publish_refuses_an_output_that_is_not_a_plain_file_in_a_plain_folder(
    tmp_path: Path, plant: str, reason: str
) -> None:
    """A link to `/proc/self/environ` would give the environment of `publish`, a FIFO would hold
    the read, and a folder that is a link would point the read at another file (#3702)."""
    folders = RunFolders(tmp_path / "run").make()
    target = folders.make_out() / NAME
    if plant == "link":
        target.symlink_to("/proc/self/environ")
    elif plant == "fifo":
        os.mkfifo(target)
    elif plant == "large":
        target.write_bytes(b"x" * 11)
    elif plant == "linked-folder":
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / NAME).write_bytes(b"{}")
        folders.out.rmdir()
        folders.out.symlink_to(elsewhere, target_is_directory=True)

    with pytest.raises(PhaseOutputError, match=reason):
        read_output(folders, NAME, limit=10)


def test_the_outcome_is_read_with_its_model_and_refuses_another_key(tmp_path: Path) -> None:
    """`publish` takes the enums and the numbers of the outcome; text that is not of the model
    stops the read."""
    folders = RunFolders(tmp_path).make()
    write_json(folders.make_out() / NAME, AgentOutcome(kind=OutcomeKind.DONE, result="repaired"))

    read = read_outcome(folders)
    (folders.out / NAME).write_text('{"kind": "done", "result": "repaired", "token": "x"}')

    assert (read.kind, read.result) == (OutcomeKind.DONE, "repaired")
    with pytest.raises(PhaseOutputError, match="not of its model"):
        read_outcome(folders)
