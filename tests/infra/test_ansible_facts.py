"""The Ansible tool environment comes from the `ansible-runner` on PATH (#4362), and its
`ansible-doc` lists the roles of the pinned collections (#6678)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.exceptions.infra import InfraReadError
from devops_cli.infra import ansible_facts
from devops_cli.infra.ansible_facts import AnsibleTool, ansible_tool
from tests.support.fakes.process import ProcessAnswer, ProcessFake


def _stand_in(folder: Path) -> Path:
    """An executable `ansible-runner` stand-in in `folder`."""
    folder.mkdir(parents=True, exist_ok=True)
    stand_in = folder / "ansible-runner"
    stand_in.write_text("#!/bin/sh\n", encoding="utf-8")
    stand_in.chmod(0o755)
    return stand_in


def test_the_tool_environment_is_the_folder_of_the_ansible_runner_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A link on PATH names the environment of the file that it points to, where the other
    Ansible commands are."""
    real = _stand_in(tmp_path / "venv" / "bin")
    on_path = tmp_path / "bin"
    on_path.mkdir()
    (on_path / "ansible-runner").symlink_to(real)
    monkeypatch.setenv("PATH", str(on_path))

    tool = ansible_tool()

    assert (tool.installed, tool.argv("ansible-config", "dump")) == (
        True,
        [str(real.parent.resolve() / "ansible-config"), "dump"],
    )


def test_no_ansible_runner_on_path_gives_no_tool_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no `ansible-runner` on PATH, no other folder gives the tool environment, and a dry run
    shows each command with no folder."""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    tool = ansible_tool()

    assert (tool.installed, tool.argv("ansible-config", "dump")) == (
        False,
        ["ansible-config", "dump"],
    )


def test_a_role_listing_that_is_not_a_mapping_is_refused(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """`ansible-doc -t role -l -j` prints a JSON list in place of the mapping of the roles."""
    tool = AnsibleTool(bin_dir=tmp_path / "bin")
    process_fake.answer([str(tmp_path / "bin" / "ansible-doc")], ProcessAnswer(stdout="[]\n"))

    with pytest.raises(InfraReadError) as raised:
        ansible_facts.read_collection_roles(tool, tmp_path, tmp_path / "collections")

    assert (
        raised.value.message
        == "ansible-doc -t role -l -j did not print the JSON that devops reads."
    )
