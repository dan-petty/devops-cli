"""The export of an implement fixture as a Harbor task (#3104): the four files of a task folder,
and one task folder for each committed fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_ROADMAP_EVAL_IMPLEMENT_FIXTURES
from devops_cli.roadmap.implement.implement_eval import LoadedCase, load_case, load_cases
from tests.support.implement_step import BODY
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_eval import PLAN, write_fixture

BASE = "0123456789abcdef0123456789abcdef01234567"
TIMEOUT_SECONDS = 600
TASK_FILES = (
    "instruction.md",
    "environment/Dockerfile",
    "tests/test.sh",
    "task.toml",
)

EXPECTED_INSTRUCTION = (
    "# Make the sample shout\n"
    "\n"
    f"Issue #1, group 1 of the plan, at commit `{BASE}`.\n"
    "\n"
    "Do the work of group 1 of the plan below, and tick each task of the group in `tasks.md` "
    "when it is done.\n"
    "\n"
    "## The issue\n"
    "\n" + BODY + "\n"
    "## The plan\n"
    "\n"
    "### proposal.md\n"
    "\n" + PLAN["proposal.md"] + "\n"
    "### design.md\n"
    "\n" + PLAN["design.md"] + "\n"
    "### tasks.md\n"
    "\n" + PLAN["tasks.md"]
)

EXPECTED_DOCKERFILE = (
    "# The environment of the task: this repository at the base commit of the fixture, with\n"
    "# the interpreter, uv and the tools that the checks of the fixture use.\n"
    "FROM python:3.14-slim-trixie\n"
    "\n"
    "ENV PYTHONUNBUFFERED=1 \\\n"
    "    UV_COMPILE_BYTECODE=1 \\\n"
    "    UV_LINK_MODE=copy\n"
    "\n"
    "RUN apt-get update \\\n"
    "    && apt-get install -y --no-install-recommends ca-certificates git \\\n"
    "    && rm -rf /var/lib/apt/lists/*\n"
    "\n"
    "COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /usr/local/bin/\n"
    "\n"
    "WORKDIR /app\n"
    "RUN git clone --quiet https://github.com/dan-petty/devops-cli /app \\\n"
    f"    && git -C /app checkout --quiet --detach {BASE}\n"
    "\n"
    "RUN uv sync --frozen\n"
)

EXPECTED_SCRIPT = (
    "#!/bin/bash\n"
    "# The reward of one trial: 1 when every check of the fixture passes, and 0 otherwise.\n"
    "# The verifier of Harbor reads the reward from /logs/reward.txt.\n"
    "set -u\n"
    "\n"
    "reward=1\n"
    "if ! uv run devops ci test tests/test_sample.py; then\n"
    "  reward=0\n"
    "fi\n"
    "\n"
    'mkdir -p "$(dirname /logs/reward.txt)"\n'
    "printf '%s\\n' \"$reward\" > /logs/reward.txt\n"
)

EXPECTED_TASK_CONFIG = (
    'version = "1.0"\n'
    "\n"
    "[metadata]\n"
    'name = "sample"\n'
    f'description = "Issue #1, group 1, at {BASE[:12]}. The export of an implement eval fixture."\n'
    "\n"
    "[verifier]\n"
    "timeout_sec = 600.0\n"
    "\n"
    "[agent]\n"
    "timeout_sec = 600.0\n"
    "\n"
    "[environment]\n"
    "build_timeout_sec = 600.0\n"
    "cpus = 2\n"
    "memory_mb = 4096\n"
    "storage_mb = 10240\n"
)


def _loaded(tmp_path: Path) -> LoadedCase:
    return load_case(write_fixture(tmp_path / "fixture"))


def test_a_fixture_becomes_a_task_folder(tmp_path: Path) -> None:
    from devops_cli.roadmap.implement.implement_eval_harbor import export_task

    folder = export_task(
        _loaded(tmp_path), tmp_path / "tasks" / "sample", timeout_seconds=TIMEOUT_SECONDS
    )

    assert folder == tmp_path / "tasks" / "sample"
    assert [path.relative_to(folder).as_posix() for path in _task_files(folder)] == list(TASK_FILES)
    assert all(path.is_file() for path in _task_files(folder))
    assert all(path.read_text(encoding="utf-8").strip() for path in _task_files(folder))


def test_the_instruction_holds_the_issue_and_the_plan(tmp_path: Path) -> None:
    from devops_cli.roadmap.implement.implement_eval_harbor import instruction_text

    assert instruction_text(_loaded(tmp_path)) == EXPECTED_INSTRUCTION


def test_the_dockerfile_checks_out_the_base_commit_of_the_fixture(tmp_path: Path) -> None:
    from devops_cli.roadmap.implement.implement_eval_harbor import dockerfile_text

    assert dockerfile_text(_loaded(tmp_path)) == EXPECTED_DOCKERFILE


def test_the_test_script_runs_the_checks_and_writes_the_reward(tmp_path: Path) -> None:
    from devops_cli.roadmap.implement.implement_eval_harbor import REWARD_FILE, test_script_text

    text = test_script_text(_loaded(tmp_path))

    assert text == EXPECTED_SCRIPT
    assert REWARD_FILE == "/logs/reward.txt"
    assert REWARD_FILE in text


def test_the_task_configuration_carries_the_time_limit(tmp_path: Path) -> None:
    from devops_cli.roadmap.implement.implement_eval_harbor import task_config_text

    loaded = _loaded(tmp_path)

    assert task_config_text(loaded, TIMEOUT_SECONDS) == EXPECTED_TASK_CONFIG
    assert "timeout_sec = 900.0" in task_config_text(loaded, 900)


def test_a_fixture_with_no_issue_text_is_refused(tmp_path: Path) -> None:
    from devops_cli.exceptions.roadmap import ImplementEvalError
    from devops_cli.roadmap.implement.implement_eval_harbor import export_task

    folder = write_fixture(tmp_path / "fixture")
    (folder / "issue.md").write_text("", encoding="utf-8")
    loaded = load_case(folder)

    with pytest.raises(ImplementEvalError) as raised:
        export_task(loaded, tmp_path / "tasks" / "sample", timeout_seconds=TIMEOUT_SECONDS)

    assert raised.value.exit_code == 1
    assert raised.value.error_code == "ROADMAP_EVAL_REFUSED"
    assert "sample" in str(raised.value)
    assert "issue.md" in str(raised.value)
    assert not (tmp_path / "tasks" / "sample").exists()


def test_each_committed_fixture_becomes_a_task_folder(tmp_path: Path) -> None:
    from devops_cli.roadmap.implement.implement_eval_harbor import export_task

    root = REPO_ROOT / CONST_ROADMAP_EVAL_IMPLEMENT_FIXTURES
    cases = load_cases(root)

    folders = [
        export_task(case, tmp_path / "tasks" / case.name, timeout_seconds=TIMEOUT_SECONDS)
        for case in cases
    ]

    assert sorted(path.name for path in root.iterdir() if (path / "case.json").is_file()) == [
        case.name for case in cases
    ]
    assert [folder.name for folder in folders] == [case.name for case in cases]
    for folder in folders:
        assert all(path.read_text(encoding="utf-8").strip() for path in _task_files(folder))


def _task_files(folder: Path) -> list[Path]:
    return [folder / name for name in TASK_FILES]
