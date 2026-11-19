"""The tools of each infra repo: `devops devcontainer post-start` runs the install command of the
project profile of each infra repo in its checkout (#6336)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.config.defaults import DEFAULT_INFRA_TOOLS_INSTALL_TIMEOUT_SECONDS
from devops_cli.config.settings import load_settings
from devops_cli.infra.tools import install_repo_tools
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

_FIRST = "example-org/infra"
_SECOND = "example-org/lab"


def _checkout(root: Path, *, project_file: str | None = None) -> Path:
    """A checkout of the type `ansible-k8s`, with a project file when one is given."""
    root.mkdir(parents=True)
    (root / "ansible.cfg").write_text("[defaults]\n", encoding="utf-8")
    if project_file is not None:
        (root / ".devops").mkdir()
        (root / ".devops" / "project.toml").write_text(project_file, encoding="utf-8")
    return root


@pytest.fixture
def repos(tmp_path: Path, config: Callable[..., Path]) -> Callable[..., list[Path]]:
    """Write one `infra.repos` entry for each checkout path, and give the paths."""

    def write(*paths: Path) -> list[Path]:
        names = (_FIRST, _SECOND)[: len(paths)]
        entries = [
            {"repo": name, "path": str(path)} for name, path in zip(names, paths, strict=True)
        ]
        config(infra={"repos": entries})
        return list(paths)

    return write


def _installs(process: ProcessFake) -> list[tuple[tuple[str, ...], Path | None, float]]:
    return [(call.argv, call.cwd, call.timeout) for call in process.calls]


def test_the_install_command_of_the_template_runs_in_each_checkout(
    tmp_path: Path, repos: Callable[..., list[Path]], process_fake: ProcessFake
) -> None:
    first, second = repos(_checkout(tmp_path / "infra"), _checkout(tmp_path / "lab"))

    lines = install_repo_tools(load_settings())

    assert _installs(process_fake) == [
        (("make", "install"), first, DEFAULT_INFRA_TOOLS_INSTALL_TIMEOUT_SECONDS),
        (("make", "install"), second, DEFAULT_INFRA_TOOLS_INSTALL_TIMEOUT_SECONDS),
    ]
    assert lines == [
        f"Installed the tools of {_FIRST} in {first} (make install)",
        f"Installed the tools of {_SECOND} in {second} (make install)",
    ]


def test_the_project_file_gives_the_install_command(
    tmp_path: Path, repos: Callable[..., list[Path]], process_fake: ProcessFake
) -> None:
    project = 'extends = "ansible-k8s"\n[tools]\ninstall = ["just", "tools"]\n'
    (first,) = repos(_checkout(tmp_path / "infra", project_file=project))

    install_repo_tools(load_settings())

    assert _installs(process_fake) == [
        (("just", "tools"), first, DEFAULT_INFRA_TOOLS_INSTALL_TIMEOUT_SECONDS)
    ]


def test_a_missing_checkout_is_a_warning_and_the_next_repo_goes_on(
    tmp_path: Path, repos: Callable[..., list[Path]], process_fake: ProcessFake
) -> None:
    missing, second = repos(tmp_path / "missing", _checkout(tmp_path / "lab"))

    lines = install_repo_tools(load_settings())

    assert _installs(process_fake) == [
        (("make", "install"), second, DEFAULT_INFRA_TOOLS_INSTALL_TIMEOUT_SECONDS)
    ]
    assert lines[0] == f"Warning: {_FIRST} has no checkout at {missing}; no tools installed"


def test_an_empty_install_command_runs_nothing(
    tmp_path: Path, repos: Callable[..., list[Path]], process_fake: ProcessFake
) -> None:
    (first,) = repos(_checkout(tmp_path / "infra", project_file="[tools]\ninstall = []\n"))

    lines = install_repo_tools(load_settings())

    assert (process_fake.calls, lines) == (
        [],
        [f"{_FIRST} in {first} declares no install command (tools.install)"],
    )


def test_an_invalid_project_file_is_a_warning(
    tmp_path: Path, repos: Callable[..., list[Path]], process_fake: ProcessFake
) -> None:
    repos(_checkout(tmp_path / "infra", project_file='extends = "cobol"\n'))

    lines = install_repo_tools(load_settings())

    assert process_fake.calls == []
    assert lines[0].startswith(f"Warning: the project profile of {_FIRST} is invalid: ")


def test_a_failed_install_is_a_warning_with_its_last_line_and_the_next_repo_goes_on(
    tmp_path: Path, repos: Callable[..., list[Path]], process_fake: ProcessFake
) -> None:
    first, second = repos(_checkout(tmp_path / "infra"), _checkout(tmp_path / "lab"))
    failure = "make: *** No rule to make target 'install'.  Stop.\n"

    def by_checkout(call: ProcessCall) -> ProcessAnswer:
        return ProcessAnswer(returncode=2, stderr=failure) if call.cwd == first else ProcessAnswer()

    process_fake.answer("make install", by_checkout)

    lines = install_repo_tools(load_settings())

    assert lines == [
        f"Warning: the install of the tools of {_FIRST} in {first} failed with exit code 2: "
        "make: *** No rule to make target 'install'.  Stop.",
        f"Installed the tools of {_SECOND} in {second} (make install)",
    ]


def test_an_install_that_times_out_is_a_warning(
    tmp_path: Path, repos: Callable[..., list[Path]], process_fake: ProcessFake
) -> None:
    (first,) = repos(_checkout(tmp_path / "infra"))
    timeout = subprocess.TimeoutExpired(
        ["make", "install"], DEFAULT_INFRA_TOOLS_INSTALL_TIMEOUT_SECONDS
    )
    process_fake.answer("make install", ProcessAnswer(side_effect=timeout))

    lines = install_repo_tools(load_settings())

    assert lines == [
        f"Warning: the install of the tools of {_FIRST} in {first} did not end in "
        f"{DEFAULT_INFRA_TOOLS_INSTALL_TIMEOUT_SECONDS:.0f} s"
    ]


def test_a_dry_run_runs_no_install(
    tmp_path: Path, repos: Callable[..., list[Path]], process_fake: ProcessFake
) -> None:
    (first,) = repos(_checkout(tmp_path / "infra"))

    lines = install_repo_tools(load_settings(), dry_run=True)

    assert (process_fake.calls, lines) == (
        [],
        [f"Would install the tools of {_FIRST} in {first} (make install)"],
    )


def test_no_infra_repo_gives_no_line(
    config: Callable[..., Path], process_fake: ProcessFake
) -> None:
    config(infra={"repos": []})

    assert (install_repo_tools(load_settings()), process_fake.calls) == ([], [])
