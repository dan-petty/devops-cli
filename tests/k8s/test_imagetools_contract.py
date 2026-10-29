"""The recorded `docker buildx imagetools inspect` that the fake replays is the record of the
command the image pins run, and holds both outcomes the code reads (#1994).

The real side of this contract is the recording: `tests/support/imagetools_recording.py` runs the
real tool, as an anonymous client, over `RECORDED_IMAGES`. A registry is not reachable from the
suite, so the cases here hold the record to the code instead of running the tool again.
"""

from __future__ import annotations

import json
import re
import subprocess

import pytest

from devops_cli.k8s.image_pins import inspect_command
from tests.support.fakes.imagetools import ImagetoolsFake
from tests.support.fakes.process import ProcessCall
from tests.support.imagetools_recording import RECORDED_IMAGES


def test_the_record_holds_each_recorded_image_and_no_other(imagetools: ImagetoolsFake) -> None:
    """A test resolves only an image the real tool resolved."""
    assert sorted(imagetools.runs) == sorted(RECORDED_IMAGES)


@pytest.mark.parametrize("image", RECORDED_IMAGES)
def test_each_run_is_of_the_command_the_code_builds(imagetools: ImagetoolsFake, image: str) -> None:
    """A change to the command fails here until the real tool is recorded again."""
    assert imagetools.runs[image].argv == tuple(inspect_command(image)[1:])


def test_the_record_holds_a_resolved_and_a_refused_run(imagetools: ImagetoolsFake) -> None:
    """A resolved run prints the manifest with its digest; a refused run exits 1 with one
    `ERROR:` line and prints nothing."""
    resolved = [run for run in imagetools.runs.values() if run.returncode == 0]
    refused = [run for run in imagetools.runs.values() if run.returncode != 0]
    assert (
        bool(resolved),
        all(json.loads(run.stdout)["digest"].startswith("sha256:") for run in resolved),
        bool(refused),
        all(run.stdout == "" and run.stderr.startswith("ERROR: ") for run in refused),
    ) == (True, True, True, True)


def test_the_fake_refuses_an_image_the_record_does_not_hold(imagetools: ImagetoolsFake) -> None:
    """An unrecorded image fails the test that resolves it, naming the image."""
    call = ProcessCall(argv=tuple(inspect_command("example.com/not/recorded:1")))

    with pytest.raises(AssertionError, match=re.escape("example.com/not/recorded:1")):
        imagetools.answer(call)


def test_the_fake_answers_a_recorded_image_with_its_recorded_result(
    imagetools: ImagetoolsFake,
) -> None:
    """The fake gives back the exit code, the output and the error the real tool gave."""
    image = RECORDED_IMAGES[2]
    run = imagetools.runs[image]

    answer = imagetools.answer(ProcessCall(argv=tuple(inspect_command(image))))

    assert (answer.returncode, answer.stdout, answer.stderr) == (
        run.returncode,
        run.stdout,
        run.stderr,
    )
    assert isinstance(answer, subprocess.CompletedProcess)
