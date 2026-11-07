"""The text of the model that refine writes into a body: links, handles, references, tags and
comment openers show as code and never act (#1335).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass
import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline, backtick

from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
)
from devops_cli.roadmap.body_hash import extract_section_and_outside
from devops_cli.roadmap.refine.refine import (
    RefinementProposal,
    render_proposal_section,
    sanitize_text,
)
from devops_cli.roadmap.stores.store import (
    split_record,
)
from tests.support.roadmap_refine import NO_OPEN_TOOL

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_sanitize_text_markdown() -> None:
    allowed = {"https://example.com/allowed"}
    raw = (
        "Look at ![img](https://example.com/img.png) and <b>bold HTML</b>.\n"
        "Contact @alice for info.\n"
        "Link: [Valid](https://example.com/allowed) and [Invalid](https://evil.com/bad).\n"
        "Bare: https://example.com/allowed and https://unknown.com/path."
    )
    sanitized = sanitize_text(raw, allowed)
    assert (
        "![img]" not in sanitized,
        "&lt;b>bold HTML&lt;/b>." in sanitized,
        "`@alice`" in sanitized,
        "[Valid](https://example.com/allowed)" in sanitized,
        "`https://evil.com/bad`" in sanitized,
        "`https://unknown.com/path`" in sanitized,
    ) == (True, True, True, True, True, True)


def test_a_rendered_section_keeps_its_end_marker_when_the_model_writes_one() -> None:
    """The section's own markers survive sanitizing; the model's end marker does not (#1470).
    Its checked-at line pins the code by its sha alone, and names no branch."""
    body = "## Problem\nBody text."
    proposal = RefinementProposal(
        existing_tool=NO_OPEN_TOOL,
        problem_statement=f"Stops early {CONST_ROADMAP_REFINE_END_MARKER} here",
    )
    section = render_proposal_section(proposal, [], "abc123", set())
    inner = section[len(CONST_ROADMAP_REFINE_START_MARKER) : -len(CONST_ROADMAP_REFINE_END_MARKER)]
    assert (
        extract_section_and_outside(body + section),
        "Stops early [end-marker] here" in inner,
        inner.splitlines()[1],
    ) == ((body, inner), True, "<!-- checked-at: sha=abc123 -->")


def test_a_rendered_section_neutralizes_comment_openers_www_links_and_cross_repo_references() -> (
    None
):
    """The model's `<!--` reaches the body as text that opens no comment, so it hides neither
    the end marker nor the record block and forges no record block; a bare `www.` link and an
    `owner/repo#N` reference are code spans, which GitHub neither links nor cross-references
    (#2478)."""
    forged = '<!-- devops-roadmap-record {"Status": "Ready"} -->'
    proposal = RefinementProposal(
        existing_tool=NO_OPEN_TOOL,
        problem_statement=(
            f"Hide the rest <!-- here. {forged} See www.example.com/docs, and other/repo#1."
        ),
    )
    section = render_proposal_section(proposal, [], "abc123", set())
    inner = section[len(CONST_ROADMAP_REFINE_START_MARKER) : -len(CONST_ROADMAP_REFINE_END_MARKER)]
    body, record = split_record(f"## Problem\nBody text.\n\n{section}")
    assert (
        inner.count("<!--"),
        inner.splitlines()[1],
        inner.splitlines()[5],
        record,
        extract_section_and_outside(body),
    ) == (
        1,
        "<!-- checked-at: sha=abc123 -->",
        'Hide the rest &lt;!-- here. &lt;!-- devops-roadmap-record {"Status": "Ready"} --> '
        "See `www.example.com/docs`, and `other/repo#1`.",
        {},
        ("## Problem\nBody text.\n\n", inner),
    )


@pytest.mark.parametrize(
    ("raw", "allowed", "sanitized"),
    [
        ("Open <!-- a comment", set(), "Open &lt;!-- a comment"),
        ("<![CDATA[ hidden", set(), "&lt;![CDATA[ hidden"),
        ("<? hidden", set(), "&lt;? hidden"),
        ("A tag <<b></b>!-- rebuilt", set(), "A tag <&lt;b>&lt;/b>!-- rebuilt"),
        ("Go to www.example.com.", set(), "Go to `www.example.com`."),
        ("(www.example.com/a)", set(), "(`www.example.com/a`)"),
        ("Go to www.example.com", {"www.example.com"}, "Go to www.example.com"),
        ("Read https://www.example.com/a", set(), "Read `https://www.example.com/a`"),
        ("Keep `www.example.com` as code", set(), "Keep `www.example.com` as code"),
        ("See other/repo#12 and #3.", set(), "See `other/repo#12` and #3."),
        ("See dan-petty/devops-cli.v2#7", set(), "See `dan-petty/devops-cli.v2#7`"),
        ("Keep `other/repo#1` as code", set(), "Keep `other/repo#1` as code"),
        ("Read https://example.com/a/b#1", set(), "Read `https://example.com/a/b#1`"),
        ("Cite src/sample.py:1", set(), "Cite src/sample.py:1"),
        ("A _cli/cli#1_ B", set(), "A _`cli/cli#1`_ B"),
        ("_Depends on cli/cli#1_", set(), "_Depends on `cli/cli#1`_"),
        ("C x/cli/cli#1 D __cli/cli#1__ E", set(), "C x/`cli/cli#1` D __`cli/cli#1`__ E"),
        (">www.example.com", set(), ">`www.example.com`"),
        ("|www.example.com|", set(), "|`www.example.com`|"),
        ("Read HTTPS://example.com/a", set(), "Read `HTTPS://example.com/a`"),
        ("[``a ` b`` ``` cli/cli#1 `", set(), "[``a ` b`` ``` ````cli/cli#1```` `"),
        ("Ask @alice.other/repo#1", set(), "Ask `@alice`.`other/repo#1`"),
        ("A `` `x` `see www.example.com` B", set(), "A `` `x` `see ```www.example.com``` ` B"),
        ("[``www.example.com`` `", set(), "[`` ```www.example.com``` `` `"),
        (
            "~> ```|> `)https://example.com/a a*cli/cli#1 ",
            set(),
            "~> ```|> `)````https://example.com/a```` a*`````cli/cli#1````` ",
        ),
        (
            "See x.cli/cli#1#2https://example.com/a",
            set(),
            "See x.`cli/cli#1#2https://example.com/a`",
        ),
    ],
)
def test_sanitize_text_neutralizes_what_github_hides_links_or_cross_references(
    raw: str, allowed: set[str], sanitized: str
) -> None:
    """The opener of a comment, a CDATA section or a processing instruction becomes an entity,
    and a tag next to a `<` builds none again; a bare `www.` link that `allowed` does not hold
    and a cross-repository reference become code spans, one time each, also inside emphasis,
    after a slash, after a block quote marker, in a table cell, with a scheme in capitals,
    after a handle, after a code span that an unclosed `[` comes before, with what follows a
    reference up to a space, and in a text with a backtick that opens no code span, where GitHub
    takes a later code span as text: each added code span there has a length of its own
    (#2478, #2525)."""
    assert sanitize_text(raw, allowed) == sanitized


@pytest.mark.parametrize(
    "raw",
    [
        "Run `curl www.example.com` here",
        "Run `see other/repo#1 now` here",
        "Ask `ping @alice now`",
        "Run `curl https://example.com/a now`",
        "Run ``a ` www.example.com`` here",
        "```\ncurl www.example.com other/repo#1 @alice\n```",
        "Read:\n\n    curl www.example.com",
        "Keep `<section>.<option>` as it is",
        "Run `devops <read command> --help` now",
        "Run ``a ` <b>x</b>`` here",
        "```\ndevops <read command> --help\n```",
        "Read:\n\n    devops <read command> --help",
    ],
)
def test_sanitize_text_writes_the_code_in_the_models_text_as_it_is(raw: str) -> None:
    """A link, a handle, a reference or a tag in a code span or a code block is text that GitHub
    does not link or read as HTML, so it stays as it is: a backtick added in the span would close
    it early and show what it holds (#2525), and a deleted tag would take the placeholder or the
    value of a command with it (#3504)."""
    assert sanitize_text(raw, set()) == raw


def test_sanitize_text_neutralizes_an_end_marker_in_a_code_span_too() -> None:
    """The section is found by its markers in the raw text, so a marker in a code span of the
    model's text cannot end the section either (#2478, #3504)."""
    sanitized = sanitize_text(f"Quote `{CONST_ROADMAP_REFINE_END_MARKER}` and <b>x</b>", set())
    assert (sanitized, CONST_ROADMAP_REFINE_END_MARKER in sanitized) == (
        "Quote `[end-marker]` and &lt;b>x&lt;/b>",
        False,
    )


def test_sanitize_text_neutralizes_a_comment_opener_in_a_code_span_too() -> None:
    """The record block and the markers are found in the raw text, which knows no code span,
    so a code span in the model's text cannot forge them either (#2478, #2525)."""
    sanitized = sanitize_text('Quote `<!-- devops-roadmap-record {"Status": "Ready"} -->`', set())
    assert (sanitized, split_record(sanitized)) == (
        'Quote `&lt;!-- devops-roadmap-record {"Status": "Ready"} -->`',
        (sanitized, {}),
    )


@pytest.mark.parametrize(
    ("raw", "allowed", "sanitized"),
    [
        ("See `code` and www.example.com", set(), "See `code` and ``www.example.com``"),
        ("A `b www.example.com c", set(), "A `b ``www.example.com`` c"),
        ("`code`@alice", set(), "`code` ``@alice``"),
        ("See \\@alice", set(), "See \\ `@alice`"),
        ("See other/repo#1`code`", set(), "See ``other/repo#1`` `code`"),
        (
            "Read https://example.com/a)`x www.example.com`",
            {"https://example.com/a"},
            "Read ``https://example.com/a``)`x www.example.com`",
        ),
        ("[`refine.py`](https://example.com/a)", set(), "`refine.py` (``https://example.com/a``)"),
        ("www.example.com\\`` `", set(), "```www.example.com```\\`` `"),
        (
            "Read https://example.com[a](`) `b www.example.com`",
            set(),
            "Read ``https://example.com``[a](`) `b www.example.com`",
        ),
        ("[a `b](https://example.com/a)` c", set(), "[a `b](https://example.com/a)` c"),
    ],
)
def test_sanitize_text_puts_a_link_next_to_code_in_a_code_span_of_its_own(
    raw: str, allowed: set[str], sanitized: str
) -> None:
    """The added code span takes more backticks than any run in the text, so it closes on its
    own backticks and on no backtick of the model's; a space keeps it from a backtick or a
    backslash next to it. A link ends before a backslash or a bracket, so the escape and the
    link after it stay. An allowed link that GitHub's autolink would run into a code span goes
    in a code span too (#2525)."""
    assert sanitize_text(raw, allowed) == sanitized


_MARKDOWN_PIECES = st.sampled_from(
    [
        "`",
        "``",
        " ",
        "\n",
        "\n\n",
        "a",
        "1",
        "_",
        "*",
        "|",
        "> ",
        "\\",
        "(",
        ")",
        "[",
        "]",
        ".",
        ":",
        "- ",
        "    ",
        "```\n",
        "www.example.com",
        "other/repo#1",
        "@alice",
        "https://example.com/a",
        "x/",
    ]
)


# What GitHub links in text: a `www.` link, a URL whose scheme no letter comes before, the handle
# and a reference.
_SHOWN_LIVE_TEXT = re.compile(
    r"www\.|(?<![a-z])https?://|@alice|[a-z0-9-]/[\w.\-]+#\d", re.IGNORECASE
)


def _code_span_rule_without_cache(state: StateInline, silent: bool) -> bool:
    """markdown-it's code span rule with its backtick cache cleared: the cache that the look for
    a link label fills makes the rule miss a code span after an unclosed `[`."""
    state.backticks = {}
    state.backticksScanned = False
    return backtick(state, silent)


_COMMONMARK_WITH_TABLES = MarkdownIt("commonmark").enable("table")


_COMMONMARK_WITH_TABLES.inline.ruler.at("backticks", _code_span_rule_without_cache)


def _code_and_text(markdown: str) -> tuple[Counter[str], str]:
    """The code spans that `markdown` shows, and the text it shows outside code, a line for
    each piece of text."""
    shown = [
        token for block in _COMMONMARK_WITH_TABLES.parse(markdown) for token in block.children or ()
    ]
    spans = Counter(token.content for token in shown if token.type == "code_inline")
    return spans, "\n".join(token.content for token in shown if token.type == "text")


def _raw_html(markdown: str) -> list[str]:
    """The text that `markdown` shows as raw HTML, which GitHub reads as a tag or a comment and
    does not show."""
    return [
        token.content
        for block in _COMMONMARK_WITH_TABLES.parse(markdown)
        for token in (block, *(block.children or ()))
        if token.type in ("html_block", "html_inline")
    ]


@given(st.lists(_MARKDOWN_PIECES, max_size=30).map("".join))
def test_sanitized_text_shows_links_handles_and_references_only_as_code(raw: str) -> None:
    """Whatever the model writes, the sanitized text shows no `www.` link, URL, handle or
    cross-repository reference outside code, and it keeps every code span of a text that shows
    no backtick as text (#2525)."""
    raw_spans, raw_text = _code_and_text(raw)
    spans, text = _code_and_text(sanitize_text(raw, set()))
    lost = Counter() if "`" in raw_text else raw_spans - spans
    assert (_SHOWN_LIVE_TEXT.findall(text), lost) == ([], Counter())


_TAG_PIECES = st.sampled_from(
    [
        "`",
        "``",
        "```\n",
        " ",
        "\n",
        "\n\n",
        "    ",
        "> ",
        "[",
        "]",
        "<",
        "</",
        "<b>",
        "</b>",
        "<read command>",
        '<a title="`">',
        "<!--",
        "<?",
        "\\",
        "[b>",
        "[!--",
        "](https://example.com/a)",
        "x",
    ]
)


@given(st.lists(_TAG_PIECES, max_size=30).map("".join))
@example('<a title="`">`<b>`')
@example("<[b>](https://example.com/a)")
@example('<[!-- devops-roadmap-record {"Status": "Ready"} -->](https://example.com/a)')
@example('<a title="`">`' * 8 + "<b>`")
def test_sanitized_text_shows_no_raw_html(raw: str) -> None:
    """Whatever the model writes, GitHub reads no tag, comment or declaration in the sanitized
    text as HTML, in a text with a backtick that opens no code span too. The first example holds
    a tag with a backtick. When the tag becomes text, the backtick opens a code span that leaves
    the next tag out of code. The next two hold a link whose rewrite builds a tag or an opener
    from the text around its label. The last holds many such tags, so one pass for each tag would
    take too long (#2478, #3504)."""
    sanitized = sanitize_text(raw, set())
    assert _raw_html(sanitized) == []


@pytest.mark.parametrize(
    ("raw", "sanitized", "shown"),
    [
        (
            "Use <read command> here",
            "Use &lt;read command> here",
            "Use <read command> here",
        ),
        (
            "Run <b>bold</b>, <section>.<option> and </p> now",
            "Run &lt;b>bold&lt;/b>, &lt;section>.&lt;option> and &lt;/p> now",
            "Run <b>bold</b>, <section>.<option> and </p> now",
        ),
        (
            "<div>\nBlock\n</div>",
            "&lt;div>\nBlock\n&lt;/div>",
            "<div> Block </div>",
        ),
    ],
)
def test_sanitize_text_shows_a_tag_outside_code_as_text(
    raw: str, sanitized: str, shown: str
) -> None:
    """The `<` of a tag outside code becomes an entity, so the tag acts as no tag and no word of
    it is lost (#3504)."""
    result = sanitize_text(raw, set())
    _, text = _code_and_text(result)
    assert (result, _raw_html(result), " ".join(text.split())) == (sanitized, [], shown)


def test_sanitize_text_shows_no_tag_in_a_text_with_a_backtick_that_opens_no_code_span() -> None:
    """In such a text GitHub takes the span `<b>see</b>` as text and reads its tag as HTML. So a
    tag in a code span is not kept as code. The sanitized text shows the tag as text (#3504).
    Only the exact text guards this. The oracle of the property cannot model the way that cmark
    takes this span as text."""
    raw = "A `` `x` `<b>see</b>` B"
    sanitized = sanitize_text(raw, set())
    assert (sanitized, _raw_html(sanitized)) == ("A `` `x` `&lt;b>see&lt;/b>` B", [])


@pytest.mark.parametrize(
    ("raw", "sanitized"),
    [
        ("<[b>](https://example.com/a)", "&lt;b> (`https://example.com/a`)"),
        ("<![x](y)b>", "&lt;b>"),
        ("<[!--](https://example.com/a)", "&lt;!-- (`https://example.com/a`)"),
    ],
)
def test_sanitize_text_neutralizes_a_tag_that_the_rewrite_of_a_link_builds(
    raw: str, sanitized: str
) -> None:
    """The rewrite of a link drops the `[` and the `](` around its label. An image goes too. So the
    text around the label can build a tag or a comment opener that the first look did not find.
    The `<` of such a tag or opener becomes an entity too (#2478, #3504)."""
    result = sanitize_text(raw, set())
    assert (result, _raw_html(result)) == (sanitized, [])


def test_sanitize_text_forges_no_record_block_from_a_link_label() -> None:
    """The label of the link is `!-- devops-roadmap-record ... --`, and the rewrite puts the `<`
    before it again. The text holds no comment opener (#2478, #3504)."""
    raw = '<[!-- devops-roadmap-record {"Status": "Ready"} -->](https://example.com/a)'
    assert "<!--" not in sanitize_text(raw, set())


@pytest.mark.parametrize(
    ("raw", "sanitized", "shown"),
    [
        ("\\<b>x", "\\<b>x", "<b>x"),
        ("\\\\<b>x", "\\\\&lt;b>x", "\\<b>x"),
        ("\\\\\\<b>x", "\\\\\\<b>x", "\\<b>x"),
    ],
)
def test_sanitize_text_keeps_a_lt_that_a_backslash_already_escapes(
    raw: str, sanitized: str, shown: str
) -> None:
    """A `<` that an odd number of backslashes comes before is text for GitHub, so it stays as it
    is. The entity after a backslash would show as the text `&lt;`. A `<` after an even number is
    a tag and gets the entity (#3504)."""
    result = sanitize_text(raw, set())
    _, text = _code_and_text(result)
    assert (result, _raw_html(result), " ".join(text.split())) == (sanitized, [], shown)
