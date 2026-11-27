"""Tests for the roadmap step `open` (#5020).

Tests that a second run makes no second pull request, an update changes only differing
fields, a refused text is retried once with form-checked text, dry run sends 0 requests,
second open PR for an issue is refused, commits with [skip ci] are refused, and sweep
recovery opens PRs in at most 3 requests.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_STATUS_IN_PROGRESS,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.roadmap.stores.store import (
    ImplementRecordKey,
    ItemField,
    StageRecordKey,
)
from tests.support.fakes.github import API, github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
BRANCH = "feat/5020-open-step"
BASE = "main"
TITLE = "refactor(roadmap): one open step for every pull request"
BODY = "Consolidate pull request opening.\n\nCloses #5020\n\nChange: `openspec/changes/5020-open-step/`"

LABELS_YML = (
    '- name: "type/refactor"\n  color: "ededed"\n'
    '- name: "scope/roadmap"\n  color: "ededed"\n'
    '- name: "type/bug"\n  color: "ededed"\n'
    '- name: "type/feature"\n  color: "ededed"\n'
)


def _delivery_body(issue: int) -> str:
    """A delivery body that closes `issue` in the form of `pull_form` (#5974)."""
    return f"Consolidate pull request opening.\n\nCloses #{issue}"


def _plan_body(issue: int) -> str:
    """A plan body for `issue` in the form of `plan_body_problems` (#5974)."""
    return (
        f"Plan the open step for every pull request.\n\nPlans #{issue}\n\n"
        f"Change: `openspec/changes/{issue}-open-step/`"
    )


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    s = InMemoryRoadmapStore(repo=REPO)
    s.seed_file(".github/labels.yml", LABELS_YML)
    s.seed_file(".github/labels.yml", LABELS_YML, ref=BASE)
    return s


def _existing_pr_payload(
    number: int = 101,
    title: str = TITLE,
    body: str = BODY,
    head: str = BRANCH,
    base: str = BASE,
    labels: tuple[str, ...] = ("type/refactor", "scope/roadmap"),
) -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": "open",
        "draft": True,
        "html_url": f"https://github.com/{REPO}/pull/{number}",
        "head": {"ref": head, "sha": "headsha123", "repo": {"full_name": REPO}},
        "base": {
            "ref": base,
            "sha": "basesha123",
            "repo": {"full_name": REPO, "default_branch": "main"},
        },
        "labels": [{"name": lbl} for lbl in labels],
    }


def test_second_run_makes_no_second_pull_request(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    """When a PR already exists for head and base, open_or_update creates no duplicate."""
    from devops_cli.roadmap.steps.open import OpenRequest, OpenStatus, open_or_update

    pr_num = store.seed_pull(TITLE, head_ref=BRANCH, labels=("type/refactor", "scope/roadmap"))
    existing = _existing_pr_payload(number=pr_num)
    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls?head=example:{BRANCH}&state=open",
        github_json([existing]),
    )

    request = OpenRequest(
        repo=REPO,
        head=BRANCH,
        base=BASE,
        title=TITLE,
        body=BODY,
        kind="delivery",
        store=store,
    )
    result = open_or_update(request)

    assert result.number == pr_num
    assert result.status == OpenStatus.UNCHANGED
    # Assert no POST to /pulls was made
    posts = [
        req for req in github_api.requested if req.startswith(f"POST {API}/repos/{REPO}/pulls")
    ]
    assert posts == []


def test_update_changes_only_fields_that_differ(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    """When a PR exists and title differs, PATCH updates only differing title."""
    from devops_cli.roadmap.steps.open import OpenRequest, OpenStatus, open_or_update

    pr_num = store.seed_pull(
        "old title", head_ref=BRANCH, labels=("type/refactor", "scope/roadmap")
    )
    existing = _existing_pr_payload(number=pr_num, title="old title", body=BODY)
    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls?head=example:{BRANCH}&state=open",
        github_json([existing]),
    )
    github_api.route(
        "PATCH",
        f"/repos/{REPO}/pulls/{pr_num}",
        github_json({"number": pr_num, "title": TITLE}),
    )

    request = OpenRequest(
        repo=REPO,
        head=BRANCH,
        base=BASE,
        title=TITLE,
        body=BODY,
        kind="delivery",
        store=store,
    )
    result = open_or_update(request)

    assert result.number == pr_num
    assert result.status == OpenStatus.UPDATED
    patches = [
        req
        for req in github_api.requested
        if req.startswith(f"PATCH {API}/repos/{REPO}/pulls/{pr_num}")
    ]
    assert len(patches) == 1
    # Check payload sent in PATCH only includes title
    patch_req = next(r for r in github_api.sent if r.method == "PATCH")
    payload = json.loads(patch_req.content)
    assert payload == {"title": TITLE}


