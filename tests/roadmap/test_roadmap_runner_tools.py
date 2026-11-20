"""The table of the tools that the runner image must hold (#3072).

The first tests read the sources of the gate offline: the rows of `devops ci`, the hooks of
`.pre-commit-config.yaml`, the required jobs of `ci.yml` and the live-marked tests. They fail when a
program that one of them needs is in neither `RUNNER_TOOLS` nor `NOT_IN_RUNNER`. The last tests run
the check of a tool over the process fake. No test compares a tool version with the `Dockerfile`:
the devtools image gives the version of each tool (#5585, #4361).
"""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import os
import shlex
import subprocess
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.commands.ci import get_check_specs
from devops_cli.exceptions import ToolExecutionError
from devops_cli.roadmap.runner_tools import (
    CHECKOUT_TOOLS,
    HOOK_PROGRAMS,
    IMAGE_TOOLS,
    NOT_IN_RUNNER,
    RUNNER_TOOLS,
    RunnerTool,
    ToolSource,
    bootstrap_checkout,
    checkout_environment,
    expected_text,
    failures,
    hooks_without_programs,
    main,
    tool_failure,
    tool_names,
)
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import PREVIEW
from tests.support.paths import REPO_ROOT, TESTS_ROOT
from tests.support.trees import parse_python_file

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
    """The tools that the required jobs `static` and `test-shard` of `ci.yml` install, by job."""
    jobs = yaml.safe_load(_text(".github/workflows/ci.yml"))["jobs"]
    found: dict[str, set[str]] = {}
    # The gate `test` installs its tools in the shard jobs `test-shard` (#3050).
    for name, job in (("static", "static"), ("test", "test-shard")):
        tools: set[str] = set()
        for step in jobs[job]["steps"]:
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
        for node in ast.walk(parse_python_file(path)):
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


# ── The check of one tool ───────────────────────────────────────────────────────────────────

PROJECT = importlib.metadata.version("devops-cli")
DEVOPS = next(tool for tool in RUNNER_TOOLS if tool.name == "devops")
UV = next(tool for tool in RUNNER_TOOLS if tool.name == "uv")


def _argv(call: ProcessCall) -> tuple[str, ...]:
    """The words of a call, without the preview flags that the process runner puts after `uv`."""
    return tuple(word for word in call.argv if word not in PREVIEW)


def test_the_project_passes_when_it_prints_its_installed_version(
    process_fake: ProcessFake,
) -> None:
    process_fake.answer("devops --version", ProcessAnswer(stdout=f"devops {PROJECT}\n"))

    assert tool_failure(DEVOPS) is None


def test_the_project_fails_when_it_prints_another_version(process_fake: ProcessFake) -> None:
    process_fake.answer("devops --version", ProcessAnswer(stdout="devops 0.0.1\n"))

    assert tool_failure(DEVOPS) == (
        f"Runner tool 'devops' is not at its installed version '{PROJECT}'. "
        "Its version command printed: devops 0.0.1"
    )


def test_a_tool_fails_when_its_version_command_fails(process_fake: ProcessFake) -> None:
    process_fake.answer(
        lambda call: _argv(call) == ("uv", "--version"), ProcessAnswer(returncode=127)
    )

    assert tool_failure(UV) == "Runner tool 'uv': `uv --version` exited with status 127."


