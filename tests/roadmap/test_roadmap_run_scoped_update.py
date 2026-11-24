"""The scoped update that a webhook delivery runs at once, and the poll that reconciles after it
(#1533). The scoped intake reads every issue through the listing snapshot (#3670), a pull
request, review or check suite delivery runs the watch row scoped to its pull requests (#4413),
and a trusted comment runs the row that its text wakes, on the checkout of that row's lane
(#4415).
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import httpx2
import pytest

from devops_cli.ai.client import LLMClient
from devops_cli.config.constants import (
    CONST_GITHUB_CLONE_URL,
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_WATCH_LEDGER_FILENAME,
)
from devops_cli.config.settings import AIConfig
from devops_cli.roadmap.intake.intake_model import GatewayIntakeModel, ModelProposal
from devops_cli.roadmap.run import (
    SCOPED_UPDATES,
    JobOutcome,
    WebhookDelivery,
    lane_clone_dirname,
    lane_of_row,
    read_intake_record,
    run_scoped_update,
    service_state_dir,
)
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.listing_snapshot import intake_listing
from devops_cli.roadmap.stores.store import (
    CloseReason,
    ImplementRecordKey,
    ItemField,
    StageRecordKey,
)
from tests.support.fakes.embeddings import FakeEmbedder
from tests.support.fakes.git import GitFake
from tests.support.fakes.github import API, GitHubApiFake, RunnerSession, github_json
from tests.support.fakes.http import WebFake
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.llm_stream_fakes import serve_llm
from tests.support.roadmap_intake import FINISHED, on_github
from tests.support.roadmap_run import (
    NOW,
    REPO,
    REPO_DIR,
    TWENTY_MINUTES_AGO,
    IntakeModel,
    bare_remote,
    intake_table,
    make_candidates,
    poll_round,
    read_schedule,
    serve_as,
    stamp_successes,
    webhook_delivery,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

# The `pull_request` actions that change the state or the checks of a staged draft.
_PULL_ACTIONS = (
    "opened",
    "reopened",
    "synchronize",
    "closed",
    "labeled",
    "unlabeled",
    "ready_for_review",
)

_HEAD = "4" * 40

_INFRA_CHECK = "Semantic PR title"


@pytest.fixture
def github_api(github_api_and_gh: tuple[GitHubApiFake, ProcessFake]) -> GitHubApiFake:
    """GitHub's API faked for every GitHub session."""
    api, _process = github_api_and_gh
    return api


def _staged_draft(store: InMemoryRoadmapStore, pull: int) -> int:
    """An open Item of `store` whose record names the staged draft `pull`."""
    issue = store.seed_issue(f"Plan {pull}", fields={ItemField.PRIORITY: "P1-High"})
    item = store.item(issue)
    assert item is not None
    store.set_marks(item, {StageRecordKey.PR: str(pull)})
    return issue


def _route_open_draft(api: GitHubApiFake, pull: int) -> None:
    """Answer the reads of the open plan draft `pull`, whose infra check fails, so that the round
    reads it and takes no ready path."""
    api.route(
        "GET",
        f"/repos/{REPO}/pulls/{pull}",
        github_json(
            {
                "number": pull,
                "state": "open",
                "merged": False,
                "draft": True,
                "body": f"The plan of pull {pull}.",
                "head": {"sha": _HEAD, "ref": f"feat/{pull}-plan"},
                "base": {"ref": "main", "repo": {"default_branch": "main"}},
            }
        ),
    )
    api.route(
        "GET",
        f"/repos/{REPO}/commits/{_HEAD}/check-runs",
        github_json(
            {"check_runs": [{"name": _INFRA_CHECK, "status": "completed", "conclusion": "failure"}]}
        ),
    )


def _delivery(event: str, action: str, *pulls: int) -> WebhookDelivery:
    """A delivery of `event` with `action` that names pull requests `pulls`."""
    return WebhookDelivery(repo=REPO, event=event, action=action, pull_numbers=pulls)


def _comment(text: str, number: int) -> WebhookDelivery:
    """A delivery of the comment `text` that a trusted person wrote on issue `number`."""
    return WebhookDelivery(
        repo=REPO, event="issue_comment", action="created", number=number, comment=text
    )


