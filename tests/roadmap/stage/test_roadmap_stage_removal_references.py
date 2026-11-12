"""`devops roadmap stage`: check test references to entities a plan removes (#3324), and read
which command or option an added requirement removes (#3287, #4954)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.roadmap.stage.stage import StagedChange, StageTarget, _stage_one
from devops_cli.roadmap.stage.stage_change import check_proposal
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_removal_references import (
    find_removed_names,
    scan_removal_references,
)
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import STAGE_REPO, StageRepo, seed_stageable

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

pytestmark = pytest.mark.usefixtures("keyring_store")

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
PULLS = f"/repos/{STAGE_REPO}/pulls"
OPENED = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    store.seed_file(
        ".github/labels.yml",
        '- name: "type/docs"\n  color: "0075ca"\n- name: "scope/openspec"\n  color: "0e8a16"\n',
    )
    return store


@pytest.fixture
def opened(github_api: GitHubApiFake) -> GitHubApiFake:
    github_api.route("POST", PULLS, OPENED)
    return github_api


def test_find_removed_names_extracts_governed_identifiers_and_skips_prepositions() -> None:
    proposal_text = "The planner removes `valkey_set` from `CONST_MCP_EXPOSURE_TABLE`."
    names = find_removed_names(proposal_text)
    assert names == {"valkey_set"}
    assert "CONST_MCP_EXPOSURE_TABLE" not in names


def test_find_removed_names_handles_multiple_identifiers_and_verbs() -> None:
    text = (
        "This change deletes `valkey_set` and `valkey_get` from `CONST_MCP_EXPOSURE_TABLE`.\n"
        "It also deprecates `legacy_func`.\n"
        "Another item drops `tool_a` from `registry`.\n"
        "`tool_b` is removed from `active_tools`.\n"
        "Finally, retires `old_entity`."
    )
    names = find_removed_names(text)
    assert names == {"valkey_set", "valkey_get", "legacy_func", "tool_a", "tool_b", "old_entity"}
    assert "CONST_MCP_EXPOSURE_TABLE" not in names
    assert "registry" not in names
    assert "active_tools" not in names


def test_find_removed_names_returns_empty_when_no_removal() -> None:
    text = "Adds a new feature with `valkey_set` in `CONST_MCP_EXPOSURE_TABLE`."
    names = find_removed_names(text)
    assert names == set()


def test_scan_reports_unhandled_test_reference(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "example_test.py").write_text(
        "def test_it():\n    client.call('valkey_set')\n",
        encoding="utf-8",
    )

    change_dir = tmp_path / "openspec" / "changes" / "3230-sample"
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text(
        "The change removes `valkey_set` from `CONST_MCP_EXPOSURE_TABLE`.\n",
        encoding="utf-8",
    )
    (change_dir / "design.md").write_text("Decisions:\n- None\n", encoding="utf-8")
    (change_dir / "tasks.md").write_text(
        "# Tasks\n- [ ] 1.1 Update other files\n",
        encoding="utf-8",
    )

    result = scan_removal_references(tmp_path, change_dir)
    assert result.unhandled_tests == {"valkey_set": ["tests/example_test.py"]}
    assert result.unhandled_sources == {}


def test_task_naming_file_accounts_for_reference(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "example_test.py").write_text(
        "def test_it():\n    client.call('valkey_set')\n",
        encoding="utf-8",
    )

    change_dir = tmp_path / "openspec" / "changes" / "3230-sample"
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text(
        "The change removes `valkey_set` from `CONST_MCP_EXPOSURE_TABLE`.\n",
        encoding="utf-8",
    )
    (change_dir / "design.md").write_text("Decisions:\n- None\n", encoding="utf-8")
    (change_dir / "tasks.md").write_text(
        "# Tasks\n- [ ] 1.1 Update `tests/example_test.py`\n",
        encoding="utf-8",
    )

    result = scan_removal_references(tmp_path, change_dir)
    assert result.unhandled_tests == {}
    assert result.unhandled_sources == {}


def test_source_reference_is_reported_as_warning_not_test_failure(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "example.py").write_text(
        "def setup():\n    register('valkey_set')\n",
        encoding="utf-8",
    )

    change_dir = tmp_path / "openspec" / "changes" / "3230-sample"
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text(
        "The change removes `valkey_set` from `CONST_MCP_EXPOSURE_TABLE`.\n",
        encoding="utf-8",
    )
    (change_dir / "design.md").write_text("Decisions:\n- None\n", encoding="utf-8")
    (change_dir / "tasks.md").write_text(
        "# Tasks\n- [ ] 1.1 Update other files\n",
        encoding="utf-8",
    )

    result = scan_removal_references(tmp_path, change_dir)
    assert result.unhandled_tests == {}
    assert result.unhandled_sources == {"valkey_set": ["src/example.py"]}


def test_change_with_no_removal_passes_scan(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "example_test.py").write_text("x = 1\n", encoding="utf-8")

    change_dir = tmp_path / "openspec" / "changes" / "3230-sample"
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text(
        "Adds a new capability.\n",
        encoding="utf-8",
    )
    (change_dir / "design.md").write_text("Decisions:\n- None\n", encoding="utf-8")
    (change_dir / "tasks.md").write_text(
        "# Tasks\n- [ ] 1.1 Do something\n",
        encoding="utf-8",
    )

    result = scan_removal_references(tmp_path, change_dir)
    assert result.unhandled_tests == {}
    assert result.unhandled_sources == {}


def test_stage_fails_on_unhandled_test_reference(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, opened: GitHubApiFake
) -> None:
    stage_repo.track({"tests/example_test.py": "def test_valkey():\n    call('valkey_set')\n"})
    sha = stage_repo.git("rev-parse", "HEAD")

    item = store.item(1)
    assert item is not None
    target = StageTarget(item, "fix", "1-the-job-drops-a-comment")
    change = StagedChange(
        target=target,
        title="docs(openspec): plan #1 Stop the job dropping a comment",
        body="Plans #1",
        files={
            f"openspec/changes/{target.change}/proposal.md": "The change removes `valkey_set` from `CONST_MCP_EXPOSURE_TABLE`.\n",
            f"openspec/changes/{target.change}/design.md": "Decisions:\n- none\n",
            f"openspec/changes/{target.change}/tasks.md": "# Tasks\n- [ ] 1.1 Update another file\n",
        },
        groups=(),
        validated=True,
        budget=1000,
        proposal=make_stage_proposal(),
    )

    with pytest.raises(RoadmapStageError) as exc_info:
        _stage_one(store, STAGE_REPO, stage_repo.clone, sha, change, (), NOW)

    assert "tests/example_test.py" in str(exc_info.value)
    assert "valkey_set" in str(exc_info.value)
    # Staging must open no draft pull request
    assert opened.requested == []


def test_stage_succeeds_and_comments_warning_on_unhandled_source_reference(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, opened: GitHubApiFake
) -> None:
    stage_repo.track({"src/example.py": "def register():\n    init('valkey_set')\n"})
    sha = stage_repo.git("rev-parse", "HEAD")

    item = store.item(1)
    assert item is not None
    target = StageTarget(item, "fix", "1-the-job-drops-a-comment")
    change = StagedChange(
        target=target,
        title="docs(openspec): plan #1 Stop the job dropping a comment",
        body="Plans #1",
        files={
            f"openspec/changes/{target.change}/proposal.md": "The change removes `valkey_set` from `CONST_MCP_EXPOSURE_TABLE`.\n",
            f"openspec/changes/{target.change}/design.md": "Decisions:\n- none\n",
            f"openspec/changes/{target.change}/tasks.md": "# Tasks\n- [ ] 1.1 Update another file\n",
        },
        groups=(),
        validated=True,
        budget=1000,
        proposal=make_stage_proposal(),
    )

    _stage_one(store, STAGE_REPO, stage_repo.clone, sha, change, (), NOW)

    # Pull request was opened
    assert len(opened.requested) == 1
    # Issue comment names src/example.py as a warning
    comments = [c.body for c in store.comments_on(1)]
    assert any("src/example.py" in c and "warning" in c.lower() for c in comments)


# ── The command or option that an added requirement removes (#3287, #4954) ────

KEPT_COMMAND = "devops pr check-readiness"
REMOVED_COMMAND = "devops roadmap intake-eval"
REMOVED_OPTION = "--old"
BASE_TEXTS = {
    "Readiness names a missing change folder": (
        f"The command `{KEPT_COMMAND}` SHALL name each missing change folder."
    ),
    "The intake-eval command runs each case": f"`{REMOVED_COMMAND}` SHALL run each case.",
    "The old option writes the plan": f"`devops roadmap stage {REMOVED_OPTION}` SHALL write it.",
}
TREE = StagedTree(["src/devops_cli/sample.py", "tests/test_sample.py"])


def _stale_command_problems(added: str) -> list[str]:
    """The problems of a plan that adds one requirement with the text `added` to the capability
    `comment-thread`, whose base requirements name each command and option of `BASE_TEXTS`."""
    scenario = {"name": "The case", "when": "the command runs", "then": "the case runs"}
    spec: dict[str, Any] = {
        "capability": "comment-thread",
        "added": [{"name": "The added rule", "text": added, "scenarios": [scenario]}],
        "modified": [],
    }
    plan = make_stage_proposal(specs=[spec])

    return check_proposal(
        plan,
        ["comment-thread"],
        TREE,
        registry=(),
        requirement_texts={"comment-thread": BASE_TEXTS},
    )


@pytest.mark.parametrize(
    "added",
    [
        pytest.param(
            f"The command `{KEPT_COMMAND}` SHALL read the changed files of a pull request from the "
            "compare endpoint of the base branch's tip and the head commit, and MUST NOT request "
            "the pulls files list for them.",
            id="2530-must-not-request",
        ),
        pytest.param(
            f"The command `{KEPT_COMMAND}` SHALL report a compare answer that holds GitHub's limit "
            "of 300 files as a possibly truncated list, naming the limit, and MUST NOT report a "
            "missing change folder as a blocker from that list.",
            id="2530-must-not-report",
        ),
        pytest.param(
            f"The command `{KEPT_COMMAND} --dry-run` SHALL list the compare request that reads the "
            "file list and MUST NOT list the pulls files request.",
            id="2530-must-not-list-a-request",
        ),
        pytest.param(
            f"`{KEPT_COMMAND}` SHALL NOT read the files of a closed pull request.",
            id="shall-not-read",
        ),
    ],
)
def test_a_requirement_that_forbids_one_act_of_a_command_removes_nothing(added: str) -> None:
    assert _stale_command_problems(added) == []


@pytest.mark.parametrize(
    ("added", "removed"),
    [
        pytest.param(
            f"The `{REMOVED_COMMAND}` command MUST NOT exist.", REMOVED_COMMAND, id="subject"
        ),
        pytest.param(f"`{REMOVED_COMMAND}` SHALL NOT exist.", REMOVED_COMMAND, id="bare-subject"),
        pytest.param(
            f"The command `{REMOVED_COMMAND}` MUST NOT be available.",
            REMOVED_COMMAND,
            id="be-available",
        ),
        pytest.param(
            f"The commands `devops roadmap intake-old` and `{REMOVED_COMMAND}` MUST NOT exist.",
            REMOVED_COMMAND,
            id="subject-list",
        ),
        pytest.param(
            f"The command `{KEPT_COMMAND}` SHALL stay, and `{REMOVED_COMMAND}` MUST NOT exist.",
            REMOVED_COMMAND,
            id="second-clause",
        ),
        pytest.param(
            f"The CLI SHALL keep `{KEPT_COMMAND}` (the `{REMOVED_COMMAND}` command MUST NOT exist).",
            REMOVED_COMMAND,
            id="in-parentheses",
        ),
        pytest.param(
            "The CLI SHALL run the intake duplicate evaluation as `devops roadmap eval intake`, "
            f"and MUST NOT register `{REMOVED_COMMAND}` as a command or as an alias.",
            REMOVED_COMMAND,
            id="3185-must-not-register",
        ),
        pytest.param(
            "The command matrix and the CLI reference SHALL list `devops roadmap eval intake` and "
            f"MUST NOT list `{REMOVED_COMMAND}`.",
            REMOVED_COMMAND,
            id="3185-must-not-list",
        ),
        pytest.param(
            f"The `{REMOVED_OPTION}` option of `{KEPT_COMMAND}` MUST NOT exist.",
            REMOVED_OPTION,
            id="option-of-a-command",
        ),
        pytest.param(
            f"`{KEPT_COMMAND}` MUST NOT accept `{REMOVED_OPTION}`.",
            REMOVED_OPTION,
            id="must-not-accept",
        ),
    ],
)
def test_an_added_requirement_removes_the_name_that_must_not_governs(
    added: str, removed: str
) -> None:
    problems = _stale_command_problems(added)

    assert len(problems) == 1
    assert f"`{removed}`" in problems[0]