def test_refused_text_sent_again_one_time(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    """When GitHub refuses text on first attempt, retry once with form-checked text (#3599)."""
    from devops_cli.roadmap.steps.open import OpenRequest, OpenStatus, open_or_update

    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls?head=example:{BRANCH}&state=open",
        github_json([]),
    )
    # First POST fails with 422 Unprocessable Entity, second succeeds
    github_api.route(
        "POST",
        f"/repos/{REPO}/pulls",
        github_json({"message": "Validation Failed"}, status=422),
        github_json({"number": 202, "html_url": f"https://github.com/{REPO}/pull/202"}, status=201),
    )

    request = OpenRequest(
        repo=REPO,
        head=BRANCH,
        base=BASE,
        title=TITLE,
        body=BODY,
        kind="delivery",
        store=store,
    )
    result = open_or_update(request)

    assert result.number == 202
    assert result.status == OpenStatus.CREATED
    posts = [
        req for req in github_api.requested if req.startswith(f"POST {API}/repos/{REPO}/pulls")
    ]
    assert len(posts) == 2


def test_dry_run_sees_zero_requests(store: InMemoryRoadmapStore, github_api: GitHubApiFake) -> None:
    """A dry run sends 0 requests to GitHub."""
    from devops_cli.roadmap.steps.open import OpenRequest, OpenStatus, open_or_update

    request = OpenRequest(
        repo=REPO,
        head=BRANCH,
        base=BASE,
        title=TITLE,
        body=BODY,
        kind="delivery",
        store=store,
        dry_run=True,
    )
    result = open_or_update(request)

    assert result.status == OpenStatus.CREATED
    assert github_api.requested == []


def test_refuses_second_open_pr_for_issue(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    """Refuses to open a second pull request for an issue when one already exists."""
    from devops_cli.exceptions.roadmap import RoadmapOpenRefusedError
    from devops_cli.roadmap.steps.open import OpenRequest, open_or_update

    # Seed issue 5020 in store
    store.seed_issue(title=TITLE, body=BODY, fields={ItemField.PRIORITY: "P1-High"})
    # Seed an existing open PR for issue 5020 on another branch
    store.seed_pull("PR for 5020", head_ref="feat/5020-old-branch")

    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls?head=example:{BRANCH}&state=open",
        github_json([]),
    )

    request = OpenRequest(
        repo=REPO,
        head=BRANCH,
        base=BASE,
        title=TITLE,
        body=BODY,
        item=5020,
        kind="delivery",
        store=store,
    )

    with pytest.raises(RoadmapOpenRefusedError, match="already has an open pull request"):
        open_or_update(request)

    posts = [
        req for req in github_api.requested if req.startswith(f"POST {API}/repos/{REPO}/pulls")
    ]
    assert posts == []


