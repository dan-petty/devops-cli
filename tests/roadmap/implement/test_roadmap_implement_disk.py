"""The disk use of the home volume of a runner Job, and the by-products of a step (#6076).

The kubelet evicted implement runner pods for a full `home` emptyDir, and an eviction leaves no log
of what filled the volume. The process edge is `process_fake`: it answers `du` with the lines that
the real `du -x -B1 -d 1` prints. The model of a step is a `FunctionModel` that a script answers.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.config.constants import (
    CONST_MUTMUT_TREE_DIR,
    CONST_ROADMAP_IMPLEMENT_SCRATCH_DIR,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement.implement_disk import end_step, log_disk_use
from devops_cli.roadmap.implement.implement_step import StepStatus, run_step
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import (
    CHECK,
    WINDOW,
    command_text,
    git,
    the_whole_group,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import JobWorld, group_one_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

PROBE = f"{CONST_ROADMAP_IMPLEMENT_SCRATCH_DIR}/probe_mutation.py"
MUTATED = f"{CONST_MUTMUT_TREE_DIR}/src/sample.py"


def _du_lines(worktree: Path, home: Path) -> str:
    """What `du -x -B1 -d 1 <worktree> <home>` prints for a volume like the one of #3782: each
    folder of an argument, then the argument. du counts a folder once, at the first argument that
    holds it, so the line of home and of its `.data` leave the worktree out."""
    return "".join(
        f"{size}\t{path}\n"
        for size, path in (
            (1288490188, worktree / ".venv"),
            (734003200, worktree / CONST_MUTMUT_TREE_DIR),
            (3221225472, worktree / ".data"),
            (28311552, worktree / "src"),
            (35651584, worktree / "tests"),
            (2831155, worktree / "docs"),
            (5310000000, worktree),
            (1181116006, home / ".cache"),
            (471859200, home / ".data"),
            (4096, home / ".config"),
            (1652979302, home),
        )
    )


# The folders of `_du_lines` in the line, largest first. The line names 8 folders at most, so
# `.config` is left out.
FOLDERS = (
    "worktree/.data 3.0 GB, worktree/.venv 1.2 GB, .cache 1.1 GB, worktree/mutants 700.0 MB, "
    ".data 450.0 MB, worktree/tests 34.0 MB, worktree/src 27.0 MB, worktree/docs 2.7 MB"
)


@pytest.fixture
def volume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """The home of the Job and the worktree in its data folder, as in the pod of a runner Job."""
    home = tmp_path / "home"
    worktree = home / ".data" / "worktrees" / "6076"
    (worktree / CONST_ROADMAP_IMPLEMENT_SCRATCH_DIR).mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    return home, worktree


def _answer_du(programs: ProcessFake, answer: Callable[[ProcessCall], str]) -> list[ProcessCall]:
    calls: list[ProcessCall] = []

    def du(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        calls.append(call)
        return subprocess.CompletedProcess(call.argv, 0, answer(call), "")

    programs.answer("du", ProcessAnswer(side_effect=du))
    return calls


def test_the_end_of_a_step_in_a_runner_job_names_the_largest_folders_of_the_home_volume(
    volume: tuple[Path, Path],
    process_fake: ProcessFake,
    config: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    home, worktree = volume
    config(roadmap={"implement": {"in_runner": True}})
    calls = _answer_du(process_fake, lambda call: _du_lines(worktree, home))

    log_disk_use(worktree, "fix")

    assert [call.argv for call in calls] == [
        ("du", "-x", "-B1", "-d", "1", str(worktree), str(home))
    ]
    assert capsys.readouterr().err.splitlines() == [
        MESSAGES.roadmap.implement_disk_use.format(step="fix", total="6.5 GB", folders=FOLDERS)
    ]


def test_outside_a_runner_job_the_step_reads_no_disk_use(
    volume: tuple[Path, Path],
    process_fake: ProcessFake,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Outside a runner Job, home is the home of a person and holds no volume of the Job."""
    _home, worktree = volume

    log_disk_use(worktree, "fix")

    assert (process_fake.calls, capsys.readouterr().err) == ([], "")


