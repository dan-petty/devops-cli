"""Tests for parallel implement job selection and conflict detection (#3064)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from devops_cli.roadmap.implement.implement_parallel import change_files, conflicts


def test_two_items_that_share_a_path_conflict() -> None:
    one_tasks = "# Tasks\n\n## 1. Group\n\nKind: behavior\nReads: none\nChanges: `src/devops_cli/a.py`\n\n- [ ] 1.1 Do it\n"
    two_tasks = "# Tasks\n\n## 1. Group\n\nKind: behavior\nReads: none\nChanges: `src/devops_cli/a.py`\n\n- [ ] 1.1 Do it\n"
    disjoint_tasks = "# Tasks\n\n## 1. Group\n\nKind: behavior\nReads: none\nChanges: `src/devops_cli/b.py`\n\n- [ ] 1.1 Do it\n"

    one = change_files(one_tasks)
    two = change_files(two_tasks)
    disjoint = change_files(disjoint_tasks)

    assert "src/devops_cli/a.py" in one
    assert conflicts(one, two) is True
    assert conflicts(one, disjoint) is False
    assert conflicts(frozenset(), one) is True
    assert conflicts(one, frozenset()) is True


def test_two_items_that_share_a_capability_spec_conflict(tmp_path: Path) -> None:
    change_a = tmp_path / "change-a"
    (change_a / "specs" / "my-cap").mkdir(parents=True)
    (change_a / "specs" / "my-cap" / "spec.md").write_text("spec a")

    change_b = tmp_path / "change-b"
    (change_b / "specs" / "my-cap").mkdir(parents=True)
    (change_b / "specs" / "my-cap" / "spec.md").write_text("spec b")

    change_c = tmp_path / "change-c"
    (change_c / "specs" / "other-cap").mkdir(parents=True)
    (change_c / "specs" / "other-cap" / "spec.md").write_text("spec c")

    tasks_a = "# Tasks\n\n## 1. Group\n\nKind: behavior\nReads: none\nChanges: `src/devops_cli/a.py`\n\n- [ ] 1.1 A\n"
    tasks_b = "# Tasks\n\n## 1. Group\n\nKind: behavior\nReads: none\nChanges: `src/devops_cli/b.py`\n\n- [ ] 1.1 B\n"
    tasks_c = "# Tasks\n\n## 1. Group\n\nKind: behavior\nReads: none\nChanges: `src/devops_cli/c.py`\n\n- [ ] 1.1 C\n"

    files_a = change_files(tasks_a, change_path=change_a)
    files_b = change_files(tasks_b, change_path=change_b)
    files_c = change_files(tasks_c, change_path=change_c)

    assert "openspec/specs/my-cap/spec.md" in files_a
    assert "openspec/specs/my-cap/spec.md" in files_b
    assert "openspec/specs/other-cap/spec.md" in files_c
    assert conflicts(files_a, files_b) is True
    assert conflicts(files_a, files_c) is False


def test_two_branches_of_disjoint_files_merge(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)

    git("init", "-b", "main")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.com")
    (repo / "base.txt").write_text("base")
    git("add", "base.txt")
    git("commit", "-m", "initial")

    git("checkout", "-b", "branch-a")
    (repo / "file_a.txt").write_text("a")
    git("add", "file_a.txt")
    git("commit", "-m", "commit a")

    git("checkout", "main")
    git("checkout", "-b", "branch-b")
    (repo / "file_b.txt").write_text("b")
    git("add", "file_b.txt")
    git("commit", "-m", "commit b")

    merge = git("merge", "branch-a", "-m", "merge a")
    assert merge.returncode == 0
    assert (repo / "file_a.txt").exists()
    assert (repo / "file_b.txt").exists()


def test_two_branches_touching_same_capability_spec_conflict(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=check)

    git("init", "-b", "main")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.com")
    spec_file = repo / "openspec" / "specs" / "cap" / "spec.md"
    spec_file.parent.mkdir(parents=True)
    spec_file.write_text("base spec\n")
    git("add", "openspec/specs/cap/spec.md")
    git("commit", "-m", "initial spec")

    git("checkout", "-b", "branch-a")
    spec_file.write_text("branch a content\n")
    git("add", "openspec/specs/cap/spec.md")
    git("commit", "-m", "branch a")

    git("checkout", "main")
    git("checkout", "-b", "branch-b")
    spec_file.write_text("branch b content\n")
    git("add", "openspec/specs/cap/spec.md")
    git("commit", "-m", "branch b")

    merge = git("merge", "branch-a", check=False)
    assert merge.returncode != 0  # git merge conflict

    # Verify conflict predicate catches it
    files_a = frozenset({"openspec/specs/cap/spec.md"})
    files_b = frozenset({"openspec/specs/cap/spec.md"})
    assert conflicts(files_a, files_b) is True


def test_change_files_edge_cases() -> None:
    assert change_files("") == frozenset()
    assert change_files("# Tasks\n\n## 1. Group\n\nNo changes line\n") == frozenset()

    config_tasks = (
        "# Tasks\n\n## 1. Group\n\nChanges: `src/devops_cli/config/defaults.py`\n\n- [ ] 1.1 A\n"
    )
    res_cfg = change_files(config_tasks)
    assert "docs/CONFIGURATION.md" in res_cfg
    assert "docs/ENV_VARS.md" in res_cfg

    cmd_tasks = (
        "# Tasks\n\n## 1. Group\n\nChanges: `src/devops_cli/commands/foo.py`\n\n- [ ] 1.1 A\n"
    )
    res_cmd = change_files(cmd_tasks)
    assert "docs/CLI_REFERENCE.md" in res_cmd

    path_tasks = (
        "# Tasks\n\n## 1. Group\n\n"
        "Changes: `openspec/changes/1-foo/specs/bar/spec.md`, `specs/baz/spec.md`\n\n- [ ] 1.1 A\n"
    )
    res_paths = change_files(path_tasks, files=["openspec/changes/2-qux/specs/quux/spec.md"])
    assert "openspec/specs/bar/spec.md" in res_paths
    assert "openspec/specs/baz/spec.md" in res_paths
    assert "openspec/specs/quux/spec.md" in res_paths
