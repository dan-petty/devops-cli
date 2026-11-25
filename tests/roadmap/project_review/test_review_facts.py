"""The git and lizard facts of a project review window (#4686): the commits and their types, the
net change and the churn with the generated files apart, the releases, the hot files with their
renames followed, and the complexity of the hot files at the base and at the head."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest
import yaml
from pydantic import ValidationError

from devops_cli.exceptions.roadmap import RoadmapReviewError
from devops_cli.roadmap.project_review.catalog import load_catalog
from devops_cli.roadmap.project_review.data import (
    Disagreement,
    Fact,
    FactStatus,
    ReviewData,
    ReviewWindow,
    WindowKind,
    write_review,
)
from devops_cli.roadmap.project_review.facts import (
    Hotspot,
    complexity_fact,
    hotspots,
    review_facts,
)
from devops_cli.roadmap.project_review.git_read import Commit, FileChange, commits, numstat
from devops_cli.roadmap.project_review.review import planned_review, render_review, run_review
from devops_cli.roadmap.project_review.window import parse_window, read_tags, resolve_window
from tests.support.fakes.git import GitFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.process import ProcessAnswer

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
            section="changes",
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


def test_the_facts_of_a_catalog_follow_the_git_facts_with_their_section(
    checkout: Path, tmp_path: Path, web: WebFake, config: Callable[..., Path]
) -> None:
    """data.json holds the git facts in the section `changes`, then each fact of the catalog in
    its section, and the reads of each reader kind (#4692)."""
    config(prometheus={"url": "http://prometheus.example.com:9090"})
    web.serve(
        lambda request: httpx2.Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "vector", "result": [{"metric": {}, "value": [1, "4"]}]},
            },
        )
    )
    fact = {
        "reader": "prometheus",
        "section": "service",
        "shape": "scalar",
        "unit": "count",
        "definition": "A value.",
    }
    path = tmp_path / "catalog.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "sections": [{"id": "service", "title": "Service"}],
                "readers": {"prometheus": {"requires": ["setting:prometheus.url"]}},
                "facts": [
                    {**fact, "id": "prometheus.one", "query": "sum(one)"},
                    {**fact, "id": "prometheus.two", "query": "sum(two)"},
                ],
                "disagreements": [],
            }
        ),
        encoding="utf-8",
    )

    data = run_review(
        checkout,
        "example/project",
        parse_window(version="v1.0.0..v1.1.1", now=NOW),
        catalog=load_catalog(path),
        now=NOW,
    )

    assert [(fact.id, fact.section) for fact in data.facts][-4:] == [
        ("lizard.complexity", "changes"),
        ("functional.change", "changes"),
        ("prometheus.one", "service"),
        ("prometheus.two", "service"),
    ]
    assert {fact.section for fact in data.facts[:-2]} == {"changes"}
    assert data.collection.reads == {"prometheus": 2}


def test_the_summary_shows_each_fact_that_is_not_ok_and_each_disagreement(tmp_path: Path) -> None:
    window = ReviewWindow(
        kind=WindowKind.WEEK,
        id="2026-W45",
        base_sha="a" * 40,
        head_sha="b" * 40,
        start=datetime(2026, 11, 2, tzinfo=UTC),
        end=datetime(2026, 11, 9, tzinfo=UTC),
        previous_id="2026-W44",
    )
    expired = Fact(
        id="prometheus.up",
        section="service",
        value=None,
        unit="count",
        n=None,
        source="prometheus",
        query="sum(up)",
        definition="d",
        read_at=NOW,
        status=FactStatus.EXPIRED,
        reason="The source keeps 30 days.",
    )
    pair = Disagreement(
        id="spend",
        left="prometheus.cli_spend",
        right="prometheus.gateway_spend",
        left_value=77.22,
        right_value=118.74,
        difference=0.3497,
        tolerance=0.1,
        definition="d",
    )
    data = ReviewData(repo="example/project", window=window, facts=[expired], disagreements=[pair])

    text = render_review(data, tmp_path / "data.json")

    assert "  prometheus.up: expired: The source keeps 30 days." in text
    assert (
        "Disagreement spend: prometheus.cli_spend 77.22 and prometheus.gateway_spend 118.74 "
        "differ by 35%, more than 10%."
    ) in text


