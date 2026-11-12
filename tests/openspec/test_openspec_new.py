"""Acceptance tests for `devops openspec new` (#3203)."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import (
    CONST_OPENSPEC_SCAFFOLD_MARKER,
    CONST_OPENSPEC_SPECS_DIR,
)
from devops_cli.openspec.gate import GateCheck, check_openspec
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.openspec import OpenSpecFake
from tests.support.paths import REPO_ROOT

Cli = Callable[..., Any]
TITLE = "feat(openspec): scaffold the change folder"
CHANGE_NAME = "3203-scaffold-the-change-folder"
BRANCH = "feat/3203-scaffold-the-change-folder"


def _clean_tree(openspec_fake: OpenSpecFake) -> Path:
    """Build a clean checkout from the empty scenario."""
    return openspec_fake.tree("empty")


def test_new_creates_the_four_files_with_title(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: The command creates the change folder."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)

    result = cli("openspec", "new", "3203", "--title", TITLE)

    assert result.exit_code == 0, result.output
    change_folder = tree / "openspec/changes" / CHANGE_NAME
    assert change_folder.is_dir()
    for filename in (".openspec.yaml", "proposal.md", "design.md", "tasks.md"):
        assert (change_folder / filename).is_file()


def test_new_reads_issue_title_from_github_when_title_absent(
    cli: Cli,
    openspec_fake: OpenSpecFake,
    github_api: GitHubApiFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requirement: The command reads the issue title."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)
    github_api.route(
        "GET",
        "/repos/unknown/repo/issues/3203",
        github_json({"number": 3203, "title": TITLE, "body": "", "state": "open"}),
    )

    result = cli("openspec", "new", "3203")

    assert result.exit_code == 0, result.output
    change_folder = tree / "openspec/changes" / CHANGE_NAME
    assert change_folder.is_dir()
    assert BRANCH in result.output


def test_proposal_holds_six_headings_and_cites_issue(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: The proposal holds the project sections."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)

    result = cli("openspec", "new", "3203", "--title", TITLE)
    assert result.exit_code == 0, result.output

    proposal = (tree / "openspec/changes" / CHANGE_NAME / "proposal.md").read_text(encoding="utf-8")
    headings = [
        "## Why",
        "## What Changes",
        "## Capabilities",
        "## Impact",
        "## Feasibility",
        "## Existing Tool Considered",
    ]
    last_pos = -1
    for heading in headings:
        pos = proposal.find(heading)
        assert pos != -1, f"Missing {heading}"
        assert pos > last_pos, f"{heading} out of order"
        last_pos = pos

    why_section = proposal[proposal.find("## Why") : proposal.find("## What Changes")]
    assert "#3203" in why_section


def test_design_holds_decisions_and_rejected_alternatives_with_marker(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: The design file holds decisions and rejected alternatives."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)

    result = cli("openspec", "new", "3203", "--title", TITLE)
    assert result.exit_code == 0, result.output

    design = (tree / "openspec/changes" / CHANGE_NAME / "design.md").read_text(encoding="utf-8")
    assert "## Decisions" in design
    assert "## Rejected alternatives" in design
    for section in (
        design[design.find("## Decisions") : design.find("## Rejected alternatives")],
        design[design.find("## Rejected alternatives") :],
    ):
        lines = [
            line.strip()
            for line in section.splitlines()
            if line.strip() and not line.startswith("#")
        ]
        assert lines, "Section is empty"
        assert all(line.endswith(CONST_OPENSPEC_SCAFFOLD_MARKER) for line in lines)


def test_tasks_holds_behavior_and_documents_groups(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: The tasks file holds a behavior group and a documents group."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)

    result = cli("openspec", "new", "3203", "--title", TITLE)
    assert result.exit_code == 0, result.output

    tasks = (tree / "openspec/changes" / CHANGE_NAME / "tasks.md").read_text(encoding="utf-8")
    assert "## 1. Behavior" in tasks
    assert "## 2. Documents" in tasks
    assert "uv run devops ci docs" in tasks
    assert "uv run devops ci test" in tasks

    pos_behavior = tasks.find("## 1. Behavior")
    pos_documents = tasks.find("## 2. Documents")
    assert pos_behavior < pos_documents

    behavior_section = tasks[pos_behavior:pos_documents]
    pos_test = behavior_section.find("Write failing test")
    pos_impl = behavior_section.find("Implement the behavior")
    assert pos_test != -1
    assert pos_impl != -1
    assert pos_test < pos_impl


def test_folder_and_branch_share_one_slug(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: The folder and the branch share one slug."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)

    result = cli("openspec", "new", "3203", "--title", TITLE)
    assert result.exit_code == 0, result.output

    assert CHANGE_NAME in result.output
    assert BRANCH in result.output


def test_existing_folder_stops_the_command(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: An existing folder stops the command."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)

    result1 = cli("openspec", "new", "3203", "--title", TITLE)
    assert result1.exit_code == 0

    result2 = cli("openspec", "new", "3203", "--title", TITLE)
    assert result2.exit_code == 1
    assert CHANGE_NAME in result2.output


def test_two_runs_write_the_same_bytes(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Two runs write the same bytes."""
    tree1 = openspec_fake.trees / "run1"
    tree1.mkdir()
    tree2 = openspec_fake.trees / "run2"
    tree2.mkdir()

    from tests.support.openspec_scenarios import build_scenario

    build_scenario("empty", tree1, openspec_fake.committed_skills)
    build_scenario("empty", tree2, openspec_fake.committed_skills)

    monkeypatch.chdir(tree1)
    res1 = cli("openspec", "new", "3203", "--title", TITLE)
    assert res1.exit_code == 0

    monkeypatch.chdir(tree2)
    res2 = cli("openspec", "new", "3203", "--title", TITLE)
    assert res2.exit_code == 0

    folder1 = tree1 / "openspec/changes" / CHANGE_NAME
    folder2 = tree2 / "openspec/changes" / CHANGE_NAME

    for filename in ("proposal.md", "design.md", "tasks.md"):
        assert (folder1 / filename).read_bytes() == (folder2 / filename).read_bytes()

    yaml1 = re.sub(r"created:.*\n", "", (folder1 / ".openspec.yaml").read_text(encoding="utf-8"))
    yaml2 = re.sub(r"created:.*\n", "", (folder2 / ".openspec.yaml").read_text(encoding="utf-8"))
    assert yaml1 == yaml2


