"""The recorder of the git transcripts runs the real git the same way on every host (#2146)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.support.git_recording import (
    RecordingRunner,
    load_transcript,
    record_scenario,
    render,
)
from tests.support.git_scenarios import Workspace


def test_the_recording_reads_no_git_configuration_file_of_the_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A transcript holds what git does with no configuration, so a runner whose user or system
    file sets `pull.ff` or `core.*` records the same text as any other host."""
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text("[pull]\n\tff = only\n[core]\n\tautocrlf = true\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    runner = RecordingRunner(Workspace(tmp_path / "ws", recording=True))
    (tmp_path / "ws").mkdir()

    listed = runner.run(["git", "config", "--list", "--show-scope"], cwd=tmp_path / "ws")

    assert [
        line
        for line in listed.stdout.splitlines()
        if line.startswith(("global", "system", "pull.", "core.autocrlf"))
    ] == []


def test_the_code_runs_with_no_git_configuration_of_the_host(tmp_path: Path) -> None:
    """The environment of the code's git holds `GIT_CONFIG_NOSYSTEM` at `1` and
    `GIT_CONFIG_GLOBAL` at `os.devnull`, so the code reads no host configuration and the recording
    is the same on every host (#4865)."""
    ws = Workspace(tmp_path / "ws", recording=False)

    with ws.environment():
        assert (os.environ["GIT_CONFIG_NOSYSTEM"], os.environ["GIT_CONFIG_GLOBAL"]) == (
            "1",
            os.devnull,
        )


def test_the_review_window_transcript_holds_the_complexity_fact() -> None:
    """The committed transcript of `review_window` holds `lizard.complexity` with status `ok` and
    three files in both fact lists, and no fact failed (#4865). A recording without the review
    extra would drop the `cat-file blob` exchanges and record a `skipped` fact."""
    result = load_transcript("review_window")["result"]
    lists = {"version_facts": result["version_facts"], "period_facts": result["period_facts"]}
    complexity = {
        name: [
            (fact["id"], fact["status"], fact["n"])
            for fact in facts
            if fact["id"] == "lizard.complexity"
        ]
        for name, facts in lists.items()
    }

    assert complexity == {
        "version_facts": [("lizard.complexity", "ok", 3)],
        "period_facts": [("lizard.complexity", "ok", 3)],
    }
    assert [
        (name, fact["id"])
        for name, facts in lists.items()
        for fact in facts
        if fact["status"] != "ok"
    ] == []


def test_two_recordings_of_one_scenario_are_the_same() -> None:
    """The recorder is idempotent, so a second recording of `review_window` gives the same text
    (#4865)."""
    first = render(record_scenario("review_window"))
    second = render(record_scenario("review_window"))

    assert first == second
