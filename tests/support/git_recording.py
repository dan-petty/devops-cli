"""The real git's answers, recorded over the scenarios, which `GitFake` replays (#2146, ADR 0007).

`record_scenario` runs a scenario of `tests/support/git_scenarios.py` in a scratch directory with
the real git: `ws.git` builds the repository, and every git command that the code of `src/`
starts runs through `RecordingRunner`, which keeps its arguments, directory, standard input, exit
code, standard output and standard error. The scratch directory differs on every recording, so the
record holds `{root}` in its place. The scenario's return value is kept as its result.

The `devops ci` row `git` runs `main(["--check"])` on the stock runner. It records every
scenario again and fails when a committed transcript differs, or when a transcript has no scenario.
Record again after a change to a scenario, or to a command that the code starts, with:

    uv run python -c "import sys; from tests.support.git_recording import main; sys.exit(main([]))"

`tests/test_git_contract.py` replays the committed transcripts and starts no program.
"""

from __future__ import annotations

import difflib
import getpass
import json
import re
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devops_cli.core.process import (
    DetachedProcess,
    build_subprocess_env,
    reset_process_runner,
    set_process_runner,
)
from tests.support.git_scenarios import ROOT_MARK, SCENARIOS, Workspace
from tests.support.paths import FIXTURES

TRANSCRIPTS = FIXTURES / "git"
# A path that only a host has, an e-mail address that is not on example.com, or the user's name.
HOST_PATH = re.compile(r"/(?:home|Users|tmp|root|var|mnt|workspaces)/")
EMAIL = re.compile(r"[\w.+-]+@(?!example\.com\b)[\w-]+(?:\.[\w-]+)+")


@dataclass(frozen=True)
class Exchange:
    """One git command that the code started: what it was given and what git answered."""

    argv: tuple[str, ...]
    cwd: str | None
    stdin: str | None
    returncode: int
    stdout: str
    stderr: str


class RecordingRunner:
    """A process runner that runs each command with the real program and keeps git's answers.

    It builds the child environment with `build_subprocess_env`, as the default runner does, and
    does not look up a GitHub token, which would start gh.
    """

    def __init__(self, ws: Workspace) -> None:
        self.ws = ws
        self.exchanges: list[Exchange] = []

    def prepare_cmd(self, cmd: Sequence[str]) -> list[str]:
        """The command, unchanged."""
        return list(cmd)

    def run(
        self,
        cmd: Sequence[str],
        *,
        input: str | None = None,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 60,
        isolate_env: bool = True,
        extra_allowed_env: set[str] | list[str] | frozenset[str] | None = None,
        check: bool = False,
        **_: Any,
    ) -> subprocess.CompletedProcess[str]:
        """Run `cmd` for real; keep it when it starts git."""
        argv = list(cmd)
        child_env = build_subprocess_env(
            env=env, isolate_env=isolate_env, extra_allowed_keys=extra_allowed_env
        )
        done = subprocess.run(
            argv,
            input=input,
            cwd=cwd,
            env=child_env,
            capture_output=True,
            text=True,
            errors="replace",
            check=check,
            timeout=timeout,
        )
        if Path(argv[0]).name == "git":
            self.exchanges.append(
                Exchange(
                    argv=tuple(self.ws.shown(word) for word in argv),
                    cwd=self.ws.shown(str(cwd)) if cwd is not None else None,
                    stdin=self.ws.shown(input) if input is not None else None,
                    returncode=done.returncode,
                    stdout=self.ws.shown(done.stdout),
                    stderr=self.ws.shown(done.stderr),
                )
            )
        return done

    async def run_async(self, cmd: Sequence[str], **_: Any) -> subprocess.CompletedProcess[str]:
        """No scenario starts git asynchronously."""
        raise NotImplementedError(f"a scenario started {cmd!r} asynchronously")

    def spawn_detached(self, cmd: Sequence[str], **_: Any) -> DetachedProcess:
        """No scenario starts git detached."""
        raise NotImplementedError(f"a scenario started {cmd!r} detached")


