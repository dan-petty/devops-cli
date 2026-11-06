"""The title of the pull request that the stage job opens (#2714): a plan has the type
`docs(openspec)`, so release-please lists no changelog line for it, and the branch keeps the type
of the issue."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from devops_cli.config.defaults import DEFAULT_ROADMAP_STAGE_PLANNED_LIMIT
from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.pull_form import title_problems
from devops_cli.roadmap.stage.stage import parse_filters, plan_stage, select_stageable
from devops_cli.roadmap.stage.stage_change import (
    SUMMARY_MAX_CHARS,
    StageProposal,
    delivery_title,
    staging_title,
)
from devops_cli.roadmap.stores.store import ItemField
from tests.support.builders import make_stage_proposal, stage_summary_limit
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

LONG_SUMMARY = "Report a clear error when a merge key is unset in the file"
# The label names that .github/labels.yml declares, as far as these tests need them.
DECLARED = ("scope/cli", "scope/config", "scope/openspec", "scope/roadmap")


# The largest number that the schema supports: the lead of the title is longest for it.
LARGEST_NUMBER = 999999


def _summary_of(title: str) -> str:
    """The part after `<type>(<scope>): `, which the check `Semantic PR title` measures."""
    return title.partition(": ")[2]


def _stage(store: InMemoryRoadmapStore):
    return select_stageable(
        store,
        filters=parse_filters(("status=ready",)),
        holder_of=lambda _issue, _branch: None,
        planned=PlannedChanges("main", {}, {}),
        limit=3,
        planned_limit=DEFAULT_ROADMAP_STAGE_PLANNED_LIMIT,
    )


def test_an_item_whose_title_summary_is_over_the_limit_is_left_out_with_both_counts() -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = store.seed_issue(
        f"fix(roadmap): {'a' * SUMMARY_MAX_CHARS}b",
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )

    selection = _stage(store)

    assert selection.selected == ()
    (left,) = selection.left_out
    assert left.number == number
    assert f"has {SUMMARY_MAX_CHARS + 1} characters" in left.reason
    assert f"limit is {SUMMARY_MAX_CHARS}" in left.reason


def test_an_item_whose_title_summary_is_exactly_the_limit_is_not_left_out_for_its_length() -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = store.seed_issue(
        f"fix(roadmap): {'a' * SUMMARY_MAX_CHARS}",
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )

    selection = _stage(store)

    assert [target.item.number for target in selection.selected] == [number]
    assert selection.left_out == ()


def test_a_title_with_no_type_keeps_its_reason_when_its_summary_is_over_the_limit() -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = store.seed_issue(
        f"the job drops a comment {'a' * SUMMARY_MAX_CHARS}",
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )

    (left,) = _stage(store).left_out

    assert left.number == number
    assert "Conventional Commit type" in left.reason
    assert "limit is" not in left.reason


def test_a_staging_title_has_the_type_docs_openspec_the_issue_and_the_summary() -> None:
    assert staging_title(2656, "Report a clear error") == (
        "docs(openspec): plan #2656 Report a clear error"
    )


@pytest.mark.parametrize("number", [7, 2656, LARGEST_NUMBER])
def test_a_staging_title_cuts_nothing_and_refuses_a_summary_that_does_not_fit(
    number: int,
) -> None:
    """A cut summary ends with `...`, which the form check refuses (#3249): the title is built
    whole or not at all."""
    assert len(LONG_SUMMARY) < SUMMARY_MAX_CHARS

    with pytest.raises(RoadmapStageError, match="characters after the colon") as raised:
        staging_title(number, LONG_SUMMARY + " as the user asked")

    assert raised.value.failed_items == (number,)


def test_the_guard_of_the_title_counts_units_so_a_number_with_seven_digits_refuses_emoji() -> None:
    """24 emoji are 24 characters and 48 units: with the lead of 14 the title has 62 units, and the
    guard is the only gate here, because the schema blocks the reply first for a smaller number."""
    with pytest.raises(RoadmapStageError, match="would have 62 characters after the colon"):
        staging_title(10**6, "\U0001f600" * 24)


@pytest.mark.parametrize("invisible", ["\u200b", "\ufeff", "\u2063", "\xad", "\u2800", "\u3164"])
def test_the_schema_refuses_a_summary_that_shows_nothing_to_a_reader(invisible: str) -> None:
    with pytest.raises(ValueError, match="The summary has no text"):
        make_stage_proposal(summary=invisible * 3)


def test_the_schema_message_tells_that_an_emoji_counts_as_two() -> None:
    with pytest.raises(ValueError, match="an emoji counts as two"):
        make_stage_proposal(summary="\U0001f600" * 24)


def test_a_number_with_more_digits_than_the_schema_supports_stops_the_item_and_cuts_nothing() -> (
    None
):
    """The schema accepts 47 characters, which is the room for 6 digits. A number of 7 digits
    leaves less, so the title fails loud instead of ending with `...`."""
    summary = "a" * stage_summary_limit()

    with pytest.raises(RoadmapStageError, match="characters after the colon") as raised:
        staging_title(10**6, summary)

    assert raised.value.failed_items == (10**6,)


@pytest.mark.parametrize("number", [1, 42, 999, 3249, 12345, LARGEST_NUMBER])
def test_a_summary_of_the_most_characters_that_the_schema_accepts_gives_a_title_the_form_accepts(
    number: int,
) -> None:
    """The job built a title that its own form check refused (#3249): the schema accepted 60
    characters, the lead of the title took some, and the cut summary ended with `...`."""
    summary = "a" * stage_summary_limit()

    title = staging_title(number, make_stage_proposal(summary=summary).summary)

    assert (title.endswith(summary), title_problems(title, DECLARED)) == (True, [])


def test_the_limit_of_the_schema_is_the_room_that_the_title_leaves_for_the_largest_number() -> None:
    lead = _summary_of(staging_title(LARGEST_NUMBER, ""))

    assert stage_summary_limit() == SUMMARY_MAX_CHARS - len(lead)
    assert len(_summary_of(staging_title(LARGEST_NUMBER, "a" * stage_summary_limit()))) == (
        SUMMARY_MAX_CHARS
    )


def test_the_constants_of_the_limit_name_the_largest_number_that_the_schema_supports() -> None:
    from devops_cli.roadmap.stage.stage_change import ISSUE_NUMBER_DIGITS, STAGE_SUMMARY_MAX_CHARS

    assert (10**ISSUE_NUMBER_DIGITS - 1, STAGE_SUMMARY_MAX_CHARS) == (
        LARGEST_NUMBER,
        stage_summary_limit(),
    )


def test_the_schema_refuses_a_summary_that_is_too_long_for_the_title_and_names_both_counts() -> (
    None
):
    limit = stage_summary_limit()

    with pytest.raises(ValueError, match=rf"{limit + 1} characters in the title.*limit is {limit}"):
        make_stage_proposal(summary="a" * (limit + 1))


def test_the_schema_refuses_a_summary_that_the_title_would_cut_after_the_handle_has_a_code_span() -> (
    None
):
    """A handle gets two backticks in the title, so a summary at the limit grows past the room."""
    limit = stage_summary_limit()
    summary = "a" * (limit - len("@maintainer") - 1) + " @maintainer"

    assert len(summary) == limit
    with pytest.raises(ValueError, match=rf"{limit + 2} characters in the title.*limit is {limit}"):
        make_stage_proposal(summary=summary)


@pytest.mark.parametrize(
    "spare",
    [
        lambda full: full + " ",
        lambda full: full + "\n",
        lambda full: "  " + full,
        lambda full: full[:20] + " " * 10 + full[21:],
        lambda full: full[:1] + "\t" * 12 + full[2:],
    ],
)
def test_the_schema_measures_the_summary_as_the_title_shows_it_so_spare_whitespace_costs_nothing(
    spare: Callable[[str], str],
) -> None:
    """The limit counts the one-line text of the title, so a trailing newline or a run of spaces
    that the title collapses does not make the model write the reply again."""
    limit = stage_summary_limit()
    summary = spare("a" * limit)

    proposal = make_stage_proposal(summary=summary)

    assert len(summary) > limit
    assert title_problems(staging_title(1, proposal.summary), DECLARED) == []


def _utf16_units(text: str) -> int:
    """The length that `^.{1,60}$` of the check `Semantic PR title` measures: JavaScript counts
    UTF-16 code units, and a character outside the Basic Multilingual Plane has two."""
    return len(text.encode("utf-16-le")) // 2


@pytest.mark.parametrize("symbol", ["\U0001f600", "\U00020000"], ids=["emoji", "astral-cjk"])
def test_the_limit_counts_a_character_outside_the_basic_plane_as_two_like_the_ci_check(
    symbol: str,
) -> None:
    """47 emoji are 47 characters for Python but 94 units for the CI check, which refuses the
    title (#3249). The limit counts units, so half as many fit, and the title passes both."""
    limit = stage_summary_limit()
    fits = symbol * (limit // 2)

    title = staging_title(LARGEST_NUMBER, make_stage_proposal(summary=fits).summary)

    assert _utf16_units(_summary_of(title)) <= SUMMARY_MAX_CHARS
    assert title_problems(title, DECLARED) == []
    with pytest.raises(ValueError, match=rf"{limit // 2 * 2 + 2} characters in the title"):
        make_stage_proposal(summary=symbol * (limit // 2 + 1))


@pytest.mark.parametrize("blank", [" ", "\n", "\t \xa0", "\u2028"])
def test_the_schema_refuses_a_summary_that_has_no_text_once_the_title_shows_it(
    blank: str,
) -> None:
    """The title of a blank summary is `plan #12 ` with nothing after the number."""
    with pytest.raises(ValueError, match="The summary has no text"):
        make_stage_proposal(summary=blank)


def test_the_json_schema_of_the_summary_holds_both_bounds_for_the_model() -> None:
    schema = StageProposal.model_json_schema()["properties"]["summary"]

    assert (schema["minLength"], schema["maxLength"]) == (1, stage_summary_limit())


def test_the_title_error_names_the_count_and_the_limit_for_a_number_that_is_too_large() -> None:
    summary = "a" * stage_summary_limit()

    with pytest.raises(
        RoadmapStageError,
        match=r"The title of item 1000000 would have 61 characters after the colon, "
        r"and the limit is 60\.",
    ):
        staging_title(10**6, summary)


def test_the_summary_error_tells_that_a_handle_or_a_link_gets_a_code_span() -> None:
    summary = "a" * (stage_summary_limit() - len("@maintainer") - 1) + " @maintainer"

    with pytest.raises(ValueError, match="A handle or a link gets a code span in the title"):
        make_stage_proposal(summary=summary)


def test_a_summary_with_a_handle_has_it_in_a_code_span_so_that_the_title_pings_no_one() -> None:
    assert staging_title(3, "Ask @maintainer about it") == (
        "docs(openspec): plan #3 Ask `@maintainer` about it"
    )


def test_a_staging_title_shows_a_word_in_angle_brackets_as_it_is() -> None:
    """A title is plain text: GitHub shows `<section>` as text and not as a tag, and the squash
    commit takes the title as it is. An entity would show as the text `&lt;` (#3504)."""
    assert staging_title(3, "Reject <section>.<option> keys") == (
        "docs(openspec): plan #3 Reject <section>.<option> keys"
    )


def test_the_delivery_title_shows_a_word_in_angle_brackets_as_it_is() -> None:
    assert delivery_title("fix(config): reject <section>.<option> keys", DECLARED) == (
        "fix(config): reject <section>.<option> keys"
    )


def test_a_title_still_turns_the_opener_of_a_comment_into_an_entity() -> None:
    """The text of an item stop puts the title in a comment, and the job finds the record block
    in the raw text of the comment (#2478, #3504)."""
    assert (
        staging_title(3, "Block <!-- hidden"),
        delivery_title("fix(config): block <!-- hidden", DECLARED),
    ) == ("docs(openspec): plan #3 Block &lt;!-- hidden", "fix(config): block &lt;!-- hidden")


def test_a_summary_with_words_in_angle_brackets_fits_as_the_check_counts_it() -> None:
    """The check `Semantic PR title` counts the characters of the title that GitHub shows, so a
    word in angle brackets costs its own length and not three more for an entity (#3504)."""
    summary = "a" * (stage_summary_limit() - len(" <b>")) + " <b>"

    title = staging_title(LARGEST_NUMBER, make_stage_proposal(summary=summary).summary)

    assert (title.endswith(summary), title_problems(title, DECLARED)) == (True, [])


@pytest.mark.parametrize(
    ("kind", "label", "branch_type"),
    [("bug", "type/bug", "fix"), ("feature", "type/feature", "feat")],
)
def test_the_staging_pull_request_of_a_bug_and_a_feature_has_the_docs_type_and_the_branch_type(
    kind: str,
    label: str,
    branch_type: str,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    stage_repo: StageRepo,
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = store.seed_issue(
        f"{branch_type}(roadmap): the job drops a comment",
        labels=(label,),
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    model_fake.answer(make_stage_proposal())
    openspec_fake.installed = False

    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(("status=ready", f"type={kind}")),
    )

    (change,) = plan.ready
    assert change.title == f"docs(openspec): plan #{number} Stop the job dropping a comment"
    assert change.target.branch.startswith(f"{branch_type}/{number}-")


def test_the_delivery_title_is_the_title_of_the_issue() -> None:
    assert delivery_title("fix(config): report a clear error", DECLARED) == (
        "fix(config): report a clear error"
    )


def test_the_delivery_title_keeps_the_type_and_the_scope_and_the_whole_summary() -> None:
    summary = "read the tree of the default branch once " * 3
    title = delivery_title("perf(roadmap): " + summary, DECLARED)

    assert title == f"perf(roadmap): {summary.strip()}"
    assert len(summary.strip()) > SUMMARY_MAX_CHARS
    assert not title.endswith("...")


def test_the_delivery_title_drops_the_mark_of_a_breaking_change() -> None:
    assert delivery_title("feat(cli)!: add a flag", DECLARED) == "feat(cli): add a flag"


def test_the_delivery_title_drops_a_scope_that_no_label_declares() -> None:
    """The `Semantic PR title` check refuses a scope that `.github/labels.yml` does not declare
    (#2800), so the delivery pull request keeps only a declared scope."""
    assert (
        delivery_title("fix(floor): report a clear error", DECLARED),
        delivery_title("fix(cli, floor): report a clear error", DECLARED),
        delivery_title("fix: report a clear error", DECLARED),
    ) == ("fix: report a clear error",) * 3
