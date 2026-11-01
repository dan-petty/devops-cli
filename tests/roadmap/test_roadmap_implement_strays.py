"""The stray files of an implement step (#3092): a file that the agent left in the checkout and
that its group does not name. `stray_files` decides from the names that git lists; the replay tests
below run a step with a stub model that writes such a file.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from devops_cli.config import constants
from devops_cli.roadmap.implement_step import (
    FixRequest,
    StepOutcome,
    StepStatus,
    render_outcome,
    run_fix_step,
    run_step,
)
from devops_cli.roadmap.implement_strays import stray_files
from devops_cli.roadmap.implement_tool_log import ToolCallLog
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.step_files import parse_task_groups
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import (
    REPO,
    SHOUT_CODE,
    TASKS_PATH,
    TEST_BODY,
    TICKED,
    WINDOW,
    command_text,
    git,
    is_clean_at,
    the_whole_group,
    write_call,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

CHANGE = "openspec/changes/1-sample-change"
GROUP = parse_task_groups(
    "## 1. The group\n\n"
    "Reads: none. Changes: `src/sample.py`, `tests/test_sample.py` (new).\n\n"
    "- [ ] 1.1 Add the test `tests/test_sample.py`\n"
    "  - Verification: `uv run devops ci test tests/test_sample.py`\n"
    "- [ ] 1.2 Write `docs/NOTES.md`\n"
)[0]


def _strays(*names: str) -> list[str]:
    return stray_files(names, GROUP, CHANGE)


@pytest.mark.parametrize(
    "name", ["tmp_test_x.py", "test_cwd_issue.py", "scripts/probe.py", "tests/sub/test_other.py"]
)
def test_a_file_that_the_group_does_not_name_is_a_stray_file(name: str) -> None:
    assert _strays(name) == [name]


@pytest.mark.parametrize(
    "name",
    [
        "src/sample.py",
        "tests/test_sample.py",
        "docs/NOTES.md",
        f"{CHANGE}/notes.md",
        f"{CHANGE}/specs/sample/spec.md",
        "tests/test_sample_more.py",
    ],
)
def test_a_file_that_the_group_allows_is_kept(name: str) -> None:
    assert _strays(name) == []


def test_a_test_file_is_kept_only_in_the_directory_of_a_named_test_file() -> None:
    assert _strays("tests/test_more.py", "tests/conftest.py", "src/test_more.py") == [
        "tests/conftest.py",
        "src/test_more.py",
    ]


def test_the_stray_files_come_back_in_the_order_git_listed_them() -> None:
    assert _strays("b_tmp.py", "src/sample.py", "a_tmp.py") == ["b_tmp.py", "a_tmp.py"]


def test_a_name_with_a_dot_folder_is_compared_as_a_normal_path() -> None:
    assert _strays("./src/sample.py", "docs/../src/sample.py") == []


# ── Replays with a stub model: a step runs, and the checkout is real ──────────────────────────

UNUSED = "F401 `os` imported but unused\n --> tests/test_sample.py:1:8"
STRAY = write_call("tmp_test_x.py", "import os\n")
TOLD = (
    " The step removed these files, because your group does not name them: tmp_test_x.py. Keep a "
    "scratch file under `.data/agent/scratch/`."
)


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    """The process edge, with a lint that fails on a file that holds `import os`, as it would for
    the stray file, and reads each file that it is given."""

    def lint(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        assert call.cwd is not None
        names = call.argv[call.argv.index("--") + 1 :]
        failed = any("import os" in (call.cwd / name).read_text(encoding="utf-8") for name in names)
        return subprocess.CompletedProcess(
            call.argv, int(failed), stdout=f"{UNUSED}\n" if failed else "", stderr=""
        )

    implement_programs.answer(
        lambda call: command_text(call).startswith("uv run ruff check"),
        ProcessAnswer(side_effect=lint),
    )
    return implement_programs


def _step(store: InMemoryRoadmapStore, checkout: Path, script: ModelScript) -> StepOutcome:
    return run_step(store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW)


def _committed(checkout: Path) -> list[str]:
    return git(checkout, "show", "--name-only", "--format=", "HEAD").splitlines()


def _uv_words(programs: ProcessFake) -> str:
    return " ".join(command_text(call) for call in programs.calls if call.argv[0] == "uv")


def test_a_scratch_file_in_the_root_is_removed_and_the_step_ends_done(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(*the_whole_group(), STRAY), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, outcome.removed) == (
        StepStatus.DONE,
        "",
        ("tmp_test_x.py",),
    )
    assert not (checkout / "tmp_test_x.py").exists()
    assert sorted(_committed(checkout)) == [TASKS_PATH, "src/sample.py", "tests/test_sample.py"]
    assert "tmp_test_x" not in _uv_words(programs)
    assert git(checkout, "status", "--porcelain") == ""


def test_a_new_test_file_next_to_the_named_test_file_is_kept(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    more = write_call("tests/test_sample_more.py", TEST_BODY.replace("shout", "shout_more"))
    script = ModelScript(tool_calls(*the_whole_group(), more), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.removed) == (StepStatus.DONE, ())
    assert "tests/test_sample_more.py" in _committed(checkout)


def test_a_file_in_a_directory_that_the_group_does_not_name_is_removed(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    def agent_writes_a_probe() -> None:
        (checkout / "scripts").mkdir()
        (checkout / "scripts" / "probe.py").write_text("import os\n", encoding="utf-8")

    script = ModelScript(
        tool_calls(*the_whole_group()), say("Done."), effects={2: agent_writes_a_probe}
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.removed) == (StepStatus.DONE, ("scripts/probe.py",))
    assert not (checkout / "scripts" / "probe.py").exists()
    assert "scripts/probe.py" not in _committed(checkout)


def test_the_extra_turn_tells_the_agent_which_files_the_step_removed(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    unused = write_call("tests/test_sample.py", "import os\n\n" + TEST_BODY)
    stray = write_call("tmp_test_x.py", "X = 1\n")
    first = tool_calls(
        unused, write_call("src/sample.py", SHOUT_CODE), write_call(TASKS_PATH, TICKED), stray
    )
    script = ModelScript(
        first, say("Done."), tool_calls(write_call("tests/test_sample.py", TEST_BODY)), say("Ok.")
    )

    outcome = _step(store, checkout, script)

    sent = [str(getattr(part, "content", "")) for part in script.seen[2][-1].parts][-1]
    assert (outcome.status, outcome.removed) == (StepStatus.DONE, ("tmp_test_x.py",))
    assert sent.endswith(
        f"Change only the files that you changed.{TOLD} Then reply with one short message."
    )


def test_a_scratch_file_of_the_extra_turn_is_removed_and_does_not_stop_the_step(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    ticks_missing = tool_calls(
        write_call("tests/test_sample.py", TEST_BODY), write_call("src/sample.py", SHOUT_CODE)
    )
    script = ModelScript(
        ticks_missing, say("Done."), tool_calls(write_call(TASKS_PATH, TICKED), STRAY), say("Ok.")
    )

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.reason, outcome.removed) == (
        StepStatus.DONE,
        "",
        ("tmp_test_x.py",),
    )
    assert "tmp_test_x.py" not in _committed(checkout)


def test_a_file_that_git_ignores_is_not_a_stray_file(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    (checkout / ".gitignore").write_text(".data/\n", encoding="utf-8")
    git(checkout, "add", ".gitignore")
    git(checkout, "commit", "-q", "-m", "ignore")
    scratch = checkout / ".data" / "agent" / "scratch"
    scratch.mkdir(parents=True)
    note = write_call(".data/agent/scratch/probe.py", "import os\n")
    script = ModelScript(tool_calls(*the_whole_group(), note), say("Done."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.removed) == (StepStatus.DONE, ())
    assert (scratch / "probe.py").exists()
    assert ".data/agent/scratch/probe.py" not in _committed(checkout)


def test_a_fix_step_keeps_the_new_file_that_it_writes(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    new = write_call("tests/test_sample_fix.py", TEST_BODY)
    script = ModelScript(tool_calls(write_call("src/sample.py", SHOUT_CODE), new), say("Fixed."))

    outcome = run_fix_step(
        store,
        item=1,
        fix=FixRequest(check="Static Analysis", log="E501 line"),
        source=checkout,
        model=script.model(),
        window=WINDOW,
    )

    assert (outcome.status, outcome.removed) == (StepStatus.DONE, ())
    assert "tests/test_sample_fix.py" in _committed(checkout)


def test_a_stopped_step_still_resets_the_checkout_after_it_removed_a_stray_file(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    head = git(checkout, "rev-parse", "HEAD")

    outcome = _step(store, checkout, ModelScript(tool_calls(STRAY), say("Done.")))

    assert (outcome.status, outcome.removed, outcome.reason) == (
        StepStatus.STOPPED,
        ("tmp_test_x.py",),
        "The agent changed no file.",
    )
    assert is_clean_at(checkout, head)


def test_the_log_names_the_removed_files_on_one_line_and_cuts_a_long_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    shown = constants.CONST_ROADMAP_IMPLEMENT_REASON_PATHS
    log = ToolCallLog()

    log.removed_strays(["a\nb.py", *(f"f{number}.py" for number in range(shown + 2))])

    err = capsys.readouterr().err
    assert len(log.removed) == shown + 3
    assert err.count("\n") == 1
    assert err.startswith("Removed stray files that the group does not name: a\\nb.py, f0.py")
    assert err.rstrip().endswith("and 3 more.")


def test_the_log_writes_nothing_when_no_file_was_removed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log = ToolCallLog()

    log.removed_strays([])

    assert (capsys.readouterr().err, log.removed) == ("", [])


def test_the_table_of_the_command_shows_the_removed_files(
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome = StepOutcome(
        item=1, group=1, title="The group", status=StepStatus.DONE, removed=("tmp_a.py", "b.py")
    )

    render_outcome(outcome, REPO, "table")

    assert "Removed stray files" in capsys.readouterr().out
    render_outcome(outcome, REPO, "json")
    assert '"removed": [\n    "tmp_a.py",\n    "b.py"\n  ]' in capsys.readouterr().out


def test_the_table_has_no_row_for_removed_files_when_none_was_removed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    render_outcome(
        StepOutcome(item=1, group=1, title="The group", status=StepStatus.DONE), REPO, "table"
    )

    assert "Removed stray files" not in capsys.readouterr().out