def test_the_run_reads_the_tag_pattern_of_the_roadmap_file(
    checkout: Path, git_fake: GitFake, tmp_path: Path
) -> None:
    """`[review] tag_pattern` flows to `review_facts`, `planned_review`, and `run_review` (#4730)."""
    tags = read_tags(checkout)
    window = resolve_window(checkout, parse_window(version="v1.0.0..v1.1.1", now=NOW), tags)
    custom_facts = {
        fact.id: fact for fact in review_facts(checkout, window, tags, tag_pattern="release-*")
    }
    assert "refs/tags/release-*" in custom_facts["git.releases"].query

    custom_checkout = tmp_path / "custom"
    (custom_checkout / ".devops").mkdir(parents=True)
    (custom_checkout / ".devops" / "roadmap.toml").write_text(
        '[review]\ntag_pattern = "release-*"\n', encoding="utf-8"
    )
    calls_before = len(git_fake.calls)
    plan = planned_review(
        custom_checkout, parse_window(version="release-1.0..release-1.1", now=NOW)
    )
    assert len(git_fake.calls) == calls_before
    assert any("refs/tags/release-*" in " ".join(req.argv) for req in plan)

    git_fake.answer(lambda call: "refs/tags/release-*" in call.argv, ProcessAnswer(stdout=""))
    with pytest.raises(RoadmapReviewError, match=r"tag_pattern.*'release-\*'"):
        run_review(
            custom_checkout,
            "example/project",
            parse_window(version="release-1.0..release-1.1", now=NOW),
            now=NOW,
        )


def test_run_review_omits_functional_change_when_an_openspec_fact_is_ok(
    checkout: Path, tmp_path: Path, git_fake: GitFake
) -> None:
    """When any `openspec.*` catalog fact has status `ok`, `functional.change` is omitted (#4730)."""
    path = tmp_path / "catalog.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "sections": [{"id": "openspec", "title": "OpenSpec"}],
                "readers": {"openspec": {"requires": ["path:openspec/specs"]}},
                "facts": [
                    {
                        "id": "openspec.requirements",
                        "reader": "openspec",
                        "section": "openspec",
                        "query": "openspec show --json --deltas-only",
                        "value": ".requirements",
                        "unit": "requirements",
                        "definition": "Total requirements.",
                    }
                ],
                "disagreements": [],
            }
        ),
        encoding="utf-8",
    )
    git_fake.answer(lambda call: "ls-tree" in call.argv, ProcessAnswer(stdout="openspec/specs\n"))
    git_fake.answer(lambda call: "--diff-filter=A" in call.argv, ProcessAnswer(stdout=""))
    git_fake.answer(
        lambda call: "grep" in call.argv and "-c" in call.argv,
        ProcessAnswer(stdout="openspec/specs/a/spec.md:2\n"),
    )

    data = run_review(
        checkout,
        "example/project",
        parse_window(version="v1.0.0..v1.1.1", now=NOW),
        catalog=load_catalog(path),
        now=NOW,
    )

    assert [fact.id for fact in data.facts] == [
        "git.commits",
        "git.commit_types",
        "git.net_change",
        "git.churn",
        "git.releases",
        "git.release_tags",
        "git.hotspots",
        "lizard.complexity",
        "openspec.requirements",
    ]


def test_a_shell_only_window_keeps_the_churn_rank_and_skips_the_complexity_rank(
    tmp_path: Path,
) -> None:
    """When hot files exist and lizard reads none of them, `lizard.complexity` is `skipped` (#4730)."""
    window = ReviewWindow(
        kind=WindowKind.PERIOD,
        id="w",
        base_sha="a" * 40,
        head_sha="b" * 40,
        start=datetime(2026, 11, 2, tzinfo=UTC),
        end=datetime(2026, 11, 9, tzinfo=UTC),
        previous_id=None,
    )
    shell_rows = [Hotspot("scripts/deploy.sh", commits=3, added=10, deleted=2)]
    skipped = complexity_fact(tmp_path, window, shell_rows)

    assert (skipped.value, skipped.n, skipped.status) == (None, None, FactStatus.SKIPPED)
    assert "lizard" in skipped.reason

    empty = complexity_fact(tmp_path, window, [])
    assert (empty.value, empty.n, empty.status) == ([], 0, FactStatus.OK)

    hotspot_fact = Fact(
        id="git.hotspots",
        section="changes",
        value=[row.row() for row in shell_rows],
        unit="commits",
        n=1,
        source="git",
        query="git log",
        definition="d",
        read_at=NOW,
        status=FactStatus.OK,
    )
    rendered = render_review(
        ReviewData(repo="example/project", window=window, facts=[hotspot_fact, skipped]),
        tmp_path / "data.json",
    )
    assert "git.hotspots:" in rendered
    assert f"lizard.complexity: skipped: {skipped.reason}" in rendered