def _for_pull(requests: list[str], pull: int) -> list[str]:
    """Each request of `requests` that names pull request `pull`."""
    return [request for request in requests if f"/pulls/{pull}" in request]


def _blocked_with_retry(store: InMemoryRoadmapStore) -> int:
    """A Blocked item that a stop of the implement job left, its stop comment, and the retry
    comment of a person after it."""
    number = store.seed_issue("fix(cli): the job stopped", fields={ItemField.PRIORITY: "P1-High"})
    item = store.item(number)
    assert item is not None
    store.set_field(
        item,
        ItemField.STATUS,
        "Blocked",
        marks={
            ImplementRecordKey.STOPPED: "group 2",
            ImplementRecordKey.JOB: "devops-cli-runner-1",
            ImplementRecordKey.JOB_STATE: "failed",
        },
    )
    store.seed_comment(
        number,
        f"{CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER}\nStopped at group 2.",
        author_association="NONE",
    )
    store.as_actor("owner").comment(number, "implement: retry")
    return number


@pytest.mark.usefixtures("cluster")
def test_a_comment_delivery_runs_the_row_that_its_text_wakes(
    github_api: GitHubApiFake,
    child_argvs: list[list[str]],
    git_fake: GitFake,
    tmp_path: Path,
) -> None:
    """Test first for #4415: a delivery of a comment runs the row that its text wakes, scoped to the
    issue it names and on the checkout of that row's lane. `implement: retry` runs the `implement`
    row, whose own rule clears the stop of the item; any other comment runs the `refine` row, which
    reads the one item that the reply names and no other candidate."""
    from devops_cli.roadmap.run import scoped_update_of

    # The lane clones that the Service's rows read, and the origin they clone (#5553).
    git_fake.answer(
        lambda call: "remote get-url" in " ".join(call.argv),
        ProcessAnswer(stdout=f"https://github.com/{REPO}.git\n"),
    )
    serve_as(CONST_GITHUB_CLONE_URL.format(repo=REPO), bare_remote(tmp_path))
    store, _, _ = make_candidates(3)
    blocked = _blocked_with_retry(store)

    rows = {
        text: scoped_update_of(_comment(text, blocked)) for text in ("implement: retry", "reply")
    }
    seeded = len(store.job_writes())
    reply = run_scoped_update(_comment("reply", 2), store, data_dir=tmp_path, now=NOW)
    reply_writes = len(store.job_writes()) - seeded
    unnumbered = run_scoped_update(
        WebhookDelivery(repo=REPO, event="issue_comment", action="created", comment="reply"),
        store,
        data_dir=tmp_path,
        now=NOW,
    )
    retry = run_scoped_update(
        _comment("implement: retry", blocked), store, data_dir=tmp_path, now=NOW
    )
    item = store.item(blocked)
    assert item is not None

    assert (
        {text: (update.job, lane_of_row(update.job)) for text, update in rows.items()},
        reply,
        reply_writes,
        unnumbered,
        retry,
        (item.status, item.job_record.get(ImplementRecordKey.STOPPED)),
        {
            lane: any(lane_clone_dirname(lane) in " ".join(argv) for argv in child_argvs)
            for lane in ("refine", "implement")
        },
    ) == (
        {"implement: retry": ("implement", "implement"), "reply": ("refine", "refine")},
        JobOutcome(set_ready=False, queue=0),
        0,
        JobOutcome(),
        JobOutcome(),
        ("Ready", None),
        {"refine": True, "implement": True},
    )


def test_the_issues_actions_run_a_scoped_intake_on_the_lane_of_intake() -> None:
    """`issues` opened, edited and reopened each run intake of one issue, on the lane of intake,
    and each pull request, review and check suite action runs the watch row, on the lane of
    watch (#1534, #4413, #5553)."""
    assert {
        key: (update.job, lane_of_row(update.job)) for key, update in SCOPED_UPDATES.items()
    } == {
        ("issues", "opened"): ("intake", "intake"),
        ("issues", "edited"): ("intake", "intake"),
        ("issues", "reopened"): ("intake", "intake"),
        **{("pull_request", action): ("watch", "watch") for action in _PULL_ACTIONS},
        ("pull_request_review", "submitted"): ("watch", "watch"),
        ("check_suite", "completed"): ("watch", "watch"),
    }
    assert {
        lane_of_row(update.job, {"status": ["watch"]})
        for key, update in SCOPED_UPDATES.items()
        if key[0] != "issues"
    } == {"status"}


