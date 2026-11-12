"""`devops infra onboard`: the report of an infra repo, and the settings entry that a person
confirms (#5121).

The command layer owns the options, the refusal of an agent that raises the access level, the
dry run, the write of the entry and the exit code. The rows are the domain's
(`tests/infra/test_onboard.py`).
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from syrupy.assertion import SnapshotAssertion

from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessFake
from tests.support.infra import (
    KUBE_CONTEXT,
    OLD_COMMIT,
    ORIGIN_COMMIT,
    answer_default_branch,
    answer_infra_reads,
)

REPO = "example-org/infra"


@pytest.fixture
def ready(
    infra_repo: Path,
    ansible_installed: Path,
    ssh_key_dir: Path,
    known_hosts: Path,
    config: Callable[..., Path],
) -> Path:
    """The complete repo, the tool environment, the SSH key and `known_hosts`; no entry yet."""
    known_hosts.parent.mkdir(parents=True)
    known_hosts.write_text("", encoding="utf-8")
    return config(ssh={"key_dir": str(ssh_key_dir)})


def _entries(config_file: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    entries: list[dict[str, Any]] = data.get("infra", {}).get("repos", [])
    return entries


def test_onboard_prints_one_row_for_each_check(
    cli: Callable[..., Any],
    ready: Path,
    infra_repo: Path,
    process_fake: ProcessFake,
    person_caller: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Without the entry, the last row is missing, so the command exits 1 and writes nothing."""
    answer_infra_reads(process_fake, infra_repo)
    before = ready.read_bytes()

    result = cli(
        "infra", "onboard", REPO, "--path", str(infra_repo), "--kube-context", KUBE_CONTEXT
    )

    assert result.exit_code == 1
    assert result.output.replace(str(infra_repo), "<repo>") == snapshot
    assert ready.read_bytes() == before


def test_onboard_names_the_commit_it_reads_and_a_checkout_on_another_branch(
    cli: Callable[..., Any],
    ready: Path,
    infra_repo: Path,
    process_fake: ProcessFake,
    person_caller: None,
) -> None:
    """The checkout is on an old branch: one line says so under the commit that the rows read."""
    answer_infra_reads(process_fake, infra_repo)
    answer_default_branch(
        process_fake, infra_repo, checkout_branch="feat/old", checkout_commit=OLD_COMMIT
    )

    result = cli(
        "infra", "onboard", REPO, "--path", str(infra_repo), "--kube-context", KUBE_CONTEXT
    )

    assert result.output.splitlines()[1:3] == [
        f"Reads origin/main at {ORIGIN_COMMIT}, not the working tree of the checkout.",
        f"The checkout is on the branch feat/old at {OLD_COMMIT}, not on origin/main.",
    ]


def test_a_person_confirms_the_entry_at_level_none(
    cli: Callable[..., Any],
    ready: Path,
    infra_repo: Path,
    process_fake: ProcessFake,
    person_caller: None,
) -> None:
    answer_infra_reads(process_fake, infra_repo)

    result = cli(
        "infra",
        "onboard",
        REPO,
        "--path",
        str(infra_repo),
        "--kube-context",
        KUBE_CONTEXT,
        "--confirm",
    )

    assert result.exit_code == 0, result.output
    assert _entries(ready) == [
        {
            "repo": REPO,
            "path": str(infra_repo),
            "kube_context": KUBE_CONTEXT,
            "ssh_key_prefix": "ansible",
            "agent_access": "none",
        }
    ]
    assert (
        f"17. The repository is in infra.repos: present (agent access none; written to {ready})"
        in result.output
    )


def test_a_person_sets_the_agent_access_level(
    cli: Callable[..., Any],
    ready: Path,
    infra_repo: Path,
    process_fake: ProcessFake,
    person_caller: None,
) -> None:
    answer_infra_reads(process_fake, infra_repo)

    result = cli(
        "infra", "onboard", REPO, "--path", str(infra_repo), "--agent-access", "full", "--confirm"
    )

    assert [entry["agent_access"] for entry in _entries(ready)] == ["full"]
    assert result.exit_code == 1  # the kube context is not set


def test_an_agent_cannot_raise_the_agent_access_level(
    cli: Callable[..., Any],
    ready: Path,
    infra_repo: Path,
    process_fake: ProcessFake,
    agent_caller: None,
) -> None:
    """The refusal comes first: no process starts and the config file keeps every byte."""
    before = ready.read_bytes()

    result = cli(
        "infra", "onboard", REPO, "--path", str(infra_repo), "--agent-access", "full", "--confirm"
    )

    assert result.exit_code == 1
    assert "infra.repos[].agent_access" in result.output
    assert (process_fake.calls, ready.read_bytes()) == ([], before)


def test_an_agent_keeps_the_level_that_a_person_set(
    cli: Callable[..., Any],
    ready: Path,
    infra_repo: Path,
    process_fake: ProcessFake,
    config: Callable[..., Path],
    agent_caller: None,
) -> None:
    """An agent may confirm the entry. With no `--agent-access`, the level stays as it was."""
    entry = {"repo": REPO, "path": str(infra_repo), "agent_access": "full"}
    config(infra={"repos": [entry]})
    answer_infra_reads(process_fake, infra_repo)

    result = cli("infra", "onboard", REPO, "--kube-context", KUBE_CONTEXT, "--confirm")

    assert result.exit_code == 0, result.output
    assert [(e["agent_access"], e["kube_context"]) for e in _entries(ready)] == [
        ("full", KUBE_CONTEXT)
    ]


def test_dry_run_starts_no_process_and_writes_nothing(
    cli: Callable[..., Any],
    ready: Path,
    infra_repo: Path,
    tmp_path: Path,
    process_fake: ProcessFake,
    person_caller: None,
    snapshot: SnapshotAssertion,
) -> None:
    before = ready.read_bytes()

    result = cli("infra", "onboard", REPO, "--path", str(infra_repo), "--confirm", "--dry-run")

    assert result.exit_code == 0, result.output
    assert (process_fake.calls, ready.read_bytes()) == ([], before)
    assert result.output.replace(str(tmp_path), "<tmp>") == snapshot


def test_a_local_path_names_the_repository_of_its_origin(
    cli: Callable[..., Any],
    ready: Path,
    infra_repo: Path,
    git_fake: GitFake,
    person_caller: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repo at `<tmp>/repo` has the origin `https://github.com/example/service.git`."""
    monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: f"/usr/local/bin/{Path(cmd).name}")
    (infra_repo / ".git").mkdir()
    git_fake.replay("repository_origin")
    answer_infra_reads(git_fake, infra_repo)

    result = cli("infra", "onboard", str(infra_repo), "--kube-context", KUBE_CONTEXT, "--confirm")

    assert [(e["repo"], e["path"]) for e in _entries(ready)] == [
        ("example/service", str(infra_repo))
    ]
    assert result.exit_code == 0, result.output


def test_a_repo_with_no_checkout_is_refused(
    cli: Callable[..., Any], ready: Path, tmp_path: Path, process_fake: ProcessFake
) -> None:
    result = cli("infra", "onboard", REPO, "--path", str(tmp_path / "absent"))

    assert result.exit_code == 1
    assert "No checkout of the infra repo example-org/infra" in result.output
    assert process_fake.calls == []