def host_data_in(text: str) -> list[str]:
    """What in `text` only one host has: a host path, a user name, or an e-mail address that is
    not on example.com."""
    found = HOST_PATH.findall(text) + EMAIL.findall(text)
    user = getpass.getuser()
    if len(user) > 3 and re.search(rf"\b{re.escape(user)}\b", text):
        found.append(user)
    return found


def record_scenario(name: str) -> dict[str, Any]:
    """Run the scenario `name` with the real git, and return its transcript."""
    with tempfile.TemporaryDirectory(prefix="git-scenario-") as scratch:
        ws = Workspace(Path(scratch).resolve(), recording=True)
        runner = RecordingRunner(ws)
        set_process_runner(runner)
        try:
            result = SCENARIOS[name](ws)
        finally:
            reset_process_runner()
    return {
        "scenario": name,
        "exchanges": [
            {
                "argv": list(exchange.argv),
                "cwd": exchange.cwd,
                "stdin": exchange.stdin,
                "returncode": exchange.returncode,
                "stdout": exchange.stdout,
                "stderr": exchange.stderr,
            }
            for exchange in runner.exchanges
        ],
        "result": json.loads(json.dumps(result)),
    }


def render(transcript: dict[str, Any]) -> str:
    """The text of a transcript file."""
    return json.dumps(transcript, indent=1, ensure_ascii=False) + "\n"


def transcript_path(name: str) -> Path:
    """Where the transcript of a scenario is committed."""
    return TRANSCRIPTS / f"{name}.json"


def load_transcript(name: str) -> dict[str, Any]:
    """The committed transcript of a scenario."""
    loaded: dict[str, Any] = json.loads(transcript_path(name).read_text(encoding="utf-8"))
    return loaded


def committed_names() -> list[str]:
    """The scenarios that have a committed transcript."""
    return sorted(path.stem for path in TRANSCRIPTS.glob("*.json"))


def record_all() -> dict[str, str]:
    """The text of every scenario's transcript, recorded now with the real git."""
    recorded = {}
    for name in SCENARIOS:
        text = render(record_scenario(name))
        leaked = host_data_in(text.replace(ROOT_MARK, ""))
        if leaked:
            raise ValueError(f"the transcript of {name} holds host data: {sorted(set(leaked))}")
        recorded[name] = text
    return recorded


def differences(recorded: dict[str, str]) -> list[str]:
    """The lines that tell how the committed transcripts differ from `recorded`; none when the
    same scenarios have the same transcripts."""
    report: list[str] = []
    for name in sorted(set(recorded) | set(committed_names())):
        path = transcript_path(name)
        if name not in recorded:
            report.append(f"{path.name}: no scenario records it")
            continue
        committed = path.read_text(encoding="utf-8") if path.exists() else ""
        if committed != recorded[name]:
            report.extend(
                difflib.unified_diff(
                    committed.splitlines(),
                    recorded[name].splitlines(),
                    fromfile=f"committed/{path.name}",
                    tofile=f"git/{path.name}",
                    lineterm="",
                )
                or [f"{path.name}: not committed"]
            )
    return report


def write_all(recorded: dict[str, str]) -> None:
    """Write the transcripts, and delete the ones no scenario records."""
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    for stale in set(committed_names()) - set(recorded):
        transcript_path(stale).unlink()
    for name, text in recorded.items():
        transcript_path(name).write_text(text, encoding="utf-8")


def main(argv: Sequence[str]) -> int:
    """Record every scenario. With `--check`, write nothing and fail when a transcript differs."""
    version = subprocess.run(
        ["git", "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    recorded = record_all()
    if "--check" in argv:
        report = differences(recorded)
        if report:
            print(f"The committed git transcripts differ from {version}:")
            print("\n".join(report))
            print(
                "Record them again: uv run python -c "
                '"import sys; from tests.support.git_recording import main; sys.exit(main([]))"'
            )
            return 1
        print(f"The {len(recorded)} git transcripts match {version}.")
        return 0
    write_all(recorded)
    print(f"Recorded {len(recorded)} git transcripts with {version}.")
    return 0
