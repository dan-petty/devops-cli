"""Contract suite of the git edge: the code of `src/` over the process fake and over `GitFake` gives
what the real git gave, recorded in `tests/fixtures/git/` (#2146, ADR 0007).

Every transcript is replayed twice, over a `ProcessFake` that answers the recorded commands in
order and over `GitFake`. Both runs must give the recorded result, and the first must start the
recorded commands and no other. The suite starts no program: the module refuses every start of
one. The `git` row of `devops ci` records the transcripts again with the real git and fails when
one differs (`tests/support/git_recording.py`).
"""

from __future__ import annotations

import json
import socket
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from devops_cli.core.process import run_subprocess
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.git_recording import (
    committed_names,
    differences,
    host_data_in,
    load_transcript,
    transcript_path,
)
from tests.support.git_scenarios import ROOT_MARK, SCENARIOS, Workspace

SCENARIO_NAMES = sorted(SCENARIOS)


@pytest.fixture(autouse=True)
def no_program_starts(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail the test that starts a program of any name."""

    def refuse(self: subprocess.Popen[Any], args: Any, *rest: Any, **kwargs: Any) -> None:
        pytest.fail(f"the contract suite started a program: {args!r}", pytrace=False)

    monkeypatch.setattr(subprocess.Popen, "__init__", refuse)
    yield


def test_every_scenario_has_a_transcript_and_no_transcript_lacks_a_scenario() -> None:
    """The transcripts are the scenarios', so a scenario added or removed needs a recording."""
    assert committed_names() == SCENARIO_NAMES


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_a_transcript_holds_git_commands_and_no_host_data(name: str) -> None:
    """A transcript names its directory `{root}`, and holds no host path, user name or e-mail
    address other than example.com."""
    transcript = load_transcript(name)
    text = transcript_path(name).read_text(encoding="utf-8")

    assert (
        [
            exchange["argv"][0]
            for exchange in transcript["exchanges"]
            if exchange["argv"][0] != "git"
        ],
        host_data_in(text),
    ) == ([], [])


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_a_scenario_over_the_process_fake_starts_the_recorded_commands_and_gives_the_result(
    name: str, process_fake: ProcessFake, tmp_path: Path
) -> None:
    """The code starts the recorded commands in the recorded order, each with the recorded standard
    input and environment and the recorded answer, and returns the recorded result."""
    transcript = load_transcript(name)
    pending = list(transcript["exchanges"])
    unexpected: list[str] = []

    def next_answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        record = pending.pop(0) if pending else None
        expected = [w.replace(ROOT_MARK, str(tmp_path)) for w in record["argv"]] if record else []
        if list(call.argv) != expected:
            unexpected.append(f"started {list(call.argv)}, recorded {expected}")
            raise AssertionError(unexpected[-1])
        assert record is not None
        given = (call.stdin, call.env or None)
        recorded = (record["stdin"], record["env"])
        if given != recorded:
            unexpected.append(f"started with {given}, recorded {recorded}")
            raise AssertionError(unexpected[-1])
        done = subprocess.CompletedProcess(
            list(call.argv),
            record["returncode"],
            record["stdout"].replace(ROOT_MARK, str(tmp_path)),
            record["stderr"].replace(ROOT_MARK, str(tmp_path)),
        )
        if call.check and done.returncode != 0:
            raise subprocess.CalledProcessError(
                done.returncode, done.args, done.stdout, done.stderr
            )
        return done

    process_fake.answer(
        lambda call: Path(call.argv[0]).name == "git", ProcessAnswer(side_effect=next_answer)
    )

    result = json.loads(json.dumps(SCENARIOS[name](Workspace(tmp_path, recording=False))))

    assert (result, unexpected, [r["argv"] for r in pending]) == (transcript["result"], [], [])


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_a_scenario_over_the_git_fake_gives_the_recorded_result(
    name: str, git_fake: GitFake, tmp_path: Path
) -> None:
    """`GitFake` answers every command of the scenario from its transcript, so the code returns
    what it returned over the real git."""
    git_fake.replay(name)

    result = json.loads(json.dumps(SCENARIOS[name](Workspace(tmp_path, recording=False))))

    assert result == load_transcript(name)["result"]


def test_a_git_command_with_no_record_fails_the_test_and_names_it(
    git_fake: GitFake, tmp_path: Path
) -> None:
    """The fake never answers a command that git was not asked: a changed command fails here."""
    git_fake.replay("working_tree_state")

    with pytest.raises(pytest.fail.Exception, match=r"no record of `git -C .*nosuch-subcommand"):
        run_subprocess(["git", "-C", str(tmp_path / "repo"), "nosuch-subcommand"], quiet=True)


def test_a_scripted_answer_wins_over_a_record(git_fake: GitFake, tmp_path: Path) -> None:
    """A failure that a recording cannot hold, such as a git that cannot start, is scripted."""
    git_fake.replay("working_tree_state")
    git_fake.answer(["git", "status"], ProcessAnswer(side_effect=OSError("git is gone")))

    with pytest.raises(OSError, match="git is gone"):
        run_subprocess(["git", "status", "--porcelain"], cwd=tmp_path / "repo", quiet=True)


def test_a_test_with_the_git_fake_cannot_start_a_real_git(git_fake: GitFake) -> None:
    """The fixture refuses a real git for the whole test."""
    with pytest.raises(pytest.fail.Exception, match="started a real git"):
        subprocess.run(["git", "--version"], check=False)


@pytest.mark.parametrize("command", ["a shell string", "bytes"])
def test_a_test_with_the_git_fake_cannot_start_a_real_git_by_a_shell_string_or_bytes(
    git_fake: GitFake, command: str
) -> None:
    """The refusal reads the program as the process guard of the test floor does: the first word
    of a command line, and a bytes argument decoded."""
    with pytest.raises(pytest.fail.Exception, match="started a real git"):
        if command == "bytes":
            subprocess.run([b"git", b"--version"], check=False)
        else:
            subprocess.run("git --version", shell=True, check=False)


def _commit_tree_call(tmp_path: Path) -> dict[str, Any]:
    """The `commit-tree` command of the `commit_snapshots` transcript, as a call of the test."""
    record = next(
        exchange
        for exchange in load_transcript("commit_snapshots")["exchanges"]
        if "commit-tree" in exchange["argv"]
    )
    return {
        "cmd": [word.replace(ROOT_MARK, str(tmp_path)) for word in record["argv"]],
        "input": record["stdin"],
        "env": record["env"],
        "answer": record["stdout"],
    }


def test_a_record_is_found_by_the_standard_input_and_the_environment_of_the_call(
    git_fake: GitFake, tmp_path: Path
) -> None:
    """A commit made with the recorded message, identity and dates gets the recorded id."""
    git_fake.replay("commit_snapshots")
    call = _commit_tree_call(tmp_path)

    done = run_subprocess(call["cmd"], input=call["input"], env=call["env"], quiet=True)

    assert done.stdout == call["answer"]


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"input": "another message\n"}, "input"),
        ({"env": {"GIT_AUTHOR_NAME": "Someone Else"}}, "env"),
        ({"env": {"GIT_AUTHOR_DATE": "1999-01-01T00:00:00+00:00"}}, "env"),
        ({"env": {"GIT_COMMITTER_EMAIL": "x@example.com"}}, "env"),
    ],
)
def test_a_commit_with_another_message_or_identity_or_date_has_no_record(
    git_fake: GitFake, tmp_path: Path, change: dict[str, Any], field: str
) -> None:
    """The fake does not answer a commit that differs from the recorded one in what the commit
    holds, so a change to the message, the author or the date fails the test."""
    git_fake.replay("commit_snapshots")
    call = _commit_tree_call(tmp_path)
    if field == "env":
        call["env"] = {**call["env"], **change["env"]}
    else:
        call.update(change)

    with pytest.raises(pytest.fail.Exception, match=r"no record of `git -C .*commit-tree"):
        run_subprocess(call["cmd"], input=call["input"], env=call["env"], quiet=True)


