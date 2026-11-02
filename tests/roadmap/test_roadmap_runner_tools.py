"""The table of the tools that the runner image must hold (#3072).

The first tests read the sources of the gate offline: the rows of `devops ci`, the hooks of
`.pre-commit-config.yaml`, the required jobs of `ci.yml`, the live-marked tests and the tools lock.
They fail when a program that one of them needs is in neither `RUNNER_TOOLS` nor `NOT_IN_RUNNER`.
The next tests compare the pins of the table with the Dockerfiles. The last tests run the check of
a tool over the process fake.
"""

from __future__ import annotations

import ast
import shlex
import tomllib
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.commands.ci import get_check_specs
from devops_cli.config.defaults import DEFAULT_PYTHON_VERSION
from devops_cli.roadmap.runner_tools import (
    GH_VERSION,
    HOOK_PROGRAMS,
    NODE_MAJOR,
    NOT_IN_RUNNER,
    RUNNER_TOOLS,
    UV_VERSION,
    RunnerTool,
    ToolSource,
    expected_text,
    failures,
    hooks_without_programs,
    main,
    tool_failure,
    tool_names,
)
from devops_cli.tools_lock import load_tools_lock
from tests.support.dockerfile import stages
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.paths import REPO_ROOT, TESTS_ROOT

HELD = set(tool_names())
DECIDED = HELD | set(NOT_IN_RUNNER)


