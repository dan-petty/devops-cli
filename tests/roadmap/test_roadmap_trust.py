"""Which authors the roadmap jobs trust (#2478, #3502): the rule, and the four readers of an item.

The jobs trust an item of a person with write access, and an item whose author login is exactly the
login of the Service App's bot or `github-actions[bot]`. An item of a bot goes to the stage job, the
implement job and the alternatives job only after the review of refine approved it. The roadmap is
the in-memory store, and no model runs.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_ROADMAP_ACTIONS_BOT_LOGIN
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.alternatives import select_items
from devops_cli.roadmap.implement import retry_asked
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.refine import select_candidates
from devops_cli.roadmap.stage import StageSelection, parse_filters, select_stageable
from devops_cli.roadmap.store import (
    IssueComment,
    Item,
    ItemField,
    JudgeVerdict,
    RefineRecordKey,
)
from devops_cli.roadmap.trust import is_approved, is_bot_filed, is_trusted, trusted_replies
from tests.support.roadmap_stage import STAGE_REPO

APP = "devops-cli-service[bot]"
CONTRIBUTOR = "CONTRIBUTOR"
NOW = datetime(2026, 11, 5, 12, tzinfo=UTC)
NO_PLANS = PlannedChanges("main", {}, {})
PLACED = {ItemField.PRIORITY: "P2-Medium"}


@pytest.fixture
def app_login(config: Callable[..., Path]) -> str:
    """The slug of the Service App, so that `APP` is the login of its bot."""
    config(service={"github_app": {"slug": APP.removesuffix("[bot]")}})
    return APP


def _item(
    login: str | None, association: str | None = CONTRIBUTOR, record: dict[str, str] | None = None
) -> Item:
    return Item(
        number=1,
        title="fix(roadmap): a title",
        url="https://example.com/1",
        author_login=login,
        author_association=association,
        job_record={RefineRecordKey(key): value for key, value in (record or {}).items()},
    )


def _comment(login: str | None, association: str | None) -> IssueComment:
    return IssueComment(
        body=f"{login} {association}",
        created_at=NOW,
        author_login=login,
        author_association=association,
    )


# ── The rule ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("login", "association", "trusted"),
    [
        pytest.param("a-person", "OWNER", True, id="owner"),
        pytest.param("a-person", "MEMBER", True, id="member"),
        pytest.param("a-person", "COLLABORATOR", True, id="collaborator"),
        pytest.param(APP, CONTRIBUTOR, True, id="the-service-app"),
        pytest.param(CONST_ROADMAP_ACTIONS_BOT_LOGIN, CONTRIBUTOR, True, id="github-actions"),
        pytest.param("dependabot[bot]", CONTRIBUTOR, False, id="another-bot"),
        pytest.param("a-stranger", "NONE", False, id="a-stranger"),
        pytest.param("a-stranger", CONTRIBUTOR, False, id="a-contributor"),
        pytest.param("a-stranger", None, False, id="no-association"),
        pytest.param(None, None, False, id="no-login"),
    ],
)
def test_the_jobs_trust_a_person_with_write_access_and_the_two_bots_only(
    app_login: str, login: str | None, association: str | None, trusted: bool
) -> None:
    assert is_trusted(_item(login, association)) is trusted


@pytest.mark.parametrize(
    "login",
    [
        f"{APP}x",
        f"x{APP}",
        APP.removesuffix("[bot]"),
        APP.upper(),
        f" {APP}",
        f"{CONST_ROADMAP_ACTIONS_BOT_LOGIN}2",
        CONST_ROADMAP_ACTIONS_BOT_LOGIN.removesuffix("[bot]"),
    ],
)
def test_a_login_that_only_resembles_a_trusted_bot_login_is_not_trusted(
    app_login: str, login: str
) -> None:
    assert (is_bot_filed(_item(login)), is_trusted(_item(login))) == (False, False)


def test_with_no_app_slug_no_item_of_the_service_app_is_trusted(
    config: Callable[..., Path],
) -> None:
    config(service={"github_app": {"slug": None}})

    assert (
        is_trusted(_item(APP)),
        is_trusted(_item(None)),
        is_trusted(_item(CONST_ROADMAP_ACTIONS_BOT_LOGIN)),
    ) == (False, False, True)


def test_an_item_of_a_bot_needs_an_approval_and_an_item_of_a_person_needs_none(
    app_login: str,
) -> None:
    approved = {RefineRecordKey.JUDGE: JudgeVerdict.APPROVED.value}
    refused = {RefineRecordKey.JUDGE: JudgeVerdict.REFUSED.value}

    assert [
        is_approved(_item(APP)),
        is_approved(_item(APP, record=refused)),
        is_approved(_item(APP, record=approved)),
        is_approved(_item(CONST_ROADMAP_ACTIONS_BOT_LOGIN)),
        is_approved(_item(CONST_ROADMAP_ACTIONS_BOT_LOGIN, record=approved)),
        is_approved(_item("a-person", "OWNER")),
    ] == [False, False, True, False, True, True]


def test_the_model_of_refine_reads_the_replies_of_a_person_with_write_access_and_of_the_app_only(
    app_login: str,
) -> None:
    owner = _comment("a-person", "OWNER")
    collaborator = _comment("a-colleague", "COLLABORATOR")
    app = _comment(APP, CONTRIBUTOR)
    comments = [
        _comment("a-stranger", "NONE"),
        owner,
        _comment(CONST_ROADMAP_ACTIONS_BOT_LOGIN, CONTRIBUTOR),
        _comment("dependabot[bot]", CONTRIBUTOR),
        collaborator,
        _comment(f"{APP}x", CONTRIBUTOR),
        _comment(None, None),
        app,
    ]

    assert trusted_replies(comments) == [owner, collaborator, app]


# ── The readers ───────────────────────────────────────────────────────────────


def _seed(
    store: InMemoryRoadmapStore,
    login: str | None,
    association: str | None = CONTRIBUTOR,
    *,
    status: str = "New",
    approved: bool = False,
    title: str = "fix(roadmap): the job drops a comment",
) -> int:
    number = store.seed_issue(
        title,
        body="Body.",
        labels=("type/bug",),
        fields={**PLACED, ItemField.STATUS: status},
        author_login=login,
        author_association=association,
    )
    if approved:
        item = store.item(number)
        assert item is not None
        store.set_marks(item, {RefineRecordKey.JUDGE: JudgeVerdict.APPROVED.value})
    return number


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


def test_the_refine_reader_takes_an_item_of_the_app_and_leaves_out_another_bot_and_a_stranger(
    store: InMemoryRoadmapStore, app_login: str
) -> None:
    taken = _seed(store, APP)
    github = _seed(store, CONST_ROADMAP_ACTIONS_BOT_LOGIN)
    other = _seed(store, "dependabot[bot]")
    stranger = _seed(store, "a-stranger", "NONE")
    lookalike = _seed(store, f"{APP}x")

    selected, waiting = select_candidates(store)

    assert ([item.number for item in selected], sorted(w.item.number for w in waiting)) == (
        [taken, github],
        [other, stranger, lookalike],
    )


def _stage(store: InMemoryRoadmapStore, *, item: int | None = None) -> StageSelection:
    return select_stageable(
        store,
        filters=parse_filters(("status=ready",)),
        holder_of=lambda _issue, _branch: None,
        planned=NO_PLANS,
        item_number=item,
        limit=5,
        planned_limit=5,
    )


def test_the_stage_reader_takes_an_approved_item_of_the_app_and_says_why_it_leaves_out_the_others(
    store: InMemoryRoadmapStore, app_login: str
) -> None:
    taken = _seed(store, APP, status="Ready", approved=True)
    github = _seed(store, CONST_ROADMAP_ACTIONS_BOT_LOGIN, status="Ready", approved=True)
    unjudged = _seed(store, APP, status="Ready")
    other = _seed(store, "dependabot[bot]", status="Ready", approved=True)
    stranger = _seed(store, "a-stranger", "NONE", status="Ready", approved=True)
    person = _seed(store, "a-person", "OWNER", status="Ready")

    selection = _stage(store)

    texts = MESSAGES.roadmap
    assert (
        sorted(target.item.number for target in selection.selected),
        {left.number: left.reason for left in selection.left_out},
    ) == (
        sorted([taken, github, person]),
        {
            unjudged: texts.stage_left_unjudged,
            other: texts.stage_left_author.format(
                author="dependabot[bot]", association=CONTRIBUTOR
            ),
            stranger: texts.stage_left_author.format(author="a-stranger", association="NONE"),
        },
    )


def test_the_alternatives_reader_checks_an_approved_item_of_the_app_and_no_other_bot_item(
    store: InMemoryRoadmapStore, app_login: str
) -> None:
    taken = _seed(store, APP, status="Ready", approved=True)
    _seed(store, APP)
    _seed(store, "dependabot[bot]", approved=True)
    _seed(store, "a-stranger", "NONE")
    person = _seed(store, "a-person", "OWNER")

    selection = select_items(
        store, item_number=None, limit=5, recheck_days=30, retry_days=1, now=NOW
    )

    assert sorted(item.number for item in selection.selected) == sorted([taken, person])


def test_an_implement_retry_comment_of_the_app_starts_no_retry(app_login: str) -> None:
    owner = _comment("a-person", "OWNER")
    owner = owner.model_copy(update={"body": "implement: retry"})
    app = _comment(APP, CONTRIBUTOR).model_copy(update={"body": "implement: retry"})
    actions = _comment(CONST_ROADMAP_ACTIONS_BOT_LOGIN, CONTRIBUTOR).model_copy(
        update={"body": "implement: retry"}
    )

    assert (retry_asked([app]), retry_asked([actions]), retry_asked([app, owner])) == (
        False,
        False,
        True,
    )