def test_gate_refuses_scaffold_marker(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: The gate refuses the scaffold marker."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)

    result = cli("openspec", "new", "3203", "--title", TITLE)
    assert result.exit_code == 0

    findings = check_openspec(tree)
    scaffold_findings = [f for f in findings if f.check == GateCheck.SCAFFOLD]
    assert scaffold_findings
    assert any("proposal.md" in f.detail for f in scaffold_findings)


def test_delta_chooses_modified_or_added_from_base_spec(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: The delta chooses ADDED or MODIFIED from the base spec."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)

    # Copy the nested roadmap-refine/selection base spec into the fake tree
    base_spec_dir = tree / CONST_OPENSPEC_SPECS_DIR / "roadmap-refine/selection"
    base_spec_dir.mkdir(parents=True, exist_ok=True)
    real_spec = REPO_ROOT / CONST_OPENSPEC_SPECS_DIR / "roadmap-refine/selection/spec.md"
    (base_spec_dir / "spec.md").write_text(real_spec.read_text(encoding="utf-8"), encoding="utf-8")

    result = cli(
        "openspec",
        "new",
        "3203",
        "--title",
        TITLE,
        "--capability",
        "roadmap-refine/selection:Only the limit stops a refine round",
    )
    assert result.exit_code == 0, result.output

    delta = (
        tree / "openspec/changes" / CHANGE_NAME / "specs/roadmap-refine/selection/spec.md"
    ).read_text(encoding="utf-8")
    assert "## MODIFIED Requirements" in delta
    assert "Only the limit stops a refine round" in delta
    assert "Scenario: A backlog full of Ready items" in delta


def test_new_capability_gets_purpose_and_added(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: A new capability gets a Purpose."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)

    result = cli(
        "openspec",
        "new",
        "3203",
        "--title",
        TITLE,
        "--capability",
        "openspec-scaffold:Command creates the change folder",
    )
    assert result.exit_code == 0, result.output

    delta = (tree / "openspec/changes" / CHANGE_NAME / "specs/openspec-scaffold/spec.md").read_text(
        encoding="utf-8"
    )
    assert "## Purpose" in delta
    purpose_line = delta[delta.find("## Purpose") : delta.find("## ADDED Requirements")].strip()
    assert len(purpose_line) >= 50
    assert "## ADDED Requirements" in delta
    assert "Command creates the change folder" in delta


def test_skip_specs_follows_paths(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: skip_specs follows the named paths."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)

    # 1. Non-observable paths -> skip_specs: true
    result_non_obs = cli(
        "openspec",
        "new",
        "3203",
        "--title",
        TITLE,
        "--paths",
        "tests/test_openspec_new.py",
        "--paths",
        "docs/openspec.md",
    )
    assert result_non_obs.exit_code == 0
    yaml_content = (tree / "openspec/changes" / CHANGE_NAME / ".openspec.yaml").read_text(
        encoding="utf-8"
    )
    assert "skip_specs: true" in yaml_content


def test_skip_specs_false_when_observable_paths(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: skip_specs is false when observable paths given."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)

    result_obs = cli(
        "openspec",
        "new",
        "3204",
        "--title",
        "feat: add new feature",
        "--paths",
        "src/devops_cli/foo.py",
    )
    assert result_obs.exit_code == 0
    yaml_content = (tree / "openspec/changes/3204-add-new-feature/.openspec.yaml").read_text(
        encoding="utf-8"
    )
    assert "skip_specs: false" in yaml_content


def test_dry_run_makes_no_request_and_writes_nothing(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: A dry run makes no request."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)

    result = cli("openspec", "new", "3203", "--title", TITLE, "--dry-run")
    assert result.exit_code == 0, result.output
    assert not (tree / "openspec/changes" / CHANGE_NAME).exists()
    assert CHANGE_NAME in result.output
    assert BRANCH in result.output


def test_dry_run_requires_title(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: A dry run without title is refused."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)

    result = cli("openspec", "new", "3203", "--dry-run")
    assert result.exit_code == 1
    assert "--title" in result.output


def test_output_names_next_steps(
    cli: Cli, openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: The command prints the next steps."""
    tree = _clean_tree(openspec_fake)
    monkeypatch.chdir(tree)

    result = cli("openspec", "new", "3203", "--title", TITLE)
    assert result.exit_code == 0
    assert BRANCH in result.output
    assert "uv run devops ci" in result.output
    assert f"uv run devops openspec archive {CHANGE_NAME}" in result.output


def test_skill_points_to_command() -> None:
    """Requirement: The skill points to the command."""
    claude_skill = (REPO_ROOT / ".claude/skills/devops-openspec-new/SKILL.md").read_text(
        encoding="utf-8"
    )
    agents_skill = (REPO_ROOT / ".agents/skills/devops-openspec-new/SKILL.md").read_text(
        encoding="utf-8"
    )

    for skill_text in (claude_skill, agents_skill):
        assert "devops openspec new" in skill_text
        assert "openspec new change" not in skill_text