def _text(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def _programs(argv: Sequence[str]) -> list[str]:
    """The programs that one command of a row starts: its first word, the tool that `uv run`
    starts, and `nice`, which a row can put in front of that tool."""
    words = list(argv)
    found = [words[0]]
    if words[:2] == ["uv", "run"]:
        rest = words[2:]
        if rest[0] == "nice":
            found.append("nice")
            rest = rest[3:]
        found.append(rest[0])
    return found


def _row_programs() -> dict[str, set[str]]:
    return {
        spec.name: {program for argv in spec.commands for program in _programs(argv)}
        for spec in get_check_specs()
    }


def _hooks() -> dict[str, dict[str, Any]]:
    config = yaml.safe_load(_text(".pre-commit-config.yaml"))
    return {hook["id"]: hook for repo in config["repos"] for hook in repo["hooks"]}


def _hook_programs() -> dict[str, set[str]]:
    """The programs of the hooks. A hook of a remote repository runs under `pre-commit`; a local
    hook runs its `entry`."""
    config = yaml.safe_load(_text(".pre-commit-config.yaml"))
    found: dict[str, set[str]] = {}
    for repo in config["repos"]:
        for hook in repo["hooks"]:
            if repo["repo"] == "local":
                found[hook["id"]] = set(_programs(shlex.split(hook["entry"])))
            else:
                found[hook["id"]] = {"pre-commit"}
    return found


def _gate_job_tools() -> dict[str, set[str]]:
    """The tools that the required jobs `static` and `test` of `ci.yml` install, by job."""
    jobs = yaml.safe_load(_text(".github/workflows/ci.yml"))["jobs"]
    found: dict[str, set[str]] = {}
    for name in ("static", "test"):
        tools: set[str] = set()
        for step in jobs[name]["steps"]:
            if "actionlint" in step.get("uses", ""):
                tools.add("actionlint")
            words = shlex.split(step.get("run", "").replace("\n", " "))
            tools.update(words[index + 1] for index, word in enumerate(words) if word == "--tool")
        found[name] = tools
    return found


def _live_binaries() -> Iterator[str]:
    """The binaries named by `@pytest.mark.live(...)` in the tests, read from the syntax tree."""
    for path in TESTS_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "mark.live(" not in source or path.name == "test_hermetic_floor.py":
            continue
        for node in ast.walk(ast.parse(source)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "live"
            ):
                yield from (
                    arg.value
                    for arg in node.args
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                )


# ── The sources of the gate need no program outside the two tables ──────────────────────────


def test_each_program_of_a_ci_row_is_held_or_left_out_with_a_reason() -> None:
    needed = set().union(*_row_programs().values())

    assert sorted(needed - DECIDED) == []


def test_each_program_of_a_hook_is_held_or_left_out_with_a_reason() -> None:
    needed = set().union(*_hook_programs().values())

    assert sorted(needed - DECIDED) == []


def test_each_tool_that_a_required_job_installs_is_held_or_left_out_with_a_reason() -> None:
    needed = set().union(*_gate_job_tools().values())

    assert (sorted(needed - DECIDED), "trivy" in needed, "promtool" in needed) == ([], True, True)


def test_each_binary_of_a_live_marked_test_is_held_or_left_out_with_a_reason() -> None:
    needed = set(_live_binaries())

    assert (sorted(needed - DECIDED), "jq" in needed) == ([], True)


def test_each_tool_of_the_tools_lock_is_held_or_left_out_with_a_reason() -> None:
    assert sorted(set(load_tools_lock().tools()) - DECIDED) == []


# ── The two tables agree with each other and with the sources ───────────────────────────────


def test_no_program_is_both_held_and_left_out() -> None:
    assert sorted(HELD & set(NOT_IN_RUNNER)) == []


def test_each_tool_is_listed_once_and_has_a_reason_to_be_there() -> None:
    names = tool_names()

    assert (len(names) == len(set(names)), [t.name for t in RUNNER_TOOLS if not t.needed_by]) == (
        True,
        [],
    )


def test_each_reason_to_hold_a_tool_names_a_real_row_hook_or_job() -> None:
    rows, hooks, jobs = _row_programs(), _hooks(), _gate_job_tools()
    known = {
        "ci": set(rows),
        "hook": set(hooks),
        "gate": set(jobs),
    }
    unknown = []
    for tool in RUNNER_TOOLS:
        for reason in tool.needed_by:
            kind, _, name = reason.partition(":")
            if kind in known and name not in known[kind]:
                unknown.append(f"{tool.name}: {reason}")
            if kind not in {*known, "test", "job"}:
                unknown.append(f"{tool.name}: {reason}")

    assert unknown == []


def test_a_tool_that_a_row_starts_names_that_row_as_a_reason() -> None:
    """A program that the argv of a row starts is held for that row, so the table says why."""
    missing = [
        f"{program}: ci:{row}"
        for row, programs in _row_programs().items()
        for program in programs
        if program in HELD
        and not any(tool.name == program and f"ci:{row}" in tool.needed_by for tool in RUNNER_TOOLS)
        and program not in {"uv", "python", "git", "devops"}
    ]

    assert missing == []


def test_a_tool_that_the_lock_gives_is_a_tool_of_the_lock() -> None:
    locked = set(load_tools_lock().tools())

    assert sorted(t.name for t in RUNNER_TOOLS if t.source is ToolSource.TOOLS_LOCK) == sorted(
        {t.name for t in RUNNER_TOOLS if t.source is ToolSource.TOOLS_LOCK} & locked
    )


def test_the_version_of_each_dev_dependency_is_the_version_of_the_lockfile() -> None:
    """The check of a dev dependency reads the installed distribution. The image syncs the
    lockfile, so the distribution must be the version that `uv.lock` names."""
    packages = tomllib.loads(_text("uv.lock"))["package"]
    locked = {package["name"]: package["version"] for package in packages}
    dev = [t for t in RUNNER_TOOLS if t.source is ToolSource.DEV_GROUP]

    assert dev
    assert {t.package: expected_text(t) for t in dev} == {t.package: locked[t.package] for t in dev}


# ── The pins of the table agree with the Dockerfiles ────────────────────────────────────────


def _runner() -> list[list[str]]:
    return stages(_text("Dockerfile"))["runner"]


def _runs(stage: list[list[str]]) -> list[str]:
    return [" ".join(words[1:]) for words in stage if words[0].upper() == "RUN"]


def test_the_pins_of_the_table_are_the_pins_of_the_dockerfile() -> None:
    dockerfile = _text("Dockerfile")
    devcontainer = _text(".devcontainer/Dockerfile")

    assert (
        f"ghcr.io/astral-sh/uv:{UV_VERSION}@sha256:" in dockerfile,
        f"--from=ghcr.io/astral-sh/uv:{UV_VERSION} " in devcontainer,
        f"/releases/download/v{GH_VERSION}/" in dockerfile,
        f"FROM node:{NODE_MAJOR}-" in dockerfile,
        _text(".node-version").strip(),
        f"FROM python:{DEFAULT_PYTHON_VERSION}-" in dockerfile,
        _text(".python-version").startswith(f"{DEFAULT_PYTHON_VERSION}."),
    ) == (True, True, True, True, NODE_MAJOR, True, True)


def test_a_tool_whose_release_fails_the_scan_of_the_image_is_left_out_with_the_reason() -> None:
    """The scan of the image fails on a fixed HIGH finding in a Go binary, and the owner alone may
    lower it. Trivy, actionlint and shellcheck (which only actionlint uses) wait for a release
    that the scan accepts."""
    held = set(tool_names())
    scan = ("trivy", "actionlint", "shellcheck")

    assert (
        held.isdisjoint(scan),
        all("image scan" in NOT_IN_RUNNER[name] for name in scan),
        "FROM docker.io/kjanat/actionlint" in _text("Dockerfile"),
    ) == (True, True, False)


def test_the_apt_packages_of_the_runner_are_the_apt_tools_of_the_table() -> None:
    (install,) = (run for run in _runs(_runner()) if "apt-get install" in run)
    words = shlex.split(install.split("apt-get install")[1].split("&&")[0])
    packages = {word for word in words if not word.startswith("-")} - {"ca-certificates"}

    assert packages == {t.name for t in RUNNER_TOOLS if t.source is ToolSource.APT}


def test_the_runner_installs_the_tools_of_the_lock_that_the_table_holds_and_the_service_none() -> (
    None
):
    held = {t.name for t in RUNNER_TOOLS if t.source is ToolSource.TOOLS_LOCK}
    in_runner = " ".join(_runs(_runner()))
    in_service = " ".join(_runs(stages(_text("Dockerfile"))["service"]))

    assert (
        [name for name in sorted(held - {"openspec"}) if f"--tool {name}" not in in_runner],
        "install-tools" in in_service,
    ) == ([], False)


def test_the_last_step_of_the_runner_runs_the_check_of_every_tool_as_the_job_user() -> None:
    runner = _runner()
    check = next(
        index
        for index, words in enumerate(runner)
        if words[0] == "RUN" and "devops_cli.roadmap.runner_tools" in " ".join(words)
    )
    user = next(index for index, words in enumerate(runner) if words[0] == "USER")
    run = " ".join(runner[check])

    assert (user < check, check == max(i for i, w in enumerate(runner) if w[0] == "RUN")) == (
        True,
        True,
    )
    assert "DEVOPS_CLI_USER_DATA_ROOT=/opt/devops-tools" in run


# ── The check of one tool ───────────────────────────────────────────────────────────────────


def _tool(name: str = "ruff", **fields: Any) -> RunnerTool:
    return RunnerTool(name, ToolSource.IMAGE_PIN, ("job",), (name, "--version"), **fields)


def test_a_tool_passes_when_its_version_command_prints_its_pin(process_fake: ProcessFake) -> None:
    process_fake.answer("ruff --version", ProcessAnswer(stdout="ruff 0.16.8\n"))

    assert tool_failure(_tool(pin="0.16.8")) is None


def test_a_tool_fails_when_it_prints_another_version(process_fake: ProcessFake) -> None:
    process_fake.answer("ruff --version", ProcessAnswer(stdout="ruff 0.15.0\n"))

    assert tool_failure(_tool(pin="0.16.8")) == (
        "Runner tool 'ruff' does not hold its pin '0.16.8'. "
        "Its version command printed: ruff 0.15.0"
    )


def test_a_tool_fails_when_its_version_command_fails(process_fake: ProcessFake) -> None:
    process_fake.answer("ruff --version", ProcessAnswer(returncode=127))

    assert tool_failure(_tool(pin="0.16.8")) == (
        "Runner tool 'ruff': `ruff --version` exited with status 127."
    )


def test_a_tool_with_no_command_fails_when_it_is_not_on_path(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)

    assert tool_failure(RunnerTool("nice", ToolSource.BASE, ("ci:security",))) == (
        "Runner tool 'nice' is not on PATH."
    )


def test_a_tool_with_no_pin_passes_on_any_output(process_fake: ProcessFake) -> None:
    process_fake.answer("git --version", ProcessAnswer(stdout="git version 2.47.3\n"))

    assert tool_failure(RunnerTool("git", ToolSource.APT, ("job",), ("git", "--version"))) is None


def test_a_tool_of_the_lock_must_link_at_its_locked_version(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["devops", "install-tools", "--check"],
        ProcessAnswer(returncode=1, stderr="trivy 0.75.0: not installed\n"),
    )
    tool = RunnerTool("trivy", ToolSource.TOOLS_LOCK, ("gate:static",), ("trivy", "--version"))

    assert tool_failure(tool) == (
        "Runner tool 'trivy' is not at its locked version. trivy 0.75.0: not installed"
    )
    (call,) = process_fake.calls
    assert call.argv[:6] == (
        "devops",
        "install-tools",
        "--check",
        "--tool",
        "trivy",
        "--target-dir",
    )


def test_the_check_of_a_tool_of_the_lock_runs_the_version_command_after_the_pin_check(
    process_fake: ProcessFake,
) -> None:
    version = load_tools_lock().tools()["trivy"].version
    process_fake.answer("trivy --version", ProcessAnswer(stdout=f"Version: {version}\n"))
    tool = RunnerTool("trivy", ToolSource.TOOLS_LOCK, ("gate:static",), ("trivy", "--version"))

    assert (tool_failure(tool), [call.argv[0] for call in process_fake.calls]) == (
        None,
        ["devops", "trivy"],
    )


@pytest.fixture
def every_tool_passes(process_fake: ProcessFake) -> ProcessFake:
    """Each version command prints its own pin, and each pin check of the lock succeeds."""

    def answer(call: Any) -> ProcessAnswer:
        if call.argv[1:2] == ("install-tools",):
            return ProcessAnswer()
        # The process runner puts preview flags after `uv`, so the tool is found by its program.
        tool = next(t for t in RUNNER_TOOLS if t.check and t.check[0] == call.argv[0])
        return ProcessAnswer(stdout=f"{tool.name} {expected_text(tool)}\n")

    process_fake.answer(lambda call: True, answer)
    return process_fake


def test_every_tool_of_the_table_has_a_check_that_the_fake_can_answer(
    every_tool_passes: ProcessFake,
) -> None:
    """This fails when a pin cannot be read from its source, such as a dev dependency that is
    not installed."""
    assert failures() == []


def test_main_prints_each_failure_and_exits_1(
    process_fake: ProcessFake, capsys: pytest.CaptureFixture[str]
) -> None:
    process_fake.answer(lambda call: call.argv[0] == "uv", ProcessAnswer(returncode=127))

    assert main() == 1
    assert "Runner tool 'uv': `uv --version` exited with status 127." in capsys.readouterr().err


def test_main_exits_0_when_every_tool_passes(
    every_tool_passes: ProcessFake, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main() == 0
    assert f"All {len(RUNNER_TOOLS)} runner tools run at their pins." in capsys.readouterr().out


def test_a_hook_that_the_job_leaves_out_is_a_hook_of_the_config_and_runs_programs_not_in_the_image() -> (
    None
):
    """The Job leaves out a hook only when its program is a decided absence (#3134)."""
    config = yaml.safe_load(_text(".pre-commit-config.yaml"))
    ids = {hook["id"] for repo in config["repos"] for hook in repo["hooks"]}

    assert (
        sorted(set(HOOK_PROGRAMS) - ids),
        sorted(
            p for programs in HOOK_PROGRAMS.values() for p in programs if p not in NOT_IN_RUNNER
        ),
    ) == ([], [])


def test_a_hook_is_missing_its_program_when_the_program_is_not_on_the_search_path(
    tmp_path: Path,
) -> None:
    empty, held = tmp_path / "empty", tmp_path / "held"
    empty.mkdir()
    held.mkdir()
    (held / "actionlint").write_text("#!/bin/sh\n", encoding="utf-8")
    (held / "actionlint").chmod(0o755)

    assert (hooks_without_programs(str(empty)), hooks_without_programs(str(held))) == (
        tuple(HOOK_PROGRAMS),
        (),
    )
