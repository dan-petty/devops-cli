"""Pull request template invariants: what .github/pull_request_template.md holds."""

from __future__ import annotations

import re

from tests.support.paths import REPO_ROOT

_PR_TEMPLATE = REPO_ROOT / ".github" / "pull_request_template.md"


_HEADING_OR_RULE_LINE = re.compile(r"^\s*(?:#{1,6}\s|(?:-\s*){3,}$|(?:\*\s*){3,}$|(?:_\s*){3,}$)")


def test_pr_template_reads_as_the_squash_commit_message() -> None:
    """The squash merge copies the body into `main` as the commit message (#2266).

    The repository squash-merges with `PR_TITLE` and `PR_BODY`. Of the last 60 merges, 49
    messages held the template's `## Summary` and `## Item` headings, and the `Change:` line
    named a folder that the archive had moved. The template has no heading and no rule, and
    names the archived change folder.
    """
    text = _PR_TEMPLATE.read_text(encoding="utf-8")
    assert [line for line in text.splitlines() if _HEADING_OR_RULE_LINE.match(line)] == []
