"""A refine round whose job fails makes no person wait (#3632).

A proposal that fails a form check, a question that no read tool answers and an investigation that
ends with no proposal are job failures: the record counts the tries, a later round tries again, and
at the limit the item waits on a body edit and the inbox lists it. A question marked `(a person
decides)` still makes a person wait. The model is a scripted client and a scripted pydantic-ai
model, and git runs on a temporary repository, so no test reaches a network.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior

from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_FAILURE_MAX_CHARS,
    CONST_ROADMAP_REFINE_MAX_TRIES,
)
from devops_cli.roadmap.refine import (
    AcceptanceCriterion,
    JobCheck,
    NextStep,
    QuestionAnswer,
    RefinementProposal,
    RefinePlan,
    apply_refine,
    form_checks,
    plan_refine,
    refine_left_out,
    render_refine_plan,
)
from devops_cli.roadmap.store import ItemField, RefineRecordKey
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.scripted_model import Script, call

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
_CRITERION = AcceptanceCriterion(
    name="A design",
    requirement="The item SHALL have a design.",
    scenario="A person reads the item",
    when="a person reads the item",
    then="the design is in the item",
)
_WHOLE = RefinementProposal(
    existing_tool="No open tool covers the need.",
    problem_statement="The item needs a design.",
    acceptance_criteria=[_CRITERION],
)
_NO_CRITERION = _WHOLE.model_copy(update={"acceptance_criteria": []})
_OPEN_FACT = QuestionAnswer(question="Where is the sample function?", answer="?", kind="fact")
_UNSOURCED = _WHOLE.model_copy(update={"key_questions": [_OPEN_FACT]})
_SOURCED = _WHOLE.model_copy(
    update={
        "key_questions": [
            _OPEN_FACT.model_copy(
                update={"answer": "In src/sample.py.", "sources": ["src/sample.py:1"]}
            )
        ]
    }
)
_PERSON_QUESTION = QuestionAnswer(
    question="Which repository secret holds the key?", answer="A person picks it.", kind="person"
)
_PERSON_WAIT = _WHOLE.model_copy(update={"key_questions": [_PERSON_QUESTION]})
_PROPOSED_DECISION = QuestionAnswer(
    question="Which library parses it?", answer="Use the library.", kind="decision"
)


class _Client:
    """The proposal step's client: it answers each request from `proposals`, by the item's number,
    and counts the requests."""

    def __init__(self, proposals: dict[int, RefinementProposal]) -> None:
        self.proposals = proposals
        self.requests = 0

    def chat_structured(self, system: str, prompt: str, schema: type[Any], **_: Any) -> Any:
        self.requests += 1
        return self.proposals[json.loads(prompt)["number"]]


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
    (repo / "src" / "sample.py").write_text(
        "def hello_world():\n    return 'hello'\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    """A private roadmap, so no web search runs."""
    return InMemoryRoadmapStore(repo=REPO, is_private=True)


def _seed(store: InMemoryRoadmapStore, title: str = "Item") -> int:
    return store.seed_issue(
        title, body="Body", fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"}
    )


def _round(
    store: InMemoryRoadmapStore,
    git_repo: Path,
    proposals: dict[int, RefinementProposal],
    script: Script | None = None,
    *,
    client: _Client | None = None,
) -> RefinePlan:
    """One round of `devops roadmap refine --confirm`, planned and then applied."""
    plan = plan_refine(
        store,
        repo=REPO,
        source=git_repo,
        model=client or _Client(proposals),
        investigator=script.model() if script is not None else None,
    )
    apply_refine(store, plan)
    return plan


def _record(store: InMemoryRoadmapStore, number: int) -> dict[str, str | None]:
    """The refine keys of a job failure in the job record of issue `number`."""
    item = store.item(number)
    assert item is not None
    return {
        key.value: item.job_record.get(key)
        for key in (
            RefineRecordKey.NEXT_STEP,
            RefineRecordKey.TRIES,
            RefineRecordKey.FAILED_CHECK,
            RefineRecordKey.FAILURE,
        )
    }


def test_a_proposal_that_fails_a_form_check_makes_no_person_wait_and_counts_the_try(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    number = _seed(store)

    plan = _round(store, git_repo, {number: _NO_CRITERION})

    refined = plan.refined_items[0]
    assert (
        refined.next_step,
        store.comments_on(number),
        store.read_issue_body(number),
        _record(store, number),
    ) == (
        NextStep.RETRY,
        [],
        "Body",
        {
            "refine.next_step": "retry",
            "refine.tries": "1",
            "refine.failed_check": "acceptance_criteria",
            "refine.failure": "The reply of the model failed the form check.",
        },
    )


def test_a_later_round_tries_the_item_again_and_the_limit_ends_the_tries(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    number = _seed(store)
    client = _Client({number: _NO_CRITERION})

    steps = [
        (_round(store, git_repo, {}, client=client).refined_items[0].next_step, client.requests)
        for _ in range(CONST_ROADMAP_REFINE_MAX_TRIES)
    ]
    after_limit = _round(store, git_repo, {}, client=client)

    assert (steps, _record(store, number)["refine.tries"]) == (
        [(NextStep.RETRY, 1), (NextStep.RETRY, 2), (NextStep.FAILED, 3)],
        str(CONST_ROADMAP_REFINE_MAX_TRIES),
    )
    assert (
        client.requests,
        after_limit.refined_items,
        [(w.item.number, w.step) for w in after_limit.waiting_items],
        _record(store, number)["refine.next_step"],
    ) == (3, [], [(number, NextStep.FAILED)], "failed")


def test_a_body_edit_starts_the_count_of_tries_again(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    number = _seed(store)
    client = _Client({number: _NO_CRITERION})
    for _ in range(CONST_ROADMAP_REFINE_MAX_TRIES):
        _round(store, git_repo, {}, client=client)

    store.as_actor("alice").write_issue_body(number, "Body, edited")
    plan = _round(store, git_repo, {}, client=client)

    assert (plan.refined_items[0].next_step, _record(store, number)["refine.tries"]) == (
        NextStep.RETRY,
        "1",
    )


def test_a_whole_proposal_after_a_failed_try_clears_the_job_failure(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    number = _seed(store)
    proposals = {number: _NO_CRITERION}
    client = _Client(proposals)
    _round(store, git_repo, {}, client=client)

    proposals[number] = _WHOLE
    plan = _round(store, git_repo, {}, client=client)

    assert (plan.refined_items[0].next_step, _record(store, number)) == (
        NextStep.READY,
        {
            "refine.next_step": "ready",
            "refine.tries": None,
            "refine.failed_check": None,
            "refine.failure": None,
        },
    )


def test_a_proposal_that_needs_a_split_has_no_criterion_to_check() -> None:
    split = _NO_CRITERION.model_copy(update={"fits_one_pr": False, "split_offs": ["Part one."]})

    assert (form_checks(_NO_CRITERION), form_checks(split)) == (
        [JobCheck.ACCEPTANCE_CRITERIA],
        [],
    )


def test_a_question_that_a_read_tool_answers_does_not_stop_the_item(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    number = _seed(store)
    script = Script(call("read_file", path="src/sample.py"), _SOURCED)

    plan = _round(store, git_repo, {number: _UNSOURCED}, script)

    assert (plan.refined_items[0].next_step, _record(store, number)["refine.failed_check"]) == (
        NextStep.READY,
        None,
    )


def test_a_question_that_no_read_tool_answers_is_a_job_failure_that_lists_the_searches(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    number = _seed(store)
    script = Script(call("search_code", text="no_such_symbol"), _UNSOURCED)

    plan = _round(store, git_repo, {number: _UNSOURCED}, script)

    record = _record(store, number)
    assert (plan.refined_items[0].next_step, store.comments_on(number)) == (NextStep.RETRY, [])
    assert (record["refine.failed_check"], record["refine.failure"]) == (
        "missing_source",
        "Open: Where is the sample function? (missing verified source) "
        "Searched: search_code 'no_such_symbol'",
    )


def test_a_long_open_question_does_not_cut_the_searches_from_the_failure(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    number = _seed(store)
    long_fact = _OPEN_FACT.model_copy(update={"question": "Where is the sample function? " * 20})
    long_proposal = _WHOLE.model_copy(update={"key_questions": [long_fact]})
    script = Script(call("search_code", text="no_such_symbol"), long_proposal)

    _round(store, git_repo, {number: long_proposal}, script)

    failure = _record(store, number)["refine.failure"]
    assert failure is not None
    assert len(failure) <= CONST_ROADMAP_REFINE_FAILURE_MAX_CHARS
    assert failure.endswith("Searched: search_code 'no_such_symbol'")


def test_an_investigation_that_runs_out_of_output_retries_is_a_job_failure(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    number = _seed(store)
    script = Script(UnexpectedModelBehavior("Exceeded maximum output retries (2)"))

    plan = _round(store, git_repo, {number: _UNSOURCED}, script)

    record = _record(store, number)
    assert (plan.refined_items[0].next_step, store.comments_on(number), record) == (
        NextStep.RETRY,
        [],
        {
            "refine.next_step": "retry",
            "refine.tries": "1",
            "refine.failed_check": "investigation_stopped,missing_source",
            "refine.failure": "UnexpectedModelBehavior: Exceeded maximum output retries (2) "
            "Open: Where is the sample function? (missing verified source) Searched: nothing",
        },
    )


def test_a_stopped_investigation_with_nothing_else_open_keeps_the_first_proposal(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    number = _seed(store)
    proposed = _WHOLE.model_copy(update={"key_questions": [_PROPOSED_DECISION]})
    script = Script(UnexpectedModelBehavior("Exceeded maximum output retries (2)"))

    plan = _round(store, git_repo, {number: proposed}, script)

    assert (plan.refined_items[0].next_step, _record(store, number)["refine.failed_check"]) == (
        NextStep.READY,
        None,
    )


def test_a_question_marked_a_person_decides_still_makes_a_person_wait(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    number = _seed(store)

    plan = _round(store, git_repo, {number: _PERSON_WAIT})

    asked = store.comments_on(number)
    assert (plan.refined_items[0].next_step, len(asked), "(a person decides)" in asked[0].body) == (
        NextStep.PERSON,
        1,
        True,
    )


def test_a_job_failure_comes_before_a_question_for_a_person(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    number = _seed(store)
    both = _WHOLE.model_copy(update={"key_questions": [_OPEN_FACT, _PERSON_QUESTION]})

    plan = _round(store, git_repo, {number: both}, Script(both))

    assert (plan.refined_items[0].next_step, store.comments_on(number)) == (NextStep.RETRY, [])


def test_explain_says_what_a_failed_job_waits_for(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    number = _seed(store)
    client = _Client({number: _NO_CRITERION})
    _round(store, git_repo, {}, client=client)
    after_retry = refine_left_out(store, _item(store, number))
    for _ in range(CONST_ROADMAP_REFINE_MAX_TRIES - 1):
        _round(store, git_repo, {}, client=client)

    after_limit = refine_left_out(store, _item(store, number))

    assert after_retry is None
    assert after_limit is not None
    assert "A body edit makes refine try again." in after_limit
    assert "acceptance_criteria: 3 of 3 tries." in after_limit


def _item(store: InMemoryRoadmapStore, number: int) -> Any:
    item = store.item(number)
    assert item is not None
    return item


def test_the_report_counts_the_items_that_go_on_without_a_person(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    ready = _seed(store, "Ready item")
    asks = _seed(store, "Person item")
    retry = _seed(store, "Retry item")
    plan = plan_refine(
        store,
        repo=REPO,
        source=git_repo,
        model=_Client({ready: _WHOLE, asks: _PERSON_WAIT, retry: _NO_CRITERION}),
    )

    report = render_refine_plan(plan).splitlines()

    assert report[2:5] == [
        "## 2 item(s) go on without a person",
        f"- #{ready} Ready item",
        f"- #{retry} Retry item",
    ]
