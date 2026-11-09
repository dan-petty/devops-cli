"""Tests for workspace subcommands and multi-root workspace file generation."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from devops_cli.commands.workspace import app as workspace_app
from devops_cli.commands.workspace import sync_from_repos
from devops_cli.config.defaults import DEFAULT_MAX_AST_FILE_SIZE_BYTES
from devops_cli.main import app
from tests.support.fakes.process import ProcessAnswer, ProcessFake

runner = CliRunner()


def test_sync_from_repos_generates_multiroot_workspace(tmp_path: Path) -> None:
    repos_root = tmp_path / "repos"
    alpha = repos_root / "group-a" / "alpha"
    beta = repos_root / "group-b" / "beta"
    (alpha / ".git").mkdir(parents=True)
    (beta / ".git").mkdir(parents=True)

    workspace_file = tmp_path / ".code-workspace"

    sync_from_repos(repos_root, workspace_file)

    data = json.loads(workspace_file.read_text(encoding="utf-8"))
    assert [folder["path"] for folder in data["folders"]] == [
        str(alpha.resolve()),
        str(beta.resolve()),
        ".",
    ]
    assert data["settings"]["editor.formatOnSave"] is True
    assert data["settings"]["files.trimTrailingWhitespace"] is True


def test_workspace_generate_resolves_default_paths_from_project_root(
    tmp_path: Path,
    config: Callable[..., Path],
) -> None:
    project_root = tmp_path / "project"
    repo_dir = project_root / "group" / "repo"
    repo_dir.mkdir(parents=True)
    (repo_dir / ".git").mkdir()
    workspace_file = project_root / ".code-workspace"

    config(repos={"base_dir": str(project_root)}, workspace={"file": str(workspace_file)})
    result = runner.invoke(app, ["workspace", "generate"], catch_exceptions=False)

    assert result.exit_code == 0
    assert workspace_file.exists()

    data = json.loads(workspace_file.read_text(encoding="utf-8"))
    assert [folder["path"] for folder in data["folders"]] == [str(repo_dir.resolve()), "."]


def test_workspace_open_resolves_default_workspace_file_from_project_root(
    tmp_path: Path,
    config: Callable[..., Path],
    process_fake: ProcessFake,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    workspace_file = project_root / ".code-workspace"
    workspace_file.write_text('{"folders": [{"path": "."}]}\n', encoding="utf-8")

    config(repos={"base_dir": str(project_root)}, workspace={"file": str(workspace_file)})
    process_fake.answer(["code", str(workspace_file)], ProcessAnswer(returncode=0))

    result = runner.invoke(app, ["workspace", "open"], catch_exceptions=False)
    assert result.exit_code == 0
    assert any(call.argv == ("code", str(workspace_file)) for call in process_fake.calls)


def test_workspace_add_remove_commands(
    tmp_path: Path,
    config: Callable[..., Path],
) -> None:
    """Verify workspace add, remove, and generate subcommands."""
    config(repos={"base_dir": str(tmp_path)})
    ws_file = tmp_path / "test.code-workspace"
    ws_file.write_text(json.dumps({"folders": [{"path": "."}]}), encoding="utf-8")

    res_add = runner.invoke(workspace_app, ["add", str(tmp_path), "--workspace", str(ws_file)])
    assert res_add.exit_code == 0

    res_remove = runner.invoke(
        workspace_app, ["remove", str(tmp_path), "--workspace", str(ws_file)]
    )
    assert res_remove.exit_code == 0

    res_gen = runner.invoke(workspace_app, ["generate", "--workspace", str(ws_file)])
    assert res_gen.exit_code == 0


def test_workspace_edge_cases_and_clean(
    tmp_path: Path,
    config: Callable[..., Path],
    isolate_data_dir: Path,
) -> None:
    """Verify duplicate add, missing remove, missing open, and clean subcommands."""
    config(repos={"base_dir": str(tmp_path)})
    ws_file = tmp_path / "test.code-workspace"
    ws_file.write_text(
        json.dumps({"folders": [{"path": str(tmp_path.resolve())}]}), encoding="utf-8"
    )

    # Add duplicate folder
    res_dup = runner.invoke(workspace_app, ["add", str(tmp_path), "--workspace", str(ws_file)])
    assert res_dup.exit_code == 0
    assert "already" in res_dup.output.lower()

    # Remove non-existent folder
    res_not_pres = runner.invoke(
        workspace_app, ["remove", "/nonexistent/path", "--workspace", str(ws_file)]
    )
    assert res_not_pres.exit_code == 0
    assert "not found" in res_not_pres.output.lower()

    # Open non-existent workspace file
    res_open_err = runner.invoke(
        workspace_app, ["open", "--workspace", "/nonexistent/file.code-workspace"]
    )
    assert res_open_err.exit_code != 0

    # Clean with older-than
    res_clean = runner.invoke(workspace_app, ["clean", "--older-than", "5"])
    assert res_clean.exit_code == 0

    # Clean when no artifacts
    res_clean_empty = runner.invoke(workspace_app, ["clean"])
    assert res_clean_empty.exit_code == 0
    assert "clean" in res_clean_empty.output.lower()

    # Clean with pruned artifacts
    cache_dir = isolate_data_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    stale_file = cache_dir / "a.json"
    stale_file.write_text("old content", encoding="utf-8")
    os.utime(stale_file, (0, 0))

    res_clean_pruned = runner.invoke(workspace_app, ["clean"])
    assert res_clean_pruned.exit_code == 0
    assert "Cleaned" in res_clean_pruned.output


@pytest.mark.parametrize(
    ("content", "is_oversized"),
    [
        ('{\n // c\n "folders": [{"path": "/x"},],\n "settings": {"a": 1}\n}', False),
        ('{"folders": "x"}', False),
        ('{"folders": [{"path": "/x"}], "settings": {"a": 1}}', True),
        (b'{"folders": [{"path": "/\xff"}]}', False),
    ],
    ids=["jsonc", "malformed", "oversized", "not-utf8"],
)
@pytest.mark.parametrize("command", ["add", "remove"])
def test_workspace_add_refuses_to_overwrite_unparseable_file(
    tmp_path: Path,
    config: Callable[..., Path],
    command: str,
    content: str | bytes,
    is_oversized: bool,
) -> None:
    """A workspace file the command cannot read is left byte-for-byte as it was (#961).

    `_load` used to warn and return empty defaults, and `add` then saved over the file,
    dropping every folder and setting it held. VS Code accepts comments and trailing
    commas in a `.code-workspace` file, which `json.loads` rejects.
    """
    config(repos={"base_dir": str(tmp_path)})
    ws = tmp_path / "w.code-workspace"
    if is_oversized:
        with ws.open("wb") as f:
            f.seek(DEFAULT_MAX_AST_FILE_SIZE_BYTES + 10)
            f.write(b"x")
    elif isinstance(content, bytes):
        ws.write_bytes(content)
    else:
        ws.write_text(content, encoding="utf-8")
    before = ws.read_bytes()

    result = runner.invoke(workspace_app, [command, str(tmp_path), "--workspace", str(ws)])

    assert (result.exit_code, ws.read_bytes(), "left unchanged" in result.output) == (
        1,
        before,
        True,
    )


def test_workspace_load_save_boundaries_and_outside_roots(
    tmp_path: Path,
    config: Callable[..., Path],
) -> None:
    """Verify _load defaults and refusals, _save boundaries, and add outside roots."""
    from devops_cli.commands.workspace import _load, _save

    # 1. _load starts from empty defaults only when the file does not exist yet
    assert _load(tmp_path / "absent.code-workspace") == {"folders": [], "settings": {}}

    # 2. _load refuses corrupted JSON, a dict without a list of folders, and an oversized file
    bad_json = tmp_path / "corrupted.code-workspace"
    bad_json.write_text("NOT JSON", encoding="utf-8")
    mal_json = tmp_path / "malformed.code-workspace"
    mal_json.write_text('{"folders": "not_a_list"}', encoding="utf-8")
    good_json = tmp_path / "good.code-workspace"
    good_json.write_text('{"folders": []}', encoding="utf-8")
    for unreadable in (bad_json, mal_json):
        with pytest.raises(typer.Exit) as raised:
            _load(unreadable)
        assert raised.value.exit_code is not None

    oversized = tmp_path / "oversized.code-workspace"
    with oversized.open("wb") as f:
        f.seek(DEFAULT_MAX_AST_FILE_SIZE_BYTES + 10)
        f.write(b"x")
    with pytest.raises(typer.Exit) as raised:
        _load(oversized)
    assert raised.value.exit_code is not None

    # 4. _save unsafe filename extension
    with pytest.raises(typer.Exit) as raised:
        _save(tmp_path / "unsafe.txt", {"folders": []})
    assert raised.value.exit_code is not None

    # 5. Add folder outside permitted roots
    allowed_root = tmp_path / "isolated_root"
    allowed_root.mkdir(parents=True)
    outside_dir = tmp_path / "outside_root" / "my_project"
    outside_dir.mkdir(parents=True)
    config(
        repos={"base_dir": str(allowed_root)},
        workspace={"file": str(allowed_root / ".code-workspace")},
    )
    res_outside = runner.invoke(workspace_app, ["add", str(outside_dir)])
    assert res_outside.exit_code == 1
