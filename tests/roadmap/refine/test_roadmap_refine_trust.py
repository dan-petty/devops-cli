"""Refine and the items that the Service App or `github-actions[bot]` opens (#3502).

A round takes an item of the Service App's bot or of `github-actions[bot]`, and sets it Ready only
when a review of the issue and the proposal approves it. A refusal is a job failure: the next round
refines the item again with the findings, and the third refusal fails the job (#4798). An item of
another bot or of a stranger waits, and its author gets one comment. The model of refine reads the
replies of trusted authors only. The roadmap is the in-memory store, the proposal step and the
review are test doubles, and git runs on a temporary repository.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import time_machine

from devops_cli.ai.client.models import StructuredOutputValidationError
from devops_cli.config.constants import (
    CONST_ROADMAP_ACTIONS_BOT_LOGIN,
    CONST_ROADMAP_LABELS_PATH,
    CONST_ROADMAP_REFINE_COMMENT_MARKER,
    CONST_ROADMAP_REFINE_MAX_BODY_CHARS,
    CONST_ROADMAP_REFINE_OUTSIDE_MARKER,
)
from devops_cli.roadmap.inbox import InboxKind, read_inbox
from devops_cli.roadmap.refine.refine import (
    AcceptanceCriterion,
    NextStep,
    RefinementProposal,
    RefinePlan,
    apply_refine,
    plan_refine,
)
from devops_cli.roadmap.refine.refine_judge import judge
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_verify import Finding, Locator, PlanPart, Verification
from devops_cli.roadmap.stores.store import ItemField, JudgeVerdict, RefineRecordKey
from devops_cli.roadmap.trust import is_approved
from tests.support.fakes.model import ModelFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
APP = "devops-cli-service[bot]"
CONTRIBUTOR = "CONTRIBUTOR"
_CRITERION = AcceptanceCriterion(
    name="A design",
    requirement="The item SHALL have a design.",
    scenario="A person reads the item",
    when="a person reads the item",
    then="the design is in the item",
)
PREMISE = "The item needs a design."
_READY = RefinementProposal(
    problem_statement=PREMISE,
    acceptance_criteria=[_CRITERION],
    existing_tool="No open tool covers the need.",
)
_FALSE_PREMISE = Finding(
    type=DefectType.FALSE_PREMISE,
    where=Locator(part=PlanPart.PROPOSAL, section="problem_statement"),
    problem="The issue does not say that the item needs a design.",
    quote=PREMISE,
)
_ADVICE = Finding(
    type=DefectType.CONTRIVED_TEST,
    where=Locator(part=PlanPart.PROPOSAL, section="acceptance_criteria"),
    problem="A test repeats the code.",
)
# The line of `_FALSE_PREMISE` that the job record keeps and the next request gives (#4798).
_FALSE_PREMISE_LINE = (
    "`false_premise` at proposal (problem_statement): The issue does not say that the item "
    f'needs a design. Evidence: "{PREMISE}"'
)
_NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
_LABELS = "- name: type/bug\n  color: D73A4A\n  description: A defect\n"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A checkout of `REPO` whose one commit holds `src/sample.py`."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    for key, value in (("user.email", "ci@example.com"), ("user.name", "CI")):
        _git(repo, "config", key, value)
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "remote", "add", "origin", f"https://example.com/{REPO}.git")
    (repo / "src" / "sample.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


@pytest.fixture(autouse=True)
def app_login(config: Callable[..., Path]) -> str:
    """The slug of the Service App, so that `APP` is the login of its bot."""
    config(service={"github_app": {"slug": APP.removesuffix("[bot]")}})
    return APP


class _Proposer:
    """The proposal step's client: it answers each request with `proposal`, or raises it when it is
    an error, and keeps each request document."""

    def __init__(self, proposal: RefinementProposal | Exception = _READY) -> None:
        self.proposal = proposal
        self.prompts: list[str] = []

    def chat_structured(self, system: str, prompt: str, schema: type[Any], **_: Any) -> Any:
        self.prompts.append(prompt)
        if isinstance(self.proposal, Exception):
            raise self.proposal
        return self.proposal


class _Verifier:
    """The client of the review: it answers each request with the `findings` it holds, and keeps
    each request document."""

    def __init__(self, *findings: Finding) -> None:
        self.findings = list(findings)
        self.prompts: list[str] = []

    def chat_structured(self, system: str, prompt: str, schema: type[Any], **_: Any) -> Any:
        self.prompts.append(prompt)
        return Verification(findings=self.findings)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    """A private roadmap, so that no web search runs."""
    return InMemoryRoadmapStore(repo=REPO, is_private=True)


def _seed(
    store: InMemoryRoadmapStore,
    login: str | None = APP,
    association: str | None = CONTRIBUTOR,
    title: str = "feat(roadmap): a report",
) -> int:
    return store.seed_issue(
        title,
        body="Make a report.",
        fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
        author_login=login,
        author_association=association,
    )


def _round(
    store: InMemoryRoadmapStore,
    git_repo: Path,
    proposer: _Proposer,
    verifier: _Verifier,
    *,
    item: int | None = None,
) -> RefinePlan:
    plan = plan_refine(
        store, repo=REPO, source=git_repo, item_number=item, model=proposer, verifier=verifier
    )
    apply_refine(store, plan)
    return plan


def _record(store: InMemoryRoadmapStore, number: int, key: RefineRecordKey) -> str | None:
    item = store.item(number)
    assert item is not None
    return item.job_record.get(key)


def _status(store: InMemoryRoadmapStore, number: int) -> str | None:
    item = store.item(number)
    assert item is not None
    return item.status


def _refine_comments(store: InMemoryRoadmapStore, number: int) -> list[str]:
    marker = CONST_ROADMAP_REFINE_COMMENT_MARKER
    return [c.body for c in store.comments_on(number) if marker in c.body]


# ── The review ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("login", [APP, CONST_ROADMAP_ACTIONS_BOT_LOGIN])
def test_a_ready_proposal_for_an_item_of_a_bot_goes_to_the_review_and_an_approval_sets_it_ready(
    store: InMemoryRoadmapStore, git_repo: Path, login: str
) -> None:
    number = _seed(store, login)
    verifier = _Verifier()

    _round(store, git_repo, _Proposer(), verifier)

    (prompt,) = verifier.prompts
    request = json.loads(prompt)
    assert (
        _status(store, number),
        _record(store, number, RefineRecordKey.JUDGE),
        request["title"],
        request["plan"]["problem_statement"],
    ) == ("Ready", "approved", "feat(roadmap): a report", PREMISE)


def test_a_refusal_is_a_job_failure_that_records_each_finding_and_asks_no_person(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)

    plan = _round(store, git_repo, _Proposer(), _Verifier(_FALSE_PREMISE, _ADVICE))

    (refined,) = plan.refined_items
    assert (
        _status(store, number),
        _record(store, number, RefineRecordKey.JUDGE),
        _record(store, number, RefineRecordKey.NEXT_STEP),
        _record(store, number, RefineRecordKey.TRIES),
        _record(store, number, RefineRecordKey.FAILED_CHECK),
        _record(store, number, RefineRecordKey.JUDGE_FINDINGS),
        (refined.is_ready, refined.next_step),
        _refine_comments(store, number),
    ) == (
        "New",
        "refused",
        "retry",
        "1",
        "judge_refused",
        _FALSE_PREMISE_LINE,
        (False, NextStep.RETRY),
        [],
    )


def test_the_next_round_refines_a_refused_item_again_with_the_findings_and_an_approval_sets_it_ready(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    proposer, verifier = _Proposer(), _Verifier(_FALSE_PREMISE)
    _round(store, git_repo, proposer, verifier)
    verifier.findings = []

    _round(store, git_repo, proposer, verifier)

    first, second = (json.loads(prompt) for prompt in proposer.prompts)
    record = {
        key: _record(store, number, key)
        for key in (
            RefineRecordKey.JUDGE,
            RefineRecordKey.NEXT_STEP,
            RefineRecordKey.TRIES,
            RefineRecordKey.FAILED_CHECK,
            RefineRecordKey.JUDGE_FINDINGS,
        )
    }
    assert (
        first["judge_findings"],
        second["judge_findings"],
        len(verifier.prompts),
        _status(store, number),
        record,
        len(_refine_comments(store, number)),
    ) == (
        [],
        [_FALSE_PREMISE_LINE],
        2,
        "Ready",
        {
            RefineRecordKey.JUDGE: "approved",
            RefineRecordKey.NEXT_STEP: "ready",
            RefineRecordKey.TRIES: None,
            RefineRecordKey.FAILED_CHECK: None,
            RefineRecordKey.JUDGE_FINDINGS: None,
        },
        1,
    )


def test_the_third_refusal_fails_the_job_and_the_inbox_lists_the_item(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    store.seed_file(CONST_ROADMAP_LABELS_PATH, _LABELS)
    store.seed_label("type/bug", "D73A4A", "A defect")
    proposer, verifier = _Proposer(), _Verifier(_FALSE_PREMISE)

    with time_machine.travel(_NOW, tick=False):
        steps = [_round(store, git_repo, proposer, verifier).refined_items for _ in range(3)]
        fourth = _round(store, git_repo, proposer, verifier)
        inbox = read_inbox(store, repo=REPO, now=_NOW, planned_limit=20, draft_days=7, wait_days=7)

    assert (
        [refined.next_step for (refined,) in steps],
        _record(store, number, RefineRecordKey.TRIES),
        [(w.item.number, w.step) for w in fourth.waiting_items],
        (len(proposer.prompts), len(verifier.prompts)),
        [line.number for line in (*inbox.jobs, *inbox.people) if line.kind is InboxKind.FAILED],
        _refine_comments(store, number),
    ) == (
        [NextStep.RETRY, NextStep.RETRY, NextStep.FAILED],
        "3",
        [(number, NextStep.FAILED)],
        (3, 3),
        [number],
        [],
    )


def test_a_failed_refusal_ends_with_a_body_edit(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    proposer, verifier = _Proposer(), _Verifier(_FALSE_PREMISE)
    for _ in range(3):
        _round(store, git_repo, proposer, verifier)
    store.write_issue_body(number, f"{store.read_issue_body(number)}\n\nA person's answer.")

    _round(store, git_repo, proposer, verifier)

    assert (
        len(verifier.prompts),
        _record(store, number, RefineRecordKey.NEXT_STEP),
        _record(store, number, RefineRecordKey.TRIES),
    ) == (4, "retry", "1")


def test_a_body_edit_after_a_refusal_makes_the_review_look_again(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    proposer, verifier = _Proposer(), _Verifier(_FALSE_PREMISE)
    _round(store, git_repo, proposer, verifier)
    store.write_issue_body(number, f"{store.read_issue_body(number)}\n\nA person's answer.")
    verifier.findings = []

    _round(store, git_repo, proposer, verifier)

    assert (
        len(verifier.prompts),
        _status(store, number),
        _record(store, number, RefineRecordKey.JUDGE),
    ) == (2, "Ready", "approved")


def _edit_outside_the_section(store: InMemoryRoadmapStore, number: int) -> None:
    """A person adds a line to the body, outside the section that refine wrote."""
    body = store.read_issue_body(number)
    store.write_issue_body(number, body.replace("Make a report.", "Make a report, with a table."))


def _approved(store: InMemoryRoadmapStore, number: int) -> bool:
    item = store.item(number)
    assert item is not None
    return is_approved(item)


def test_a_body_edit_ends_the_approval_and_a_round_reviews_the_text_again(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    proposer, verifier = _Proposer(), _Verifier()
    _round(store, git_repo, proposer, verifier)
    before = _approved(store, number)

    _edit_outside_the_section(store, number)
    edited = _approved(store, number)
    _round(store, git_repo, proposer, verifier)

    assert (
        before,
        edited,
        _approved(store, number),
        len(verifier.prompts),
        _status(store, number),
    ) == (
        True,
        False,
        True,
        2,
        "Ready",
    )


def test_a_review_that_refuses_the_edited_text_sets_the_item_back_to_new(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    proposer, verifier = _Proposer(), _Verifier()
    _round(store, git_repo, proposer, verifier)
    _edit_outside_the_section(store, number)
    verifier.findings = [_FALSE_PREMISE]

    _round(store, git_repo, proposer, verifier)

    assert (
        _approved(store, number),
        _status(store, number),
        _record(store, number, RefineRecordKey.JUDGE),
        _record(store, number, RefineRecordKey.NEXT_STEP),
    ) == (False, "New", "refused", "retry")


def test_an_item_that_a_round_records_with_no_review_loses_its_approval_too_big_to_refine(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    proposer, verifier = _Proposer(), _Verifier()
    _round(store, git_repo, proposer, verifier)
    _edit_outside_the_section(store, number)
    too_big = _READY.model_copy(
        update={"problem_statement": "A" * CONST_ROADMAP_REFINE_MAX_BODY_CHARS}
    )

    _round(store, git_repo, _Proposer(too_big), verifier)

    assert (
        _approved(store, number),
        _record(store, number, RefineRecordKey.JUDGE),
        _record(store, number, RefineRecordKey.NEXT_STEP),
        len(verifier.prompts),
    ) == (False, None, "edit", 2)


def test_an_item_that_a_round_records_with_no_review_loses_its_approval_failing_on_its_own_text(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    verifier = _Verifier()
    _round(store, git_repo, _Proposer(), verifier)
    _edit_outside_the_section(store, number)
    failing = _Proposer(StructuredOutputValidationError("never valid", violations=2))

    with time_machine.travel(datetime(2026, 11, 8, 12, 0, tzinfo=UTC), tick=False) as clock:
        _round(store, git_repo, failing, verifier)
        clock.shift(timedelta(hours=6))
        _round(store, git_repo, failing, verifier)

    assert (
        _approved(store, number),
        _record(store, number, RefineRecordKey.JUDGE),
        _record(store, number, RefineRecordKey.NEXT_STEP),
        len(verifier.prompts),
    ) == (False, None, "edit", 1)


def test_a_proposal_that_is_not_ready_gets_no_review_and_no_verdict(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    verifier = _Verifier()
    open_proposal = _READY.model_copy(update={"fits_one_pr": False, "split_offs": ["A", "B"]})

    _round(store, git_repo, _Proposer(open_proposal), verifier)

    assert (
        verifier.prompts,
        _status(store, number),
        _record(store, number, RefineRecordKey.JUDGE),
    ) == ([], "New", None)


def test_an_item_of_the_owner_gets_no_review_and_no_verdict(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store, "a-person", "OWNER")
    verifier = _Verifier(_FALSE_PREMISE)

    _round(store, git_repo, _Proposer(), verifier)

    assert (
        verifier.prompts,
        _status(store, number),
        _record(store, number, RefineRecordKey.JUDGE),
    ) == ([], "Ready", None)


def test_item_refines_an_item_of_a_bot_with_the_review_too(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    verifier = _Verifier(_FALSE_PREMISE)

    _round(store, git_repo, _Proposer(), verifier, item=number)

    assert (len(verifier.prompts), _status(store, number)) == (1, "New")


@pytest.mark.parametrize(("login", "tasks"), [(APP, ["verification"]), ("a-person", [])])
def test_the_review_uses_the_client_of_the_verification_task_and_builds_it_only_for_a_bot_item(
    store: InMemoryRoadmapStore,
    git_repo: Path,
    model_fake: ModelFake,
    login: str,
    tasks: list[str],
) -> None:
    model_fake.answer(Verification(findings=[]))
    _seed(store, login, "OWNER" if login == "a-person" else CONTRIBUTOR)

    plan = plan_refine(store, repo=REPO, source=git_repo, model=_Proposer())

    assert (
        [call["task"] for call in model_fake.factory_calls],
        len(model_fake.sent),
        [r.is_ready for r in plan.refined_items],
    ) == (tasks, len(tasks), [True])


def test_the_review_keeps_the_approval_of_an_unchanged_item_with_no_model_call(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    item = store.item(number)
    assert item is not None
    approved = item.model_copy(
        update={"job_record": {RefineRecordKey.JUDGE: JudgeVerdict.APPROVED.value}}
    )
    verifier = _Verifier(_FALSE_PREMISE)

    kept = judge(lambda: verifier, approved, "Body.", _READY, git_repo, unchanged=True, repo=REPO)
    again = judge(lambda: verifier, approved, "Body.", _READY, git_repo, unchanged=False, repo=REPO)

    assert (kept, again[0], len(verifier.prompts)) == (
        (JudgeVerdict.APPROVED, ()),
        JudgeVerdict.REFUSED,
        1,
    )


def test_a_finding_without_a_quote_from_the_input_is_advice_and_refuses_nothing(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    invented = _FALSE_PREMISE.model_copy(update={"quote": "A sentence that no text holds."})

    _round(store, git_repo, _Proposer(), _Verifier(invented))

    assert (_status(store, number), _record(store, number, RefineRecordKey.JUDGE)) == (
        "Ready",
        "approved",
    )


@pytest.mark.parametrize(
    "kind", [DefectType.TASK_ORDER, DefectType.VERIFY_FORM, DefectType.CRITERION_DROPPED]
)
def test_a_finding_on_tasks_is_advice_because_a_proposal_has_no_task_groups(
    store: InMemoryRoadmapStore, git_repo: Path, kind: DefectType
) -> None:
    number = _seed(store)
    finding = _FALSE_PREMISE.model_copy(update={"type": kind})

    _round(store, git_repo, _Proposer(), _Verifier(finding))

    assert (_status(store, number), _record(store, number, RefineRecordKey.JUDGE)) == (
        "Ready",
        "approved",
    )


def test_a_finding_on_a_task_group_is_advice_because_a_proposal_has_no_task_groups(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    finding = _FALSE_PREMISE.model_copy(update={"where": Locator(part=PlanPart.TASKS, section="1")})

    _round(store, git_repo, _Proposer(), _Verifier(finding))

    assert (_status(store, number), _record(store, number, RefineRecordKey.JUDGE)) == (
        "Ready",
        "approved",
    )


def test_a_finding_on_a_criterion_of_the_proposal_with_the_part_issue_refuses_the_item(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    finding = _FALSE_PREMISE.model_copy(
        update={"where": Locator(part=PlanPart.ISSUE, section=_CRITERION.requirement)}
    )

    _round(store, git_repo, _Proposer(), _Verifier(finding))

    assert (_status(store, number), _record(store, number, RefineRecordKey.JUDGE)) == (
        "New",
        "refused",
    )


# ── The other accounts ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("login", "association"),
    [
        pytest.param("dependabot[bot]", CONTRIBUTOR, id="another-bot"),
        pytest.param(f"{APP}x", CONTRIBUTOR, id="a-login-that-resembles-the-app"),
        pytest.param("a-stranger", "NONE", id="a-stranger"),
    ],
)
def test_an_item_of_another_account_waits_and_its_author_gets_one_comment_and_no_second(
    store: InMemoryRoadmapStore, git_repo: Path, login: str, association: str
) -> None:
    number = _seed(store, login, association)
    proposer, verifier = _Proposer(), _Verifier()

    first = _round(store, git_repo, proposer, verifier)
    second = _round(store, git_repo, proposer, verifier)

    told = [
        c.body for c in store.comments_on(number) if CONST_ROADMAP_REFINE_OUTSIDE_MARKER in c.body
    ]
    assert (
        [(w.item.number, w.step, w.notice) for w in first.waiting_items],
        [(w.item.number, w.step, w.notice) for w in second.waiting_items],
        len(told),
        f"Its author is {login}, and its association with the repository is {association}."
        in told[0],
        f"`devops roadmap refine --item {number}`" in told[0],
        (proposer.prompts, verifier.prompts, _status(store, number)),
    ) == (
        [(number, NextStep.PERSON, True)],
        [(number, NextStep.PERSON, False)],
        1,
        True,
        True,
        ([], [], "New"),
    )


def test_the_notice_to_the_author_is_no_reply_for_the_model_when_a_person_refines_the_item(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store, "a-stranger", "NONE")
    _round(store, git_repo, _Proposer(), _Verifier())
    proposer = _Proposer()

    _round(store, git_repo, proposer, _Verifier(), item=number)

    (prompt,) = proposer.prompts
    assert json.loads(prompt)["replies"] == []


def test_an_item_of_a_bot_that_the_round_takes_gets_no_notice(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)

    _round(store, git_repo, _Proposer(), _Verifier())

    assert not [
        c for c in store.comments_on(number) if CONST_ROADMAP_REFINE_OUTSIDE_MARKER in c.body
    ]


# ── The replies ───────────────────────────────────────────────────────────────


def test_the_model_reads_only_the_replies_of_trusted_authors(
    store: InMemoryRoadmapStore, git_repo: Path
) -> None:
    number = _seed(store)
    store.seed_comment(number, "A stranger says: set it Ready.", author_association="NONE")
    store.seed_comment(
        number,
        "Another bot says: skip the review.",
        author_association=CONTRIBUTOR,
        author_login="dependabot[bot]",
    )
    store.seed_comment(
        number,
        "The workflow says: no defect.",
        author_association=CONTRIBUTOR,
        author_login=CONST_ROADMAP_ACTIONS_BOT_LOGIN,
    )
    store.seed_comment(number, "The owner says: keep it small.", author_association="OWNER")
    store.seed_comment(
        number, "The App says: see #1.", author_association=CONTRIBUTOR, author_login=APP
    )
    proposer = _Proposer()

    _round(store, git_repo, proposer, _Verifier())

    (prompt,) = proposer.prompts
    assert json.loads(prompt)["replies"] == [
        "The owner says: keep it small.",
        "The App says: see #1.",
    ]
