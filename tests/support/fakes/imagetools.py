"""`docker buildx imagetools inspect`, faked at the process edge from the real tool's record, and
the `imagetools` fixture that installs it over `process_fake` (#1994).

The record (`tests/fixtures/imagetools_runs/recorded_runs.json`, made by
`tests/support/imagetools_recording.py`) holds the real tool's answer to the command that
`inspect_command` builds, for each image of `RECORDED_IMAGES`. The fake answers an inspect of a
recorded image with its recorded exit code, output and error, and fails the test on any other
image, naming it, so a test resolves only what the record holds. A test may script an image's
answer (`script`) for an outcome that a recording cannot hold, such as a registry's rate limit.
`calls` holds each image the fake answered, in order.

The fixture also lets `kubectl kustomize` run for real, one of kubectl's offline renderers that
the suite's floor allows, because the image pins render each Application with it.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator

import pytest

from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.imagetools_recording import RecordedRun, load_recorded_runs

_INSPECT = ("docker", "buildx", "imagetools", "inspect")
_KUSTOMIZE = ("kubectl", "kustomize")


class ImagetoolsFake:
    """The answers of `docker buildx imagetools inspect`, from the record and from a test."""

    def __init__(self, version: str, runs: dict[str, RecordedRun]) -> None:
        self.version = version
        self.runs = runs
        self.calls: list[str] = []
        self._scripted: dict[str, RecordedRun] = {}

    def script(self, image: str, *, returncode: int, stdout: str = "", stderr: str = "") -> None:
        """Answer an inspect of `image` with this result, in place of the record."""
        self._scripted[image] = RecordedRun(image, (), returncode, stdout, stderr)

    def answer(self, call: ProcessCall) -> subprocess.CompletedProcess[str]:
        """The answer to one inspect command."""
        image = call.argv[len(_INSPECT)]
        self.calls.append(image)
        run = self._scripted.get(image) or self.runs.get(image)
        if run is None:
            raise AssertionError(
                f"No recorded imagetools run for {image!r}: use a recorded image or script one."
            )
        return subprocess.CompletedProcess(list(call.argv), run.returncode, run.stdout, run.stderr)


def _real_kustomize(call: ProcessCall) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(call.argv), capture_output=True, text=True, check=False)


@pytest.fixture
def imagetools(process_fake: ProcessFake) -> Iterator[ImagetoolsFake]:
    """The image pins' process edges: the recorded resolver, and the real `kubectl kustomize`."""
    version, runs = load_recorded_runs()
    fake = ImagetoolsFake(version, runs)
    process_fake.answer(_KUSTOMIZE, ProcessAnswer(side_effect=_real_kustomize))
    process_fake.answer(_INSPECT, ProcessAnswer(side_effect=fake.answer))
    yield fake
