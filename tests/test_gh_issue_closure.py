"""The closing-keyword parser: which issues a pull request body declares it closes."""

from __future__ import annotations

import pytest

from devops_cli.github.issue_closure import (
    LinkedIssue,
    extract_linked_issues,
    strip_non_prose,
)

REPO = "example/repository"


# =============================================================================
# Extracting Linked Issues
# =============================================================================


@pytest.mark.parametrize(
    "keyword",
    ["close", "closes", "closed", "fix", "fixes", "fixed", "resolve", "resolves", "resolved"],
)
def test_every_keyword_github_honours_is_recognised(keyword: str) -> None:
    """What this closes must be exactly what GitHub would have closed."""
    assert extract_linked_issues(f"{keyword} #317") == [LinkedIssue(number=317, keyword=keyword)]


def test_keyword_matching_is_case_insensitive() -> None:
    """Authors capitalise the start of a sentence."""
    assert extract_linked_issues("Closes #317")[0].number == 317


def test_a_colon_between_keyword_and_reference_is_accepted() -> None:
    """GitHub accepts `Closes: #317`."""
    assert extract_linked_issues("Closes: #317")[0].number == 317


def test_a_bare_reference_is_not_a_closing_link() -> None:
    """Mentioning an issue is not declaring that this closes it.

    Closing on a bare mention would shut issues merely referenced for context.
    """
    assert extract_linked_issues("Related to #317 and see #318") == []


def test_a_non_closing_verb_is_ignored() -> None:
    """Only GitHub's own keyword set counts."""
    assert extract_linked_issues("Addresses #317. Supersedes #318.") == []


def test_several_issues_are_all_extracted_and_ordered() -> None:
    """A pull request may close more than one issue."""
    body = "Closes #320\nFixes #317\nResolves #319"
    assert [issue.number for issue in extract_linked_issues(body)] == [317, 319, 320]


def test_a_repeated_reference_is_returned_once() -> None:
    """Restating a link must not attempt the close twice."""
    assert len(extract_linked_issues("Closes #317. Also closes #317.")) == 1


def test_a_fenced_code_block_is_not_scanned() -> None:
    """A body documenting the syntax must not be read as a live link.

    This project's own documentation shows `Closes #NNN` in examples; treating those as
    declarations would close whatever issue number the example happened to use.
    """
    body = "Explanation.\n\n```\nCloses #999\n```\n\nCloses #317"
    assert [issue.number for issue in extract_linked_issues(body)] == [317]


def test_inline_code_is_not_scanned() -> None:
    """The same reasoning applies to a backticked fragment."""
    assert extract_linked_issues("Write `Closes #999` in the body.") == []


def test_quoted_text_is_not_scanned() -> None:
    """A quoted review comment is someone else's text, not this author's declaration."""
    body = "> Closes #999\n\nI disagree, this closes nothing."
    assert extract_linked_issues(body) == []


def test_a_cross_repository_reference_is_ignored() -> None:
    """Closing the same-numbered issue in this repository would be wrong."""
    assert extract_linked_issues("Closes other/project#317", repo=REPO) == []


def test_a_reference_qualified_with_this_repository_is_honoured() -> None:
    """An explicitly qualified link to this repository is still a link to it."""
    assert extract_linked_issues(f"Closes {REPO}#317", repo=REPO)[0].number == 317


def test_an_empty_body_links_nothing() -> None:
    """A pull request with no body closes nothing."""
    assert (extract_linked_issues(""), extract_linked_issues("   ")) == ([], [])


def test_stripping_leaves_ordinary_prose_intact() -> None:
    """The scan must still see the text that matters."""
    assert "Closes #317" in strip_non_prose("Some prose.\n\nCloses #317\n")