def test_refuses_checked_head_with_skip_ci(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    """Refuses a checked head whose commit message holds [skip ci]."""
    from devops_cli.exceptions.roadmap import RoadmapOpenRefusedError
    from devops_cli.roadmap.steps.open import OpenRequest, open_or_update

    request = OpenRequest(
        repo=REPO,
        head=BRANCH,
        base=BASE,
        title=TITLE,
        body=BODY,
        kind="delivery",
        store=store,
        head_commit_message="feat(roadmap): something cool [skip ci]",
    )

    with pytest.raises(RoadmapOpenRefusedError, match="skip ci"):
        open_or_update(request)

    assert github_api.requested == []


def test_sweep_recovery_opens_pr_in_at_most_three_requests(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    """Sweep step recovers a PR when head equals checked_sha in at most 3 requests."""
    from devops_cli.roadmap.steps.open import (
        OpenRequest,
        is_recovery_due,
        recover_open,
    )

    item_num = store.seed_issue(
        title=TITLE,
        body=BODY,
        fields={ItemField.STATUS: CONST_ROADMAP_STATUS_IN_PROGRESS, ItemField.PRIORITY: "P1-High"},
    )
    store.set_marks(store.item(item_num), {ImplementRecordKey.CHECKED_SHA: "sha1234"})

    # Check due condition
    assert is_recovery_due(store.item(item_num), branch_head_sha="sha1234", store=store) is True
    assert (
        is_recovery_due(store.item(item_num), branch_head_sha="different_sha", store=store) is False
    )

    # Route: 1. check open pulls, 2. create draft pull, 3. add labels / comment
    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls?head=example:{BRANCH}&state=open",
        github_json([]),
    )
    github_api.route(
        "POST",
        f"/repos/{REPO}/pulls",
        github_json({"number": 303, "html_url": f"https://github.com/{REPO}/pull/303"}, status=201),
    )

    request = OpenRequest(
        repo=REPO,
        head=BRANCH,
        base=BASE,
        title=TITLE,
        body=_delivery_body(item_num),
        item=item_num,
        kind="delivery",
        store=store,
        producer_sha="sha1234",
    )
    result = recover_open(request)

    assert result.number == 303
    assert len(github_api.requested) <= 3


def test_status_set_for_delivery(store: InMemoryRoadmapStore, github_api: GitHubApiFake) -> None:
    """Opening a delivery pull request writes In Progress status through write_status."""
    from devops_cli.roadmap.steps.open import OpenRequest, OpenStatus, open_or_update

    item_num = store.seed_issue(
        title=TITLE,
        body=BODY,
        fields={ItemField.STATUS: CONST_ROADMAP_STATUS_READY, ItemField.PRIORITY: "P1-High"},
    )

    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls?head=example:{BRANCH}&state=open",
        github_json([]),
    )
    github_api.route(
        "POST",
        f"/repos/{REPO}/pulls",
        github_json({"number": 404, "html_url": f"https://github.com/{REPO}/pull/404"}, status=201),
    )

    request = OpenRequest(
        repo=REPO,
        head=BRANCH,
        base=BASE,
        title=TITLE,
        body=_delivery_body(item_num),
        item=item_num,
        kind="delivery",
        store=store,
    )
    result = open_or_update(request)

    assert result.number == 404
    assert result.status == OpenStatus.CREATED
    assert store.item(item_num).status == CONST_ROADMAP_STATUS_IN_PROGRESS


def test_records_kind_pr_mark(store: InMemoryRoadmapStore, github_api: GitHubApiFake) -> None:
    """Records stage.pr for plan kind, and implement.pr for delivery kind."""
    from devops_cli.roadmap.steps.open import OpenRequest, open_or_update

    item_plan = store.seed_issue(
        title="plan item", body="plan body", fields={ItemField.PRIORITY: "P1-High"}
    )
    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls?head=example:plan-branch&state=open",
        github_json([]),
    )
    github_api.route(
        "POST",
        f"/repos/{REPO}/pulls",
        github_json({"number": 501, "html_url": f"https://github.com/{REPO}/pull/501"}, status=201),
    )

    req_plan = OpenRequest(
        repo=REPO,
        head="plan-branch",
        base=BASE,
        title="docs(roadmap): plan the open step",
        body=_plan_body(item_plan),
        item=item_plan,
        kind="plan",
        store=store,
    )
    open_or_update(req_plan)
    assert store.item(item_plan).job_record.get(StageRecordKey.PR) == "501"

    item_deliv = store.seed_issue(
        title="delivery item", body="delivery body", fields={ItemField.PRIORITY: "P1-High"}
    )
    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls?head=example:deliv-branch&state=open",
        github_json([]),
    )
    github_api.route(
        "POST",
        f"/repos/{REPO}/pulls",
        github_json({"number": 502, "html_url": f"https://github.com/{REPO}/pull/502"}, status=201),
    )

    req_deliv = OpenRequest(
        repo=REPO,
        head="deliv-branch",
        base=BASE,
        title="fix(roadmap): deliver the open step",
        body=_delivery_body(item_deliv),
        item=item_deliv,
        kind="delivery",
        store=store,
    )
    open_or_update(req_deliv)
    assert store.item(item_deliv).job_record.get(ImplementRecordKey.PR) == "502"


