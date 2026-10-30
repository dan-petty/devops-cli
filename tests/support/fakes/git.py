"""The git program, faked at the process runner, and the `git_fake` fixture that installs the
fake (#2146, ADR 0007).

Every start of git in `src/` goes through the process runner (`run_subprocess`), so `GitFake` is a
`ProcessFake` that answers a `git` command from a transcript and starts nothing. A transcript is
the record of one scenario of `tests/support/git_scenarios.py` (`tests/fixtures/git/<name>.json`),
made with the real git by `tests/support/git_recording.py`. `replay` loads the transcripts a test
needs. The directory of the test stands in for `{root}`, so the repositories of a scenario are the
same names under `tmp_path`.

A command is found by its arguments and directory. When a transcript holds the same command more
than once, the fake answers the first call with the first record, the second call with the second,
and the last one again after that, for a command whose answer changes between two calls. A git
command with no record fails the test and names the command, so a change to the commands that the
code starts fails here until the transcripts are recorded again. A test may script an answer
(`answer`) for a failure that a recording cannot hold, such as a git that cannot start. The scripted
answer wins over a record. Every other program is answered as `ProcessFake` answers it.

While `git_fake` is installed, the test cannot start a real git: the fixture refuses it, so the
`git` fixture or a direct `subprocess` call in the same test fails.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from devops_cli.core.process import reset_process_runner, set_process_runner
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.git_recording import load_transcript
from tests.support.git_scenarios import ROOT_MARK

_PROGRAM = "git"
_Key = tuple[tuple[str, ...], str | None]


class GitFake(ProcessFake):
    """A process fake whose `git` commands are answered from transcripts."""

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root
        self.loaded: list[str] = []
        self._records: dict[_Key, list[dict[str, Any]]] = {}
        self._served: dict[_Key, int] = {}

    def replay(self, *scenarios: str) -> None:
        """Load the transcripts of `scenarios`."""
        for name in scenarios:
            for record in load_transcript(name)["exchanges"]:
                key = (tuple(record["argv"]), record["cwd"])
                self._records.setdefault(key, []).append(record)
            self.loaded.append(name)

    def _marked(self, text: str) -> str:
        """`text`, with the root of the test written as the placeholder."""
        return text.replace(str(self.root.resolve()), ROOT_MARK).replace(str(self.root), ROOT_MARK)

    def _key(self, call: ProcessCall) -> _Key:
        """What a record is found by: the arguments and the directory, with the root as the
        placeholder."""
        cwd = self._marked(str(call.cwd)) if call.cwd is not None else None
        return tuple(self._marked(word) for word in call.argv), cwd

    def _match_answer(self, call: ProcessCall) -> ProcessAnswer:
        if not call.argv or Path(call.argv[0]).name != _PROGRAM:
            return super()._match_answer(call)
        for matches, scripted in reversed(self._answers):
            if matches(call):
                return scripted
        key = self._key(call)
        records = self._records.get(key)
        if records is None:
            pytest.fail(
                f"no record of `{' '.join(key[0])}` in {key[1]} for the scenarios "
                f"{self.loaded or 'loaded'}: load its scenario with `replay`, or record the real "
                "git again (tests/support/git_recording.py)",
                pytrace=False,
            )
        served = self._served.get(key, 0)
        self._served[key] = served + 1
        record = records[min(served, len(records) - 1)]
        return ProcessAnswer(
            returncode=record["returncode"],
            stdout=record["stdout"].replace(ROOT_MARK, str(self.root)),
            stderr=record["stderr"].replace(ROOT_MARK, str(self.root)),
        )


@pytest.fixture
def git_fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[GitFake]:
    """The git edge, faked for every git command that the code under test starts (ADR 0007, #2146).

    Installs a `GitFake` into the process runner seam, with `tmp_path` as `{root}`, and refuses a
    real git for the rest of the test.
    """
    fake = GitFake(tmp_path)
    real_init = subprocess.Popen.__init__

    def refusing_init(self: subprocess.Popen[Any], args: Any, *rest: Any, **kwargs: Any) -> None:
        words = [args] if isinstance(args, (str, bytes)) else list(args or [])
        if words and Path(str(words[0])).name == _PROGRAM:
            pytest.fail(
                "a test with git_fake started a real git: "
                f"{' '.join(str(word) for word in words)[:256]}",
                pytrace=False,
            )
        real_init(self, args, *rest, **kwargs)

    monkeypatch.setattr(subprocess.Popen, "__init__", refusing_init)
    set_process_runner(fake)
    try:
        yield fake
    finally:
        reset_process_runner()
