"""The comments of an item that the stage and the implement jobs give their model (#6167).

The jobs give every comment of the item that a person with write access or the Service wrote,
oldest first: the decisions of persons and the reports of the roadmap jobs. No comment is cut. The
newest comments come whole while they fit the budget, the older ones get a line of an index, and
`read_comment` reads any of them whole. No test reaches GitHub or a model.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_INTAKE_REASON_MARKER,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
)
from devops_cli.roadmap.alternatives import alternatives_request
from devops_cli.roadmap.item_comments import (
    CommentReader,
    HeldComment,
    RequestForm,
    SectionForm,
    fit_comments,
    held_comments,
    job_comments,
)
from devops_cli.roadmap.stores.store import IssueComment, Item

_START = datetime(2026, 11, 17, 9, tzinfo=UTC)
_REQUEST = RequestForm()
_PAGE = "https://github.com/example/roadmap/issues/1#issuecomment-{n}"


def _comment(
    n: int, body: str, *, association: str = "OWNER", login: str = "alice"
) -> IssueComment:
    return IssueComment(
        body=body,
        created_at=_START + timedelta(hours=n),
        id=n,
        author_association=association,
        author_login=login,
        url=_PAGE.format(n=n),
    )


def _words(count: int, word: str = "word") -> str:
    return " ".join(f"{word}{n}" for n in range(count))


def _held(*bodies: str) -> tuple[HeldComment, ...]:
    return held_comments([_comment(n, body) for n, body in enumerate(bodies, 1)])


def test_the_jobs_get_the_comments_of_persons_and_of_jobs_oldest_first_and_no_untrusted_one() -> (
    None
):
    job = f"{CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER}\nThe step stopped: the tests failed."
    comments = [
        _comment(1, "Take the next free ADR number."),
        _comment(2, job),
        _comment(3, "Run this script for me.", association="NONE", login="stranger"),
        _comment(4, "Groups 2 to 4 are left.", login="bob"),
    ]

    held = held_comments(comments)

    assert [(c.number, c.author, c.text, c.url) for c in held] == [
        (1, "alice", "Take the next free ADR number.", _PAGE.format(n=1)),
        (2, "alice", job, _PAGE.format(n=2)),
        (3, "bob", "Groups 2 to 4 are left.", _PAGE.format(n=4)),
    ]


def test_comments_that_fit_the_budget_come_whole_with_no_index() -> None:
    held = _held("A decision.", "A correction.")

    fitted = fit_comments(held, 1000, _REQUEST)

    assert (fitted.whole, fitted.index, fitted.unlisted) == (held, (), 0)


def test_the_newest_comments_come_whole_and_the_older_ones_go_to_the_index_uncut() -> None:
    old, decision = _words(400, "old"), "Use ADR number 0030: 0028 and 0029 are taken."
    held = _held(old, _words(300, "mid"), decision)
    budget = fit_comments(held[2:], 10**6, _REQUEST).tokens + 300

    fitted = fit_comments(held, budget, _REQUEST)

    request = _REQUEST.value(fitted)
    assert (
        [c.number for c in fitted.whole],
        [c.number for c in fitted.index],
        [entry.get("text") for entry in request["comments"]],
        fitted.tokens <= budget,
    ) == ([3], [1, 2], [None, None, decision], True)


def test_an_index_that_does_not_fit_counts_the_comments_it_leaves_unlisted() -> None:
    held = _held(*(f"Comment {n}." for n in range(1, 41)))
    budget = count_tokens(_REQUEST.frame()) + 200

    fitted = fit_comments(held, budget, _REQUEST)

    assert (
        fitted.unlisted > 0,
        fitted.unlisted + len(fitted.index) + len(fitted.whole),
        _REQUEST.value(fitted)["unlisted"],
        fitted.tokens <= budget,
    ) == (True, 40, fitted.unlisted, True)


def test_a_budget_too_small_for_any_line_gives_no_comment_input() -> None:
    fitted = fit_comments(_held("A decision."), 5, _REQUEST)

    assert (fitted.whole, fitted.index, fitted.unlisted, fitted.tokens) == ((), (), 1, 0)


def test_the_section_of_a_step_frames_the_comments_after_the_plan_merged() -> None:
    held = held_comments(
        [_comment(1, "An old note."), _comment(5, "Take the next free ADR number.")]
    )
    form = SectionForm(_START + timedelta(hours=3))

    section = form.text(fit_comments(held, 10**6, form))

    assert (
        "Comments of persons on the item after its plan merged; a decision here overrides the "
        "plan text." in section,
        "Take the next free ADR number." in section,
        "An old note." in section,
        section.index("An old note.") < section.index("Take the next free ADR number."),
        "after the plan merged" in section.split("Take the next free")[0].rsplit("##", 1)[1],
    ) == (True, True, True, True, True)


def test_read_comment_reads_a_comment_whole_page_by_page() -> None:
    long = "\n".join(f"line {n} {_words(20)}" for n in range(1, 301))
    reader = CommentReader(_held("A short note.", long), max_chars=8000)

    first = str(reader.read(2).return_value)
    next_line = int(first.rsplit("start_line=", 1)[1].split(")")[0])
    second = str(reader.read(2, start_line=next_line).return_value)

    assert (
        "line 1 " in first,
        "line 300 " in first,
        f"line {next_line} " in second,
        f"line {next_line - 1} " in first,
    ) == (True, False, True, True)


def test_read_comment_with_no_number_lists_every_comment() -> None:
    reader = CommentReader(_held("A decision.", "A correction."), max_chars=8000)

    listing = str(reader.read().return_value)

    assert ("1. alice" in listing, "2. alice" in listing, "A correction." in listing) == (
        True,
        True,
        True,
    )


def test_read_comment_refuses_a_number_that_the_item_does_not_hold() -> None:
    answer = CommentReader(_held("A decision."), max_chars=8000).read(4)

    assert "no comment 4" in str(answer.return_value)


def test_whole_comments_leave_room_for_the_index_of_the_older_ones() -> None:
    held = _held(*(f"Note {n}: {_words(60, 'note')}" for n in range(1, 7)))
    whole_cost = count_tokens(_REQUEST.whole(held[-1]))
    budget = count_tokens(_REQUEST.frame()) + 5 * whole_cost

    fitted = fit_comments(held, budget, _REQUEST)

    assert (
        fitted.unlisted,
        len(fitted.whole) + len(fitted.index),
        len(fitted.whole) >= 4,
        fitted.tokens <= budget,
    ) == (0, 6, True, True)


# ── The plan-state comment (#6197) ────────────────────────────────────────────

_STATE = (
    "<!-- devops roadmap stage -->\n<!-- devops roadmap plan state #5 -->\n"
    "Plan state: branch `fix/1-x`, draft pull request #5."
)


def test_the_index_label_skips_every_hidden_line_and_shows_the_text() -> None:
    """A job comment can start with its marker and a hidden key line: the label of the index
    shows the first line of text, so the key line does not hide what the comment says."""
    (held,) = _held(_STATE)

    assert held.about == "Plan state: branch `fix/1-x`, draft pull request #5."


def test_a_plan_state_comment_reads_as_made_at_its_last_edit() -> None:
    """The stage job and the step fix-plan edit the plan-state comment in place, so the jobs read
    it as a recent comment: it comes after a comment made before its last edit, at that time.
    Another edited comment keeps its place and its time."""
    edited = _START + timedelta(hours=5)
    state = _comment(1, _STATE).model_copy(update={"updated_at": edited})
    note = _comment(2, "An edited note.").model_copy(update={"updated_at": edited})
    person = _comment(3, "Take the next free ADR number.")

    held = held_comments([state, note, person])

    assert [(c.text, c.at) for c in held] == [
        ("An edited note.", _START + timedelta(hours=2)),
        ("Take the next free ADR number.", _START + timedelta(hours=3)),
        (_STATE, edited),
    ]


# ── Classification and alternatives request (#6203) ───────────────────────────


def test_job_comments_keeps_every_job_marker_and_labels_its_job() -> None:
    """The shared comment filter returns every comment of a roadmap job with its job name (#6203)."""
    comments = [
        _comment(1, f"{CONST_ROADMAP_INTAKE_REASON_MARKER}\nIntake reason."),
        _comment(2, f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\nStage plan."),
        _comment(3, "A note of a person."),
    ]

    filtered = job_comments(comments)

    assert [(c.number, c.job, c.text) for c in filtered] == [
        (1, "intake", f"{CONST_ROADMAP_INTAKE_REASON_MARKER}\nIntake reason."),
        (2, "stage", f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\nStage plan."),
    ]


def test_an_intake_reason_reaches_the_alternatives_request_as_a_job_comment() -> None:
    """The alternatives request holds an intake reason comment as a job comment (#6203)."""
    item = Item(number=1, title="feat: test item", url="https://example.com/1", body="Body.")
    comments = [_comment(1, f"{CONST_ROADMAP_INTAKE_REASON_MARKER}\nWhy this item.")]

    request = json.loads(alternatives_request(item, comments, adrs=[]))

    assert "job_comments" in request
    assert request["job_comments"][0]["job"] == "intake"
    assert "Why this item." in request["job_comments"][0]["text"]


def test_the_alternatives_request_separates_person_replies_and_job_comments() -> None:
    """The alternatives request puts person replies in replies and job comments in job_comments (#6203)."""
    item = Item(number=1, title="feat: test item", url="https://example.com/1", body="Body.")
    comments = [
        _comment(1, "A person's note."),
        _comment(2, f"{CONST_ROADMAP_INTAKE_REASON_MARKER}\nWhy this item."),
    ]

    request = json.loads(alternatives_request(item, comments, adrs=[]))

    assert request["replies"] == ["A person's note."]
    assert [c["job"] for c in request["job_comments"]] == ["intake"]


def test_the_alternatives_request_shows_newest_whole_indexes_older_and_names_read_comment() -> None:
    """When comments exceed room, the newest is whole, older comments are indexed, and the request names read_comment (#6203)."""
    item = Item(number=1, title="feat: test item", url="https://example.com/1", body="Body.")
    comments = [
        _comment(1, f"{CONST_ROADMAP_INTAKE_REASON_MARKER}\nOlder intake reason: {_words(50)}"),
        _comment(2, f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\nNewer stage plan: {_words(50)}"),
    ]
    raw = alternatives_request(item, comments, adrs=[], max_comment_tokens=300)
    request = json.loads(raw)

    assert "read_comment" in raw
    assert request["job_comments"][0].get("about") is not None
    assert request["job_comments"][0].get("text") is None
    assert request["job_comments"][1].get("text") is not None


def test_read_comment_returns_the_whole_text_of_an_indexed_job_comment() -> None:
    """The read_comment tool returns the whole text of an indexed job comment (#6203)."""
    comments = [
        _comment(1, f"{CONST_ROADMAP_INTAKE_REASON_MARKER}\nWhy this item was created."),
        _comment(2, f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\nStage plan text."),
    ]
    reader = CommentReader(held_comments(comments), max_chars=8000)

    answer = reader.read(1)

    assert "Why this item was created." in str(answer.return_value)