def test_a_tool_with_no_command_fails_when_it_is_not_on_path(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("shutil.which", lambda _name, path=None: None)

    assert tool_failure(RunnerTool("nice", ToolSource.BASE, ("ci:security",))) == (
        "Runner tool 'nice' is not on PATH."
    )


def test_a_tool_of_the_devtools_image_passes_on_any_version_and_runs_only_its_version_command(
    process_fake: ProcessFake,
) -> None:
    """The devtools image gives the version of these tools, and the `Dockerfile` pins that image
    by digest, so the check compares no version: the tool runs (#5585, #4361)."""
    process_fake.answer(lambda call: True, ProcessAnswer(stdout="tool 0.0.0\n"))
    pinned = [tool for tool in RUNNER_TOOLS if tool.source is ToolSource.DEVTOOLS]

    assert {tool.name: tool_failure(tool) for tool in pinned} == {
        tool.name: None for tool in pinned
    }
    assert [call.argv[0] for call in process_fake.calls] == [tool.check[0] for tool in pinned]


@pytest.fixture
def every_tool_passes(process_fake: ProcessFake) -> ProcessFake:
    """Each version command exits 0, and the project prints its installed version."""

    def answer(call: Any) -> ProcessAnswer:
        # The process runner puts preview flags after `uv`, so the tool is found by its program.
        tool = next(t for t in RUNNER_TOOLS if t.check and t.check[0] == call.argv[0])
        return ProcessAnswer(stdout=f"{tool.name} {expected_text(tool)}\n")

    process_fake.answer(lambda call: True, answer)
    return process_fake


def test_every_tool_of_the_image_has_a_check_that_the_fake_can_answer(
    every_tool_passes: ProcessFake,
) -> None:
    """This fails when an installed version cannot be read, such as a project that is not
    installed."""
    assert failures(IMAGE_TOOLS) == []


def test_main_prints_each_failure_and_exits_1(
    process_fake: ProcessFake, capsys: pytest.CaptureFixture[str]
) -> None:
    process_fake.answer(lambda call: call.argv[0] == "uv", ProcessAnswer(returncode=127))

    assert main([]) == 1
    assert "Runner tool 'uv': `uv --version` exited with status 127." in capsys.readouterr().err


def test_main_checks_the_tools_of_the_image_and_no_tool_of_the_checkout(
    every_tool_passes: ProcessFake, capsys: pytest.CaptureFixture[str]
) -> None:
    """The image holds no dev dependency (#6517): pytest, ruff, mypy and pre-commit come from the
    venv of a checkout after its bootstrap, so the check of the image runs none of them."""
    assert main([]) == 0
    assert f"All {len(IMAGE_TOOLS)} runner tools are on PATH and run." in capsys.readouterr().out
    started = {call.argv[0] for call in every_tool_passes.calls}
    assert started & {"pytest", "ruff", "mypy", "pre-commit"} == set()


# ── The coder environment of a checkout (#6517) ──────────────────────────────────────────────

SYNC = ("uv", "sync", "--locked", "--group", "dev")
NPM = ("npm", "ci", "--ignore-scripts")
LOCK = "version = 1\n"


def _checkout(root: Path, *files: str) -> Path:
    checkout = root / "checkout"
    checkout.mkdir()
    for name in files:
        (checkout / name).write_text(LOCK, encoding="utf-8")
    return checkout


def _seed(root: Path, record: dict[str, str]) -> Path:
    """A uv-seed volume (#4814): a cache with one entry, and the record of what filled it."""
    seed = root / "uv-seed"
    (seed / "cache" / "wheels-v5").mkdir(parents=True)
    (seed / "cache" / "wheels-v5" / "entry").write_text("wheel", encoding="utf-8")
    (seed / "seed.json").write_text(json.dumps(record), encoding="utf-8")
    return seed


def _record(checkout: Path, **changed: str) -> dict[str, str]:
    lock = hashlib.sha256((checkout / "uv.lock").read_bytes()).hexdigest()
    minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    return {"uv": "job-uv", "python": minor, "uv_lock_sha256": lock, **changed}


@pytest.fixture
def uv_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cache = tmp_path / "home" / ".cache" / "uv"
    monkeypatch.setenv("UV_CACHE_DIR", str(cache))
    return cache


def test_the_bootstrap_syncs_the_dev_group_online_and_installs_the_locked_npm_packages(
    tmp_path: Path, process_fake: ProcessFake, uv_cache: Path
) -> None:
    """With no seed, the bootstrap is the online sync of the devcontainer and the clean npm
    install, both in the checkout."""
    checkout = _checkout(tmp_path, "uv.lock", "package-lock.json")

    bootstrap_checkout(checkout, seed=tmp_path / "no-seed")

    assert [(_argv(call), call.cwd, call.env) for call in process_fake.calls] == [
        (SYNC, checkout, {"UV_HTTP_RETRIES": "5", "UV_MALWARE_CHECK": "1"}),
        (NPM, checkout, None),
    ]
    assert not uv_cache.exists()


def test_the_bootstrap_copies_a_seed_that_fits_and_syncs_offline(
    tmp_path: Path, process_fake: ProcessFake, uv_cache: Path
) -> None:
    """CI checked the hashes of the seed when it built it, so the offline sync runs with no
    malware check (#4814)."""
    process_fake.answer(
        lambda call: _argv(call) == ("uv", "--version"),
        ProcessAnswer(stdout="uv job-uv (x86_64-unknown-linux)\n"),
    )
    checkout = _checkout(tmp_path, "uv.lock")
    seed = _seed(tmp_path, _record(checkout))

    bootstrap_checkout(checkout, seed=seed)

    synced = [(_argv(call), call.cwd, call.env) for call in process_fake.calls]
    assert synced[-1] == ((*SYNC, "--offline"), checkout, {"UV_MALWARE_CHECK": "0"})
    assert (uv_cache / "wheels-v5" / "entry").read_text(encoding="utf-8") == "wheel"


@pytest.mark.parametrize("changed", [{"uv_lock_sha256": "other-lock"}, {"uv": "other-uv"}])
def test_a_seed_that_does_not_fit_the_checkout_leaves_the_sync_online(
    tmp_path: Path, process_fake: ProcessFake, uv_cache: Path, changed: dict[str, str]
) -> None:
    process_fake.answer(
        lambda call: _argv(call) == ("uv", "--version"), ProcessAnswer(stdout="uv job-uv\n")
    )
    checkout = _checkout(tmp_path, "uv.lock")
    seed = _seed(tmp_path, _record(checkout, **changed))

    bootstrap_checkout(checkout, seed=seed)

    assert _argv(process_fake.calls[-1]) == SYNC
    assert not uv_cache.exists()


def test_a_sync_that_may_lock_again_runs_without_locked(
    tmp_path: Path, process_fake: ProcessFake, uv_cache: Path
) -> None:
    """A Job on an existing branch syncs as `uv run` does, so a stale `uv.lock` is locked again
    and does not fail the bootstrap (#6517)."""
    checkout = _checkout(tmp_path, "uv.lock")

    bootstrap_checkout(checkout, locked=False, seed=tmp_path / "no-seed")

    assert [_argv(call) for call in process_fake.calls] == [("uv", "sync", "--group", "dev")]


def test_a_checkout_with_no_lock_file_gets_no_bootstrap_command(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    bootstrap_checkout(_checkout(tmp_path), seed=tmp_path / "no-seed")

    assert process_fake.calls == []


def test_a_failed_sync_raises_with_the_command_and_its_output(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    process_fake.answer("uv", ProcessAnswer(returncode=2, stderr="error: Failed to fetch\n"))
    checkout = _checkout(tmp_path, "uv.lock", "package-lock.json")

    with pytest.raises(ToolExecutionError) as raised:
        bootstrap_checkout(checkout, seed=tmp_path / "no-seed")

    assert str(raised.value) == (
        "uv sync --locked --group dev exited with status 2.\nerror: Failed to fetch"
    )
    assert [_argv(call)[0] for call in process_fake.calls] == ["uv"]


def test_the_checkout_environment_puts_node_modules_and_the_venv_of_the_checkout_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin")
    checkout = tmp_path / "checkout"

    assert checkout_environment(checkout) == {
        "PATH": os.pathsep.join(
            [str(checkout / "node_modules" / ".bin"), str(checkout / ".venv" / "bin"), "/usr/bin"]
        )
    }


def _venv(checkout: Path, *names: str) -> None:
    """The programs `names` in the venv of `checkout`, as `uv sync` puts them there."""
    folder = checkout / ".venv" / "bin"
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_text("#!/bin/sh\n", encoding="utf-8")
        (folder / name).chmod(0o755)


def test_a_tool_of_the_checkout_runs_from_the_venv_of_the_checkout(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    checkout = _checkout(tmp_path)
    _venv(checkout, *(tool.name for tool in CHECKOUT_TOOLS))

    assert failures(CHECKOUT_TOOLS, checkout) == []
    assert {(call.cwd, call.env["PATH"] if call.env else "") for call in process_fake.calls} == {
        (checkout, checkout_environment(checkout)["PATH"])
    }


def test_a_tool_of_the_checkout_fails_when_the_venv_of_the_checkout_lacks_it(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    checkout = _checkout(tmp_path)
    _venv(checkout, *(tool.name for tool in CHECKOUT_TOOLS if tool.name != "ruff"))

    assert failures(CHECKOUT_TOOLS, checkout) == [
        f"Runner tool 'ruff' is not in the venv of the checkout {checkout}."
    ]


def test_main_with_a_checkout_bootstraps_it_and_checks_its_tools(
    tmp_path: Path, process_fake: ProcessFake, capsys: pytest.CaptureFixture[str]
) -> None:
    """The smoke test of the runner image runs this on a copy of the checkout (#6517)."""
    checkout = _checkout(tmp_path, "uv.lock")

    def sync(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        _venv(checkout, *(tool.name for tool in CHECKOUT_TOOLS))
        return subprocess.CompletedProcess(call.argv, 0, stdout="", stderr="")

    process_fake.answer(
        lambda call: _argv(call)[:2] == ("uv", "sync"), ProcessAnswer(side_effect=sync)
    )

    assert main([str(checkout)]) == 0
    assert f"All {len(CHECKOUT_TOOLS)} runner tools are on PATH and run." in capsys.readouterr().out
    started = [_argv(call)[0] for call in process_fake.calls]
    assert started == ["uv", *(tool.check[0] for tool in CHECKOUT_TOOLS)]


def test_main_with_a_checkout_exits_1_when_the_bootstrap_fails(
    tmp_path: Path, process_fake: ProcessFake, capsys: pytest.CaptureFixture[str]
) -> None:
    process_fake.answer("uv", ProcessAnswer(returncode=2, stderr="error: Failed to fetch\n"))

    assert main([str(_checkout(tmp_path, "uv.lock"))]) == 1
    assert "uv sync --locked --group dev exited with status 2." in capsys.readouterr().err


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
