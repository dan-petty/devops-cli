"""The git and lizard facts of a project review window (#4686): the commits and their types, the
net change and the churn with the generated files apart, the releases, the hot files with their
renames followed, and the complexity of the hot files at the base and at the head."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.roadmap.project_review.data import (
    Fact,
    FactStatus,
    ReviewData,
    ReviewWindow,
    WindowKind,
    write_review,
)
from devops_cli.roadmap.project_review.facts import Hotspot, hotspots, review_facts
from devops_cli.roadmap.project_review.git_read import Commit, FileChange, commits, numstat
from devops_cli.roadmap.project_review.window import parse_window, read_tags, resolve_window
from tests.support.fakes.git import GitFake

NOW = datetime(2026, 10, 6, tzinfo=UTC)
OK = FactStatus.OK


@pytest.fixture
def checkout(git_fake: GitFake, tmp_path: Path) -> Path:
    """The repository of the scenario `review_window`, as git answered for it."""
    git_fake.replay("review_window")
    return tmp_path / "project"


def _facts(checkout: Path, version: str) -> dict[str, Fact]:
    tags = read_tags(checkout)
    window = resolve_window(checkout, parse_window(version=version, now=NOW), tags)
    return {fact.id: fact for fact in review_facts(checkout, window, tags)}


def test_the_facts_of_a_version_window(checkout: Path) -> None:
    facts = _facts(checkout, "v1.0.0..v1.1.1")

    assert {key: (f.value, f.unit, f.n, f.source, f.status) for key, f in facts.items()} == {
        "git.commits": (4, "commits", 4, "git", OK),
        "git.commit_types": (
            {"feat": 1, "fix": 1, "refactor": 1, "other": 1},
            "commits",
            4,
            "git",
            OK,
        ),
        "git.net_change": (
            {
                "all": {"files": 4, "added": 10, "deleted": 2},
                "generated": {"files": 1, "added": 1, "deleted": 1},
            },
            "lines",
            4,
            "git",
            OK,
        ),
        "git.churn": (
            {
                "all": {"files": 4, "added": 12, "deleted": 4},
                "generated": {"files": 1, "added": 1, "deleted": 1},
            },
            "lines",
            4,
            "git",
            OK,
        ),
        "git.releases": ({"minor": 1, "patch": 1}, "tags", 2, "git", OK),
        "git.release_tags": (
            [
                {"tag": "v1.1.0", "created": "2026-10-03T10:00:00+00:00"},
                {"tag": "v1.1.1", "created": "2026-10-05T06:30:00+00:00"},
            ],
            "tags",
            2,
            "git",
            OK,
        ),
        "git.hotspots": (
            [
                {"path": "a.py", "commits": 2, "added": 4, "deleted": 2, "renamed_from": []},
                {
                    "path": "pkg/new_name.py",
                    "commits": 2,
                    "added": 5,
                    "deleted": 1,
                    "renamed_from": ["old_name.py"],
                },
                {"path": "side.py", "commits": 1, "added": 2, "deleted": 0, "renamed_from": []},
            ],
            "commits",
            3,
            "git",
            OK,
        ),
        "lizard.complexity": (
            [
                {
                    "path": "a.py",
                    "base": {"functions": 1, "ccn_max": 1, "ccn_sum": 1},
                    "head": {"functions": 1, "ccn_max": 2, "ccn_sum": 2},
                },
                {
                    "path": "pkg/new_name.py",
                    "base": {"functions": 6, "ccn_max": 2, "ccn_sum": 12},
                    "head": {"functions": 7, "ccn_max": 2, "ccn_sum": 14},
                },
                {
                    "path": "side.py",
                    "base": None,
                    "head": {"functions": 1, "ccn_max": 1, "ccn_sum": 1},
                },
            ],
            "ccn",
            3,
            "lizard",
            OK,
        ),
    }
    assert facts["git.commits"].query.startswith("git log --first-parent -M --numstat -z ")


def test_a_review_with_no_lizard_skips_the_complexity_and_says_why(
    checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "lizard", None)

    fact = _facts(checkout, "v1.0.0..v1.1.1")["lizard.complexity"]

    assert (fact.value, fact.n, fact.status) == (None, None, FactStatus.SKIPPED)
    assert "install the extra review" in fact.reason


def test_a_commit_at_an_old_name_counts_for_the_path_at_the_head() -> None:
    at = datetime(2026, 10, 1, tzinfo=UTC)
    found = [
        Commit("c3", at, "fix: c", (FileChange("c.py", 1, 0),)),
        Commit("c2", at, "refactor: b to c", (FileChange("c.py", 0, 0, old_path="b.py"),)),
        Commit("c1", at, "refactor: a to b", (FileChange("b.py", 2, 1, old_path="a.py"),)),
        Commit("c0", at, "feat: a", (FileChange("a.py", 5, 0), FileChange("z.py", 1, 0))),
    ]

    assert hotspots(found) == [
        Hotspot("c.py", commits=4, added=8, deleted=1, renamed_from=["b.py", "a.py"]),
        Hotspot("z.py", commits=1, added=1, deleted=0),
    ]


def test_numstat_reads_renames_binary_files_and_paths_with_spaces() -> None:
    text = (
        "\x1ec1\x1f1790000000\x1ffeat: x\x00\n3\t1\tsp ace.py\x00-\t-\tlogo.png\x00"
        "2\t0\t\x00a.py\x00b.py\x00"
    )

    assert commits(text) == [
        Commit(
            "c1",
            datetime.fromtimestamp(1790000000, UTC),
            "feat: x",
            (
                FileChange("sp ace.py", 3, 1),
                FileChange("logo.png", 0, 0),
                FileChange("b.py", 2, 0, old_path="a.py"),
            ),
        )
    ]
    assert numstat("") == ()


def test_a_fact_that_is_not_ok_must_say_why() -> None:
    with pytest.raises(ValidationError, match="must give a reason"):
        Fact(
            id="git.commits",
            value=None,
            unit="commits",
            n=None,
            source="git",
            query="git log",
            definition="d",
            read_at=NOW,
            status=FactStatus.ERROR,
        )


def test_the_data_is_written_with_its_json_schema(tmp_path: Path) -> None:
    window = ReviewWindow(
        kind=WindowKind.WEEK,
        id="2026-W40",
        base_sha="a" * 40,
        head_sha="b" * 40,
        start=datetime(2026, 9, 28, tzinfo=UTC),
        end=datetime(2026, 10, 5, tzinfo=UTC),
        previous_id="2026-W39",
    )
    data = ReviewData(repo="example/project", window=window, facts=[])

    written = write_review(data, tmp_path / "out")

    assert ReviewData.model_validate_json(written.read_text(encoding="utf-8")) == data
    schema = json.loads((tmp_path / "out" / "data.schema.json").read_text(encoding="utf-8"))
    assert schema["$defs"]["FactStatus"]["enum"] == ["ok", "expired", "skipped", "error"]