def test_the_disk_use_names_the_by_products_before_the_end_of_the_step_removes_them(
    volume: tuple[Path, Path],
    process_fake: ProcessFake,
    config: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    home, worktree = volume
    config(roadmap={"implement": {"in_runner": True}})
    for name in (PROBE, MUTATED):
        (worktree / name).parent.mkdir(parents=True, exist_ok=True)
        (worktree / name).write_text("x = 1\n", encoding="utf-8")
    seen: list[bool] = []

    def lines(call: ProcessCall) -> str:
        seen.append((worktree / PROBE).exists() and (worktree / MUTATED).exists())
        return _du_lines(worktree, home)

    _answer_du(process_fake, lines)

    end_step(worktree, "fix")

    scratch = worktree / CONST_ROADMAP_IMPLEMENT_SCRATCH_DIR
    assert (seen, (worktree / CONST_MUTMUT_TREE_DIR).exists(), list(scratch.iterdir())) == (
        [True],
        False,
        [],
    )
    assert "worktree/mutants 700.0 MB" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("check_status", "status"), [(0, StepStatus.DONE), (1, StepStatus.STOPPED)]
)
def test_a_step_removes_the_mutation_tree_and_the_scratch_files_of_its_agent(
    implement_store: InMemoryRoadmapStore,
    implement_checkout: Path,
    implement_programs: ProcessFake,
    check_status: int,
    status: StepStatus,
) -> None:
    """The scratch runs of the agent and a mutation run of its own write files that git ignores,
    so neither the commit nor the reset of a step removes them, and they stayed on the home volume
    for the rest of the Job (#6076). The step removes them when it ends, done or stopped."""
    checkout = implement_checkout
    (checkout / ".gitignore").write_text(f".data/\n/{CONST_MUTMUT_TREE_DIR}/\n", encoding="utf-8")
    git(checkout, "add", ".gitignore")
    git(checkout, "commit", "-q", "-m", "ignore")
    scratch = checkout / CONST_ROADMAP_IMPLEMENT_SCRATCH_DIR
    scratch.mkdir(parents=True)
    written: list[bool] = []

    def check(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        written.append((checkout / PROBE).exists() and (checkout / MUTATED).exists())
        return subprocess.CompletedProcess(call.argv, check_status, "", "")

    implement_programs.answer(
        lambda call: command_text(call) == CHECK, ProcessAnswer(side_effect=check)
    )
    # The calls of one reply run at the same time, so the folder comes in a reply of its own.
    script = ModelScript(
        tool_calls(("create_directory", {"path": str(Path(MUTATED).parent)})),
        tool_calls(write_call(PROBE, "x = 1\n"), write_call(MUTATED, "x = 1\n")),
        tool_calls(*the_whole_group()),
        say("Done."),
    )

    outcome = run_step(
        implement_store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW
    )

    assert (outcome.status, written[:1]) == (status, [True])
    assert ((checkout / CONST_MUTMUT_TREE_DIR).exists(), scratch.is_dir()) == (False, True)
    assert list(scratch.iterdir()) == []


def test_a_stop_of_the_job_writes_the_disk_use_at_its_step(
    job_world: JobWorld, capsys: pytest.CaptureFixture[str]
) -> None:
    """The kubelet stops an evicted pod at once, so the last line before it is the one of the last
    end of a step or stop. A stop writes it too, also a stop outside a step of the agent."""
    _answer_du(job_world.programs, lambda call: _du_lines(Path(call.argv[-2]), Path(call.argv[-1])))
    script = ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        say("I could not do group 2."),
    )

    job_world.run(script)

    lines = [line for line in capsys.readouterr().err.splitlines() if line.startswith("Disk use")]
    stop = MESSAGES.roadmap.implement_disk_use.format(
        step="group 2", total="6.5 GB", folders=FOLDERS
    )
    assert (len(lines), lines[-1]) == (3, stop)