def test_no_two_scenarios_give_one_command_in_one_directory_different_answers() -> None:
    """The fake finds a record by the command and the directory, so two scenarios that load
    together and answer one command differently would give a test either answer."""
    seen: dict[tuple[tuple[str, ...], str | None], dict[tuple[int, str, str], set[str]]] = {}
    for name in SCENARIO_NAMES:
        for exchange in load_transcript(name)["exchanges"]:
            key = (tuple(exchange["argv"]), exchange["cwd"])
            answer = (exchange["returncode"], exchange["stdout"], exchange["stderr"])
            seen.setdefault(key, {}).setdefault(answer, set()).add(name)

    conflicting = {
        " ".join(argv): answers
        for (argv, _), answers in seen.items()
        if len(answers) > 1 and len({n for names in answers.values() for n in names}) > 1
    }

    assert conflicting == {}


def test_a_recording_that_matches_the_transcripts_reports_no_difference() -> None:
    """The row passes when the real git gives the committed text for every scenario."""
    recorded = {name: transcript_path(name).read_text(encoding="utf-8") for name in SCENARIO_NAMES}

    assert differences(recorded) == []


def test_a_changed_transcript_and_a_transcript_without_a_scenario_are_reported() -> None:
    """The row fails, naming the file, when the real git gives other text for a scenario or a
    transcript has no scenario."""
    recorded = {name: transcript_path(name).read_text(encoding="utf-8") for name in SCENARIO_NAMES}
    changed = SCENARIO_NAMES[0]
    dropped = SCENARIO_NAMES[1]
    recorded[changed] = recorded[changed].replace('"returncode": 0', '"returncode": 1', 1)
    del recorded[dropped]

    report = differences(recorded)

    assert (
        any(line.startswith(f"+++ git/{changed}.json") for line in report),
        f"{dropped}.json: no scenario records it" in report,
    ) == (True, True)


@pytest.mark.parametrize(
    "text",
    [
        "/srv/data/repo",
        "in /opt/tool and",
        "/etc/gitconfig",
        "/run/user/1000/x",
        "/usr/lib/git-core",
        "/media/disk/repo",
    ],
)
def test_host_data_is_also_a_path_in_a_system_directory(text: str) -> None:
    """A host path is any directory of the root of a host, not only the ones of a user."""
    assert host_data_in(text) != []


def test_a_reference_or_a_file_name_that_holds_a_directory_name_is_no_host_path() -> None:
    """Only a path that starts at the root is a host path."""
    assert host_data_in("refs/heads/etc/x and docs/opt/y and {root}/repo") == []


def test_host_data_is_the_host_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """A message of git that names the host leaks it, so the name is host data."""
    monkeypatch.setattr(socket, "gethostname", lambda: "build-box7")

    assert (
        host_data_in("unable to auto-detect email address (got 'runner@build-box7.(none)')"),
        host_data_in("on another-box the pull failed"),
    ) == (["build-box7"], [])


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("{root}/repo and runner@example.com", []),
        ("/home/someone/repo", ["/home/"]),
        ("/mnt/scratch/repo", ["/mnt/"]),
        ("someone@corp.example.org", ["someone@corp.example.org"]),
    ],
)
def test_host_data_is_a_host_path_or_an_address_outside_example_com(
    text: str, found: list[str]
) -> None:
    """A transcript may hold the placeholder and example.com, and nothing else of a host."""
    assert host_data_in(text) == found