@pytest.mark.usefixtures("cluster")
def test_a_pull_request_delivery_runs_the_scoped_watch_round(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """A `pull_request` delivery reads only the pull request it names, a `check_suite` delivery
    reads each pull request of the suite, and a delivery that matches no staged draft sends no
    request (#4413)."""
    store, _, _ = make_candidates(0)
    _staged_draft(store, 42)
    _staged_draft(store, 43)
    _route_open_draft(github_api, 42)
    _route_open_draft(github_api, 43)
    start = len(github_api.requested)

    run_scoped_update(
        _delivery("pull_request", "synchronize", 42), store, data_dir=tmp_path, now=NOW
    )
    pull_round = github_api.requested[start:]
    start = len(github_api.requested)
    run_scoped_update(
        _delivery("check_suite", "completed", 42, 43), store, data_dir=tmp_path, now=NOW
    )
    suite_round = github_api.requested[start:]
    start = len(github_api.requested)
    unmatched = run_scoped_update(
        _delivery("pull_request", "synchronize", 99), store, data_dir=tmp_path, now=NOW
    )

    assert (
        bool(_for_pull(pull_round, 42)),
        _for_pull(pull_round, 43),
        bool(_for_pull(suite_round, 42)),
        bool(_for_pull(suite_round, 43)),
        _for_pull(github_api.requested[start:], 99),
        unmatched,
        (tmp_path / REPO_DIR / CONST_ROADMAP_WATCH_LEDGER_FILENAME).exists(),
        (tmp_path / REPO_DIR / "schedule.json").exists(),
    ) == (True, [], True, True, [], JobOutcome(), True, False)


@pytest.mark.parametrize("action", ["opened", "edited", "reopened"])
def test_an_issues_delivery_intakes_only_its_issue_and_writes_no_last_success(
    action: str, tmp_path: Path
) -> None:
    """The scoped update of an `issues` delivery decides and places only the issue it names: the
    model judges it alone, only it gets labels, and `schedule.json` keeps each job's last
    success as it was."""
    store, _, _ = make_candidates(3)
    stamp_successes(tmp_path, intake=TWENTY_MINUTES_AGO)
    model = IntakeModel()

    outcome = run_scoped_update(
        webhook_delivery(action, 2), store, data_dir=tmp_path, now=NOW, model=model
    )

    assert (
        outcome,
        model.asked,
        sorted({write.number for write in store.job_writes()}),
        [store.item(number) is not None for number in (1, 2, 3)],
        read_schedule(tmp_path),
    ) == (
        JobOutcome(),
        ["candidate 2"],
        [2],
        [False, True, False],
        {"intake": TWENTY_MINUTES_AGO.isoformat()},
    )


def test_an_issues_delivery_that_names_no_issue_number_decides_nothing(tmp_path: Path) -> None:
    """A delivery that names no issue number runs the scoped intake of no issue: the model judges
    nothing and the intake record stays unwritten (#4413)."""
    store, _, _ = make_candidates(2)
    model = IntakeModel()

    outcome = run_scoped_update(
        WebhookDelivery(repo=REPO, event="issues", action="opened"),
        store,
        data_dir=tmp_path,
        now=NOW,
        model=model,
    )

    assert (
        outcome,
        model.asked,
        store.job_writes(),
        (tmp_path / REPO_DIR / "intake.json").exists(),
    ) == (JobOutcome(), [], [], False)


def test_an_edit_of_an_item_and_an_event_with_no_scoped_update_change_nothing(
    tmp_path: Path,
) -> None:
    """An edit of an issue that is already an Item decides nothing and writes no record. An
    `issues` action or an event with no scoped update returns None, so its delivery stays a hint
    for a whole round."""
    store, _, _ = make_candidates(0)
    placed = store.seed_issue("placed", fields={ItemField.PRIORITY: "P2-Medium"})
    model = IntakeModel()

    def run(delivery: WebhookDelivery) -> JobOutcome | None:
        return run_scoped_update(delivery, store, data_dir=tmp_path, now=NOW, model=model)

    edited = run(webhook_delivery("edited", placed))
    closed = run(webhook_delivery("closed", placed))
    requested = run(webhook_delivery("requested", placed, event="check_suite"))

    assert (
        edited,
        closed,
        requested,
        model.asked,
        store.job_writes(),
        (tmp_path / REPO_DIR / "intake.json").exists(),
    ) == (JobOutcome(), None, None, [], [], False)


@pytest.mark.parametrize("lost", ["opened", "reopened"])
def test_a_poll_after_a_scoped_update_decides_the_lost_delivery_and_not_the_handled_one(
    lost: str, tmp_path: Path
) -> None:
    """Test first for #2009: the delivery of issue 2 runs its scoped update, and the delivery of
    issue 1 is lost. The next poll comes before intake's hourly interval. It runs intake, which
    decides issue 1 and does not decide issue 2 again."""
    store, clock, _ = make_candidates(1)
    if lost == "reopened":
        store.close_by_hand(1, CloseReason.NOT_PLANNED)
        clock.now = NOW - timedelta(minutes=5)
        store.reopen_issue(1)
    delivered = store.seed_issue("candidate 2")
    stamp_successes(tmp_path, intake=TWENTY_MINUTES_AGO)
    model = IntakeModel()
    ran: list[str] = []

    run_scoped_update(
        webhook_delivery("opened", delivered), store, data_dir=tmp_path, now=NOW, model=model
    )
    after_update = read_schedule(tmp_path)
    jobs = poll_round(
        store, tmp_path, now=NOW + timedelta(minutes=5), table=intake_table(model, ran)
    )

    assert (
        after_update,
        jobs,
        model.asked,
        store.item(1) is not None,
        store.item(delivered) is not None,
    ) == (
        {"intake": TWENTY_MINUTES_AGO.isoformat()},
        ("intake",),
        ["candidate 2", "candidate 1"],
        True,
        True,
    )


def test_a_new_issue_whose_delivery_was_lost_makes_intake_due_at_the_next_poll(
    tmp_path: Path,
) -> None:
    """Test first for #4540: intake decides candidate 1, then candidate 2 opens and no scoped
    update runs for it. The next poll comes before intake's interval and runs intake, which
    decides candidate 2. A new pull request after it makes intake due at no poll."""
    store, _, _ = make_candidates(1)
    model = IntakeModel()
    table = intake_table(model, [])
    poll_round(store, tmp_path, table=table)
    store.seed_issue("candidate 2")

    lost = poll_round(store, tmp_path, now=NOW + timedelta(minutes=5), table=table)
    store.seed_pull("a pull request", head_ref="feat/1-a-change")
    after_pull = poll_round(store, tmp_path, now=NOW + timedelta(minutes=10), table=table)

    assert (lost, after_pull, model.asked) == (
        ("intake",),
        (),
        ["candidate 1", "candidate 2"],
    )


def test_a_new_issue_that_its_scoped_update_decided_costs_the_next_intake_no_model_request(
    tmp_path: Path,
) -> None:
    """Test first for #4540: the scoped update of new candidate 2 decides it. The scoped update
    does not mark the issue as seen, so the next poll runs intake. That intake finds nothing to
    decide and sends no model request, and the poll after it runs no intake."""
    store, _, _ = make_candidates(1)
    model = IntakeModel()
    table = intake_table(model, [])
    poll_round(store, tmp_path, table=table)
    opened = store.seed_issue("candidate 2")
    run_scoped_update(
        webhook_delivery("opened", opened),
        store,
        data_dir=tmp_path,
        now=NOW + timedelta(minutes=1),
        model=model,
    )
    asked = list(model.asked)

    jobs = (
        poll_round(store, tmp_path, now=NOW + timedelta(minutes=5), table=table),
        poll_round(store, tmp_path, now=NOW + timedelta(minutes=10), table=table),
    )

    assert (asked, jobs, model.asked) == (
        ["candidate 1", "candidate 2"],
        (("intake",), ()),
        ["candidate 1", "candidate 2"],
    )


def test_a_scoped_update_keeps_the_entries_and_the_pending_flag_a_capped_round_left(
    tmp_path: Path,
) -> None:
    """A capped round decides five of seven candidates and leaves a fresh one. A scoped update of
    candidate 6 adds its entry, keeps the five others and keeps intake due. The next poll decides
    candidate 7 alone."""
    store, _, titles = make_candidates(7)
    model = IntakeModel()
    table = intake_table(model, [])
    poll_round(store, tmp_path, table=table)

    run_scoped_update(
        webhook_delivery("opened", 6),
        store,
        data_dir=tmp_path,
        now=NOW + timedelta(minutes=1),
        model=model,
    )
    record = read_intake_record(tmp_path / REPO_DIR / "intake.json")
    asked = len(model.asked)
    poll_round(store, tmp_path, now=NOW + timedelta(minutes=5), table=table)

    assert (record.pending, sorted(record.waiting), model.asked[asked:]) == (
        True,
        [1, 2, 3, 4, 5, 6],
        [titles[6]],
    )


_AI_SERIES = (
    "devops_cli_ai_requests_total",
    "devops_cli_ai_tokens_total",
    "devops_cli_ai_spend_usd_total",
)


def test_the_model_requests_of_a_scoped_intake_carry_the_intake_row(
    tmp_path: Path, web: WebFake, embedder: FakeEmbedder, otlp: FakeCollector
) -> None:
    """Test first for #4522: the model request of the scoped intake of an `issues.opened`
    delivery names the row `intake` on its request, token and spend series, as the job counter
    of the same update does, and not `other`."""
    store, _, _ = make_candidates(1)
    proposal = ModelProposal(
        type="type/feature",
        type_reason="it adds a capability.",
        priority="P2-Medium",
        priority_reason="useful, not urgent.",
        value="Medium",
        value_reason="it helps maintainers.",
        effort="Low",
        effort_reason="one module.",
    )
    reply = {
        "model": "gpt-4o",
        "choices": [{"message": {"content": proposal.model_dump_json()}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    serve_llm(web, lambda _request: httpx2.Response(200, json=reply))
    client = LLMClient(
        AIConfig(provider="openai", model="gpt-4o", api_base_url="https://example.com/v1"),
        api_key="sk-test",
        cache_enabled=False,
    )
    model = GatewayIntakeModel(AIConfig(), embedder=embedder, client=client)

    run_scoped_update(webhook_delivery("opened", 1), store, data_dir=tmp_path, now=NOW, model=model)

    assert {
        name: sorted({attributes["row"] for attributes, _ in otlp.points(name)})
        for name in _AI_SERIES
    } == {name: ["intake"] for name in _AI_SERIES}


def test_a_scoped_intake_with_a_kept_snapshot_reads_only_the_issues_changed_since_it(
    tmp_path: Path,
) -> None:
    """Test first for #3670: the intake of the Service reads every issue through the snapshot in
    its state directory. With a snapshot of 250 items kept, the delivery of a new issue sends one
    listing request, of the issues changed since the watermark, and no read of the whole
    listing; the new issue is placed."""
    github, _ = on_github()
    for number in range(1, 251):
        changed = NOW - timedelta(days=2, minutes=number)
        github.seed_issue(number, f"feat: item {number}", labels=FINISHED, updated_at=changed)
    listing = intake_listing(service_state_dir(tmp_path))

    def store() -> GitHubRoadmapStore:
        return GitHubRoadmapStore(
            REPO, runner=github, session=RunnerSession(github), listing=listing
        )

    store().issues()
    github.seed_issue(251, "feat: new idea", updated_at=NOW)
    start = len(github.calls)

    run_scoped_update(
        webhook_delivery("opened", 251), store(), data_dir=tmp_path, now=NOW, model=IntakeModel()
    )

    listings = [
        args[0]
        for args in github.calls[start:]
        if args[0].startswith(f"{API}/repos/{REPO}/issues?")
    ]
    assert (listings, [label for label in github.labels(251) if "priority" in label]) == (
        [
            f"{API}/repos/{REPO}/issues?state=all&sort=updated&direction=desc"
            "&since=2026-10-02T11:58:00Z&per_page=100"
        ],
        ["priority/p2-medium"],
    )