def test_upserts_marked_comment(store: InMemoryRoadmapStore, github_api: GitHubApiFake) -> None:
    """Upsert updates an existing marked comment or posts a new comment."""
    from devops_cli.roadmap.steps.open import OpenRequest, open_or_update

    pr_num = store.seed_pull(TITLE, head_ref=BRANCH, labels=("type/refactor", "scope/roadmap"))
    existing = _existing_pr_payload(number=pr_num)
    github_api.route("GET", "/user", github_json({"login": "octocat"}))
    github_api.route(
        "GET",
        f"/repos/{REPO}/pulls?head=example:{BRANCH}&state=open",
        github_json([existing]),
    )
    # Existing comments on issue/PR: contains one with MARKER
    marker = "<!-- roadmap-comment-marker -->"
    github_api.route(
        "GET",
        f"/repos/{REPO}/issues/{pr_num}/comments?per_page=100",
        github_json([{"id": 999, "body": f"{marker}\nold content", "user": {"login": "octocat"}}]),
    )
    github_api.route(
        "PATCH",
        f"/repos/{REPO}/issues/comments/999",
        github_json({"id": 999, "body": f"{marker}\nnew content"}),
    )

    request = OpenRequest(
        repo=REPO,
        head=BRANCH,
        base=BASE,
        title=TITLE,
        body=BODY,
        kind="delivery",
        store=store,
        comment_body=f"{marker}\nnew content",
    )
    result = open_or_update(request)

    assert result.number == pr_num
    patches = [req for req in github_api.requested if "issues/comments/999" in req]
    assert len(patches) == 1


# ── The attribute rules of CI, held before the write (#5974) ─────────────────

# The labels of an item of the type `test`, with the scopes that the tests of this section use.
_ATTRIBUTE_LABELS_YML = LABELS_YML + (
    '- name: "type/test"\n  color: "ededed"\n- name: "scope/k8s"\n  color: "ededed"\n'
)
_RUNTIME_PATH = "src/devops_cli/lang/en/help.py"


def _release_config() -> str:
    """The release-please config of this repository, so the test reads the hidden types that CI
    reads."""
    from pathlib import Path

    from devops_cli.github.release_title import RELEASE_CONFIG_PATH

    return Path(RELEASE_CONFIG_PATH).read_text(encoding="utf-8")


@pytest.fixture
def rules_store() -> InMemoryRoadmapStore:
    s = InMemoryRoadmapStore(repo=REPO)
    s.seed_file(".github/labels.yml", _ATTRIBUTE_LABELS_YML, ref=BASE)
    s.seed_file("release-please-config.json", _release_config(), ref=BASE)
    return s


def _route_diff(github_api: GitHubApiFake, head: str, files: list[tuple[str, str]]) -> None:
    github_api.route(
        "GET",
        f"/repos/{REPO}/compare/{BASE}...{head}?per_page=1",
        github_json(
            {
                "merge_base_commit": {"sha": "basesha123"},
                "files": [{"filename": path, "status": status} for path, status in files],
            }
        ),
    )


def _route_create(github_api: GitHubApiFake, number: int) -> None:
    github_api.route(
        "POST",
        f"/repos/{REPO}/pulls",
        github_json(
            {"number": number, "html_url": f"https://github.com/{REPO}/pull/{number}"}, status=201
        ),
    )


def _posted_title(github_api: GitHubApiFake) -> str:
    sent = next(r for r in github_api.sent if r.method == "POST" and r.url.path.endswith("/pulls"))
    return str(json.loads(sent.content)["title"])


def _open_test_item(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    files: list[tuple[str, str]],
    *,
    title: str = "test(roadmap): Keep the Planned limit in the stage job",
) -> Any:
    from devops_cli.roadmap.steps.open import OpenRequest, open_or_update

    item = store.seed_issue(
        "test(roadmap): the Planned limit stays out of refine",
        fields={ItemField.PRIORITY: "P2-Medium"},
    )
    head = f"test/{item}-the-planned-limit"
    _route_diff(github_api, head, files)
    _route_create(github_api, 901)
    return open_or_update(
        OpenRequest(
            repo=REPO,
            head=head,
            base=BASE,
            title=title,
            body=_delivery_body(item),
            kind="delivery",
            item=item,
            store=store,
            lookup_existing=False,
        )
    )


