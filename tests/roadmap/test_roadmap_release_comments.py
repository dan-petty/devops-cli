"""The row `release_comments`: the Service comments the version on each closed issue that a release
carries, and the time the images of the release run in the cluster (#2917).

GitHub is faked at the `gh` process edge (`GitHubFake`), the registry at the HTTP edge
(`RegistryFake`). The cluster is read by a function that each test gives the digests it holds.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx2
import pytest

from devops_cli.exceptions import RoadmapRunError
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client
from devops_cli.roadmap.release_comments import comment_releases
from devops_cli.roadmap.release_feed import GitHubReleaseFeed
from devops_cli.roadmap.release_roll import RolledDigests
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from tests.roadmap_github_fake import GitHubFake
from tests.support.fakes.github import RunnerSession
from tests.support.fakes.http import WebFake
from tests.support.fakes.oci_registry import RegistryFake

REPO = "example/roadmap"
NOW = datetime(2026, 11, 2, 12, 0, 30, tzinfo=UTC)
PREFIX = "ghcr.io/dan-petty/devops-cli"
DIGESTS = {
    f"{PREFIX}/{image}:{tag}": f"sha256:{index}{number}" + "0" * 62
    for index, tag in enumerate(("v1.0.0", "v1.1.0"), 1)
    for number, image in enumerate(("service", "runner"), 1)
}


def _changelog(*pulls: int) -> str:
    return "## changelog\n\n" + "".join(
        f"* **a:** x ([#{pull}](https://example.com/issues/{pull})) ([abc](https://e.com/c))\n"
        for pull in pulls
    )


def _rolled(tag: str) -> RolledDigests:
    return RolledDigests(
        service=DIGESTS[f"{PREFIX}/service:{tag}"], runner=DIGESTS[f"{PREFIX}/runner:{tag}"]
    )


@pytest.fixture
def github() -> GitHubFake:
    """Release `v1.0.0` of 2.5 hours ago, with two pull requests that close issues 101 and 102."""
    fake = GitHubFake(REPO)
    fake.seed_issue(11, "pull", state="closed", body="Closes #101", pull_request=True)
    fake.seed_issue(12, "pull", state="closed", body="Fixes #102", pull_request=True)
    fake.seed_issue(101, "one", state="closed")
    fake.seed_issue(102, "two", state="closed")
    fake.seed_release("v1.0.0", _changelog(11, 12), NOW - timedelta(hours=2, minutes=30))
    return fake


@pytest.fixture
def ledger(tmp_path: Path) -> Path:
    return tmp_path / "release_comments.json"


def _round(
    github: GitHubFake,
    ledger: Path,
    *,
    now: datetime = NOW,
    roll: Callable[[], RolledDigests] | None = None,
    client: httpx2.Client | None = None,
) -> None:
    store = GitHubRoadmapStore(REPO, runner=github, session=RunnerSession(github))
    comment_releases(
        store,
        GitHubReleaseFeed(REPO, runner=github),
        ledger_path=ledger,
        now=now,
        roll=roll,
        client=client,
    )


def test_a_release_comments_its_version_once_on_each_closed_issue(
    github: GitHubFake, ledger: Path
) -> None:
    _round(github, ledger)

    for number in (101, 102):
        assert len(github.comments[number]) == 1
        first, second = github.comments[number][0].split("\n")[:2]
        assert first == "<!-- devops roadmap release v1.0.0 released -->"
        assert second.startswith("Released in v1.0.0")


def test_a_second_round_posts_nothing_and_reads_only_the_list(
    github: GitHubFake, ledger: Path
) -> None:
    _round(github, ledger)
    github.calls.clear()

    _round(github, ledger)

    assert github.writes() == []
    assert github.calls == [["api", "repos/example/roadmap/releases?per_page=30"]]


def test_a_changelog_with_no_closing_text_finds_the_issue_through_the_pull_request(
    github: GitHubFake, ledger: Path
) -> None:
    github.releases.clear()
    github.seed_release("v1.0.0", _changelog(11), NOW - timedelta(hours=1))

    _round(github, ledger)

    assert len(github.comments[101]) == 1


def test_an_open_issue_and_a_pull_request_get_nothing(github: GitHubFake, ledger: Path) -> None:
    github.seed_issue(
        11, "pull", state="closed", body="Closes #103\nCloses #104", pull_request=True
    )
    github.seed_issue(103, "open")
    github.seed_issue(104, "another pull", state="closed", pull_request=True)

    _round(github, ledger)

    assert 103 not in github.comments
    assert 104 not in github.comments


def test_a_lost_ledger_is_rebuilt_from_the_comments(github: GitHubFake, ledger: Path) -> None:
    _round(github, ledger)
    ledger.unlink()
    posted = len(github.writes())

    _round(github, ledger)

    assert len(github.writes()) == posted
    assert json.loads(ledger.read_text("utf-8"))["releases"]["v1.0.0"]["released"] is True


def test_a_ledger_that_holds_both_flags_as_done_sends_only_the_list_request(
    github: GitHubFake, ledger: Path
) -> None:
    ledger.write_text(
        json.dumps({"releases": {"v1.0.0": {"released": True, "live": True}}}), encoding="utf-8"
    )

    _round(github, ledger)

    assert github.calls == [["api", "repos/example/roadmap/releases?per_page=30"]]


def test_a_ledger_that_is_not_json_fails_the_row_and_names_the_file(
    github: GitHubFake, ledger: Path
) -> None:
    ledger.write_text("not json", encoding="utf-8")

    with pytest.raises(RoadmapRunError, match=ledger.name):
        _round(github, ledger)

    assert github.writes() == []


def test_an_old_release_a_draft_and_a_prerelease_cause_no_read_and_no_comment(
    github: GitHubFake, ledger: Path
) -> None:
    github.releases.clear()
    github.seed_release("v0.9.0", _changelog(11), NOW - timedelta(hours=13))
    github.seed_release("v1.1.0", _changelog(11), NOW - timedelta(hours=1), draft=True)
    github.seed_release("v1.2.0-rc.1", _changelog(11), NOW - timedelta(hours=1), prerelease=True)

    _round(github, ledger)

    assert github.calls == [["api", "repos/example/roadmap/releases?per_page=30"]]
    assert github.comments == {}


def test_a_release_older_than_the_window_leaves_the_ledger(
    github: GitHubFake, ledger: Path
) -> None:
    _round(github, ledger)

    _round(github, ledger, now=NOW + timedelta(hours=10))

    assert json.loads(ledger.read_text("utf-8"))["releases"] == {}


# ── Live since ──


def _live(github: GitHubFake, ledger: Path, web: WebFake, rolled: RolledDigests | None) -> None:
    web.serve(RegistryFake(DIGESTS))
    with http_client(EgressLevel.PUBLIC) as client:
        _round(github, ledger, roll=lambda: rolled, client=client)


def _live_comments(github: GitHubFake, number: int, tag: str = "v1.0.0") -> list[str]:
    marker = f"<!-- devops roadmap release {tag} live -->"
    return [body for body in github.comments.get(number, []) if body.startswith(marker)]


def test_only_the_service_image_rolled_gives_no_live_comment(
    github: GitHubFake, ledger: Path, web: WebFake
) -> None:
    rolled = RolledDigests(service=_rolled("v1.0.0").service, runner="sha256:" + "f" * 64)

    _live(github, ledger, web, rolled)

    assert _live_comments(github, 101) == []
    assert len(github.comments[101]) == 1


def test_both_images_rolled_give_one_live_comment_with_the_time_of_the_round(
    github: GitHubFake, ledger: Path, web: WebFake
) -> None:
    _live(github, ledger, web, _rolled("v1.0.0"))

    for number in (101, 102):
        (comment,) = _live_comments(github, number)
        assert comment.split("\n")[1] == "Live since 2026-11-02 12:00 UTC"


def test_a_second_round_posts_no_live_comment_again(
    github: GitHubFake, ledger: Path, web: WebFake
) -> None:
    _live(github, ledger, web, _rolled("v1.0.0"))
    posted = len(github.writes())
    ledger.unlink()

    _live(github, ledger, web, _rolled("v1.0.0"))

    assert len(github.writes()) == posted


def _two_releases(github: GitHubFake) -> None:
    github.seed_issue(13, "pull", state="closed", body="Closes #103", pull_request=True)
    github.seed_issue(103, "three", state="closed")
    github.seed_release("v1.1.0", _changelog(13), NOW - timedelta(hours=1))


def test_a_newer_release_that_runs_makes_the_older_release_live(
    github: GitHubFake, ledger: Path, web: WebFake
) -> None:
    _two_releases(github)

    _live(github, ledger, web, _rolled("v1.1.0"))

    assert len(_live_comments(github, 103, "v1.1.0")) == 1
    assert len(_live_comments(github, 101, "v1.0.0")) == 1
    assert len(_live_comments(github, 102, "v1.0.0")) == 1


def test_an_older_release_that_runs_leaves_the_newer_one_without_a_live_comment(
    github: GitHubFake, ledger: Path, web: WebFake
) -> None:
    _two_releases(github)

    _live(github, ledger, web, _rolled("v1.0.0"))

    assert _live_comments(github, 103, "v1.1.0") == []
    assert len(_live_comments(github, 101, "v1.0.0")) == 1


def test_a_cluster_that_does_not_answer_still_posts_the_released_comments_and_fails_the_row(
    github: GitHubFake, ledger: Path, web: WebFake
) -> None:
    web.serve(RegistryFake(DIGESTS))

    def broken() -> RolledDigests:
        raise ClusterJobError("Deployment devops/roadmap-service not found.")

    with (
        http_client(EgressLevel.PUBLIC) as client,
        pytest.raises(RoadmapRunError, match=r"v1\.0\.0"),
    ):
        _round(github, ledger, roll=broken, client=client)

    assert len(github.comments[101]) == 1
    assert _live_comments(github, 101) == []


def test_a_round_sends_only_reads_and_comments(
    github: GitHubFake, ledger: Path, web: WebFake
) -> None:
    _live(github, ledger, web, _rolled("v1.0.0"))

    assert github.writes()
    for args in github.writes():
        assert args[args.index("-X") + 1] == "POST"
        assert any(arg.endswith("/comments") for arg in args)


# ── A release whose images are not pushed yet ──


def _new_release(github: GitHubFake) -> None:
    """Release `v1.1.0` of 5 minutes ago, with issue 103."""
    github.seed_issue(13, "pull", state="closed", body="Closes #103", pull_request=True)
    github.seed_issue(103, "three", state="closed")
    github.seed_release("v1.1.0", _changelog(13), NOW - timedelta(minutes=5))


def _live_round(
    github: GitHubFake,
    ledger: Path,
    web: WebFake,
    *,
    absent: tuple[str, ...] = (),
    rolled: str = "v1.0.0",
) -> None:
    """A round over a registry that holds every digest but the references in `absent`."""
    web.serve(RegistryFake({k: v for k, v in DIGESTS.items() if k not in absent}))
    with http_client(EgressLevel.PUBLIC) as client:
        _round(github, ledger, roll=lambda: _rolled(rolled), client=client)


def test_a_404_on_a_release_younger_than_the_limit_fails_no_round(
    github: GitHubFake, ledger: Path, web: WebFake
) -> None:
    _new_release(github)

    _live_round(github, ledger, web, absent=(f"{PREFIX}/service:v1.1.0",), rolled="v1.1.0")

    assert _live_comments(github, 103, "v1.1.0") == []
    assert len(github.comments[103]) == 1
    assert json.loads(ledger.read_text("utf-8"))["releases"]["v1.1.0"] == {
        "released": True,
        "live": False,
    }


def test_a_404_on_a_new_release_leaves_the_older_releases_checked_in_the_same_round(
    github: GitHubFake, ledger: Path, web: WebFake
) -> None:
    _new_release(github)

    _live_round(
        github,
        ledger,
        web,
        absent=(f"{PREFIX}/service:v1.1.0", f"{PREFIX}/runner:v1.1.0"),
    )

    assert len(_live_comments(github, 101, "v1.0.0")) == 1
    assert _live_comments(github, 103, "v1.1.0") == []


def test_a_404_on_the_runner_tag_of_a_new_release_is_also_not_yet(
    github: GitHubFake, ledger: Path, web: WebFake
) -> None:
    _new_release(github)

    _live_round(github, ledger, web, absent=(f"{PREFIX}/runner:v1.1.0",), rolled="v1.1.0")

    assert _live_comments(github, 103, "v1.1.0") == []


def test_a_new_release_gets_its_live_comment_in_the_round_after_its_images_are_pushed(
    github: GitHubFake, ledger: Path, web: WebFake
) -> None:
    _new_release(github)
    _live_round(github, ledger, web, absent=(f"{PREFIX}/service:v1.1.0",), rolled="v1.1.0")
    web.servers.clear()

    _live_round(github, ledger, web, rolled="v1.1.0")

    assert len(_live_comments(github, 103, "v1.1.0")) == 1


def test_a_404_on_a_release_at_the_limit_fails_the_round(
    github: GitHubFake, ledger: Path, web: WebFake
) -> None:
    """v1.0.0 is 150 minutes old, far past the limit of 20 minutes."""
    web.serve(RegistryFake({}))

    with (
        http_client(EgressLevel.PUBLIC) as client,
        pytest.raises(RoadmapRunError, match=r"v1\.0\.0"),
    ):
        _round(github, ledger, roll=lambda: _rolled("v1.0.0"), client=client)


def test_a_registry_status_other_than_404_fails_the_round_for_a_new_release(
    github: GitHubFake, ledger: Path, web: WebFake
) -> None:
    _new_release(github)
    manifest = "https://ghcr.io/v2/dan-petty/devops-cli/service/manifests/v1.1.0"
    web.respond("HEAD", manifest, 500)

    with (
        http_client(EgressLevel.PUBLIC) as client,
        pytest.raises(RoadmapRunError, match=r"v1\.1\.0"),
    ):
        _round(github, ledger, roll=lambda: _rolled("v1.1.0"), client=client)
