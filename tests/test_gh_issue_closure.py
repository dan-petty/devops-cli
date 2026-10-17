"""The closing-keyword and part-reference parsers: which issues a pull request body declares it
closes, and which it delivers part of."""

from __future__ import annotations

import pytest

from devops_cli.github.issue_closure import (
    LinkedIssue,
    extract_linked_issues,
    extract_part_references,
    strip_non_prose,
)

REPO = "example/repository"

# Text a body may carry that declares nothing, each showing `{ref}`: code in every CommonMark form,
# raw HTML, which GitHub does not render, and a quote, which is someone else's text. Each follows
# a live reference after a blank line; an unclosed fence runs to the end of the body.
_NON_PROSE = {
    "backtick-fence": "```\n{ref}\n```",
    "tilde-fence": "~~~\n{ref}\n~~~",
    "unclosed-fence": "```\n{ref}",
    "indented-code": "    {ref}",
    "inline-code": "Write `{ref}` in the body.",
    "html-comment": "<!-- {ref} -->",
    "inline-html-comment": "Prose <!-- {ref} --> and more prose.",
    "quoted": "> {ref}\n\nI disagree.",
}
# A fence, an HTML comment and a quote end the paragraph above them with no blank line between.
_INTERRUPTING = {
    "tilde-fence": "~~~\n{ref}\n~~~",
    "html-comment": "<!-- {ref} -->",
    "quoted": "> {ref}",
}


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


@pytest.mark.parametrize("shown", _NON_PROSE.values(), ids=_NON_PROSE.keys())
def test_code_raw_html_and_quotes_are_not_scanned_for_closing_keywords(shown: str) -> None:
    """Only prose declares: a `~~~` fence, indented code, an unclosed fence or an HTML comment,
    as the pull request template's guidance is, closes nothing, as a backtick fence doesn't.

    `devops roadmap close` acts on what this returns, and closing an issue named only in a
    comment or a code block is not recoverable by the person who wrote the body.
    """
    body = f"Closes #317\n\n{shown.format(ref='Closes #999')}"
    assert [issue.number for issue in extract_linked_issues(body)] == [317]


@pytest.mark.parametrize("shown", _INTERRUPTING.values(), ids=_INTERRUPTING.keys())
def test_non_prose_right_below_a_closing_line_is_not_scanned(shown: str) -> None:
    """A comment or fence on the line after `Closes #317` is a block of its own, not prose."""
    body = f"Closes #317\n{shown.format(ref='Closes #999')}"
    assert [issue.number for issue in extract_linked_issues(body)] == [317]


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


def test_prose_in_a_list_or_a_heading_is_still_read() -> None:
    """Markdown structure around a declaration does not hide it."""
    body = "## Item\n\nCloses #317\n\n- Part of #318\n"
    assert (
        [issue.number for issue in extract_linked_issues(body)],
        extract_part_references(body),
    ) == ([317], [318])


# =============================================================================
# Extracting Part References
# =============================================================================


def test_a_part_reference_names_the_issue_a_pull_request_delivers_part_of() -> None:
    """An item planned as several pull requests names it with `Part of #N` until the last."""
    assert extract_part_references("Part of #317\n\nAdds the reader.") == [317]


@pytest.mark.parametrize("phrase", ["Part of", "part of", "PART OF", "Part  of", "Part of:"])
def test_the_part_phrase_is_matched_as_closing_keywords_are(phrase: str) -> None:
    """Case, spacing and an optional colon are read as GitHub reads `Closes #N`."""
    assert extract_part_references(f"{phrase} #317") == [317]


def test_a_numbered_part_line_is_not_a_part_reference() -> None:
    """Only the phrase counts: `Part 1 of #317` names a sequence, not the issue it delivers."""
    assert extract_part_references("Part 1 of #317") == []


@pytest.mark.parametrize("shown", _NON_PROSE.values(), ids=_NON_PROSE.keys())
def test_code_raw_html_and_quotes_are_not_scanned_for_part_references(shown: str) -> None:
    """A body documenting the phrase, in code or an HTML comment, or quoting someone else,
    declares nothing."""
    assert extract_part_references(f"Part of #317\n\n{shown.format(ref='Part of #999')}") == [317]


@pytest.mark.parametrize("shown", _INTERRUPTING.values(), ids=_INTERRUPTING.keys())
def test_non_prose_right_below_a_closing_line_names_no_part(shown: str) -> None:
    """`Closes #704` over `<!-- Part of #705 -->` closes #704 and delivers part of nothing, so
    readiness does not read it as naming both."""
    assert extract_part_references(f"Closes #704\n{shown.format(ref='Part of #705')}") == []


def test_a_part_reference_to_another_repository_is_ignored() -> None:
    """The same-numbered issue in this repository is not the one named."""
    assert extract_part_references("Part of other/project#317", repo=REPO) == []


def test_a_part_reference_qualified_with_this_repository_is_honoured() -> None:
    """An explicitly qualified reference to this repository still names its issue."""
    assert extract_part_references(f"Part of {REPO}#317", repo=REPO) == [317]


def test_several_part_references_are_all_extracted_once_and_ordered() -> None:
    """Readiness refuses more than one, so each is returned for it to name."""
    body = "Part of #320\nPart of #317\nAlso part of #320."
    assert extract_part_references(body) == [317, 320]


def test_part_references_and_closing_keywords_are_read_apart() -> None:
    """A part reference closes nothing, and a closing keyword is no part reference.

    `devops roadmap close` reads only closing keywords, so the item stays open until the pull
    request that closes it, its last, merges.
    """
    assert (
        extract_linked_issues("Part of #317"),
        extract_part_references("Closes #318"),
    ) == ([], [])


def test_an_empty_body_names_no_part() -> None:
    """A pull request with no body delivers part of nothing."""
    assert (extract_part_references(""), extract_part_references("   ")) == ([], [])