def test_a_runtime_diff_of_a_test_item_gets_a_title_that_ships_a_release_and_passes_ci(
    rules_store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    """#5940: the item has the type `test`, which release-please hides, and the diff changes
    runtime code. The step writes a type that ships a release, and the title passes the rules
    that the `Semantic PR title` check runs."""
    from devops_cli.github.release_title import hidden_type_problem
    from devops_cli.roadmap.pull_form import title_problems
    from devops_cli.roadmap.title_labels import declared_label_names

    files = [(_RUNTIME_PATH, "modified"), ("tests/roadmap/test_roadmap_inbox.py", "modified")]
    result = _open_test_item(rules_store, github_api, files)

    posted = _posted_title(github_api)
    config = json.loads(_release_config())
    declared = declared_label_names(_ATTRIBUTE_LABELS_YML)
    assert (
        posted,
        result.title,
        hidden_type_problem(posted, [path for path, _ in files], config),
        title_problems(posted, declared),
        "type/bug" in result.labels,
        "type/test" in result.labels,
    ) == (
        "fix(roadmap): Keep the Planned limit in the stage job",
        posted,
        None,
        [],
        True,
        False,
    )


def test_a_diff_that_adds_a_runtime_module_gets_the_type_feat(
    rules_store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    """#5920 added a module under a `test` type, and a person retitled it to `feat`."""
    files = [("src/devops_cli/k8s/volume_move_measure.py", "added"), (_RUNTIME_PATH, "modified")]

    _open_test_item(
        rules_store, github_api, files, title="test(k8s): Add the volume move copy harness"
    )

    assert _posted_title(github_api) == "feat(k8s): Add the volume move copy harness"


def test_a_hidden_type_with_documents_only_keeps_its_type(
    rules_store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    files = [("docs/roadmap/stage.md", "modified"), ("tests/roadmap/test_x.py", "added")]

    _open_test_item(rules_store, github_api, files)

    assert _posted_title(github_api) == "test(roadmap): Keep the Planned limit in the stage job"


def test_a_shown_type_reads_no_diff(
    rules_store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    _open_test_item(rules_store, github_api, [], title="fix(roadmap): Keep the Planned limit")

    assert [r for r in github_api.requested if "/compare/" in r] == []


def test_a_scope_that_the_labels_file_lacks_is_dropped(
    rules_store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    _open_test_item(rules_store, github_api, [], title="fix(nowhere): Keep the Planned limit")

    assert _posted_title(github_api) == "fix: Keep the Planned limit"


def test_a_long_summary_is_refused_and_nothing_is_written(
    rules_store: InMemoryRoadmapStore, github_api: GitHubApiFake
) -> None:
    from devops_cli.exceptions.roadmap import RoadmapOpenRefusedError

    long_title = "fix(roadmap): " + "Keep the limit " * 5

    with pytest.raises(RoadmapOpenRefusedError, match="60"):
        _open_test_item(rules_store, github_api, [], title=long_title)

    assert [r for r in github_api.requested if r.startswith("POST")] == []


@pytest.mark.parametrize(
    ("kind", "body", "problem"),
    [
        ("plan", "Plan the open step for every pull request.\n\nCloses #{item}", "closes no"),
        ("delivery", "Deliver the open step for every pull request.\n\nCloses #1", "another"),
        ("delivery", "Deliver the open step for every pull request.", "Closes #<issue>"),
    ],
)
def test_a_body_that_breaks_the_keyword_rule_is_refused(
    rules_store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    kind: str,
    body: str,
    problem: str,
) -> None:
    """A plan closes no issue, and a delivery closes only the issue that it delivers."""
    from devops_cli.exceptions.roadmap import RoadmapOpenRefusedError
    from devops_cli.roadmap.steps.open import OpenRequest, open_or_update

    rules_store.seed_issue("unrelated", fields={ItemField.PRIORITY: "P2-Medium"})
    item = rules_store.seed_issue(
        "fix(roadmap): the open step", fields={ItemField.PRIORITY: "P2-Medium"}
    )
    request = OpenRequest(
        repo=REPO,
        head=f"fix/{item}-open-step",
        base=BASE,
        title="fix(roadmap): Check the open step",
        body=body.format(item=item),
        kind=kind,
        item=item,
        store=rules_store,
        lookup_existing=False,
    )

    with pytest.raises(RoadmapOpenRefusedError, match=problem):
        open_or_update(request)

    assert [r for r in github_api.requested if r.startswith("POST")] == []


def test_a_draft_body_over_the_limit_above_closes_is_refused() -> None:
    """A draft body has no `Change:` line yet, and the limit measures the text above `Closes`, so
    the `Closes` line does not count (#6633)."""
    from devops_cli.roadmap.pull_form import BODY_MAX_CHARS, open_body_problems

    at_limit = f"{'a' * BODY_MAX_CHARS}\n\nCloses #5020"
    over_limit = f"{'a' * (BODY_MAX_CHARS + 1)}\n\nCloses #5020"

    assert open_body_problems(at_limit, issue=5020, plan=False) == []
    problems = open_body_problems(over_limit, issue=5020, plan=False)
    assert [f"has {BODY_MAX_CHARS + 1} characters" in problem for problem in problems] == [True]


@pytest.mark.parametrize(
    ("pull_payload", "expect_request"),
    [
        pytest.param(
            {
                "number": 701,
                "html_url": f"https://github.com/{REPO}/pull/701",
                "user": {"login": "devops-cli-service[bot]"},
                "requested_reviewers": [],
            },
            True,
            id="bot-author",
        ),
        pytest.param(
            {
                "number": 701,
                "html_url": f"https://github.com/{REPO}/pull/701",
                "user": {"login": "dan-petty"},
                "requested_reviewers": [],
            },
            False,
            id="reviewer-is-author",
        ),
        pytest.param(
            {
                "number": 701,
                "html_url": f"https://github.com/{REPO}/pull/701",
                "user": {"login": "devops-cli-service[bot]"},
                "requested_reviewers": [{"login": "dan-petty"}],
            },
            False,
            id="already-requested",
        ),
    ],
)
def test_open_requests_missing_non_author_reviewers(
    store: InMemoryRoadmapStore,
    github_api: GitHubApiFake,
    pull_payload: dict[str, Any],
    expect_request: bool,
) -> None:
    """When opening a new draft PR, request reviewers only if not author or already requested."""
    from devops_cli.roadmap.steps.open import OpenRequest, open_or_update

    item_num = store.seed_issue(title=TITLE, body=BODY, fields={ItemField.PRIORITY: "P1-High"})
    github_api.route("POST", f"/repos/{REPO}/pulls", github_json(pull_payload, status=201))
    if expect_request:
        github_api.route(
            "POST",
            f"/repos/{REPO}/pulls/701/requested_reviewers",
            github_json({"requested_reviewers": [{"login": "dan-petty"}]}),
        )

    open_or_update(
        OpenRequest(
            repo=REPO,
            head=BRANCH,
            base=BASE,
            title=TITLE,
            body=_delivery_body(item_num),
            kind="delivery",
            item=item_num,
            store=store,
            lookup_existing=False,
            reviewers=("dan-petty",),
        )
    )

    reviewer_posts = [
        req for req in github_api.requested if req.endswith("/pulls/701/requested_reviewers")
    ]
    assert reviewer_posts == (
        [f"POST {API}/repos/{REPO}/pulls/701/requested_reviewers"] if expect_request else []
    )
    if expect_request:
        reviewer_call = next(
            req
            for req in github_api.sent
            if req.url.path.endswith("/pulls/701/requested_reviewers")
        )
        assert json.loads(reviewer_call.content) == {"reviewers": ["dan-petty"]}


@pytest.mark.parametrize(
    ("head", "recorded"),
    [("docs/{number}-plan-the-open-step", True), ("plan-branch", False)],
    ids=["names-the-item", "names-no-item"],
)
def test_a_plan_records_its_head_branch_when_the_branch_names_the_item(
    store: InMemoryRoadmapStore, github_api: GitHubApiFake, head: str, recorded: bool
) -> None:
    """The step records `stage.branch` in the write of `stage.pr` (#7347): a row takes a pull
    request as the plan of an item by its number and its head branch (`recorded_plan`). A head
    branch that does not name the item is not recorded."""
    from devops_cli.roadmap.steps.open import OpenRequest, open_or_update
    from devops_cli.roadmap.stores import store as record_store

    number = store.seed_issue(
        title="plan item", body="plan body", fields={ItemField.PRIORITY: "P1-High"}
    )
    branch = head.format(number=number)
    github_api.route(
        "GET", f"/repos/{REPO}/pulls?head=example:{branch}&state=open", github_json([])
    )
    github_api.route(
        "POST",
        f"/repos/{REPO}/pulls",
        github_json({"number": 501, "html_url": f"https://github.com/{REPO}/pull/501"}, status=201),
    )
    writes = len(store.job_writes())

    open_or_update(
        OpenRequest(
            repo=REPO,
            head=branch,
            base=BASE,
            title="docs(roadmap): plan the open step",
            body=_plan_body(number),
            item=number,
            kind="plan",
            store=store,
        )
    )

    item = store.item(number)
    assert item is not None
    plan = record_store.recorded_plan(item)
    assert (item.job_record.get(StageRecordKey.BRANCH), plan and tuple(plan)) == (
        (branch, (501, branch)) if recorded else (None, None)
    )
    assert [write.key for write in store.job_writes()[writes:]] == (
        ["stage.pr", "stage.branch"] if recorded else ["stage.pr"]
    )
