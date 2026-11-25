"""The shared CommonMark parser of the roadmap (#6535).

A cached factory, `commonmark_parser`, gives each plain CommonMark reader the same
`MarkdownIt("commonmark")` instance, so reading a body or task group does not pay
the parser construction cost on each call.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType

from markdown_it import MarkdownIt

from devops_cli.roadmap.markdown import commonmark_parser
from devops_cli.roadmap.refine.refine import (
    body_dependencies,
    body_questions,
    title_dependencies,
)
from devops_cli.roadmap.stage.stage_criteria import acceptance_criteria, requirement_lines


@contextmanager
def parser_builds() -> Iterator[list[int]]:
    """Count each `MarkdownIt.__init__` invocation within the context."""
    found: list[int] = []
    init = MarkdownIt.__init__.__code__

    def profile(frame: FrameType, event: str, arg: object) -> None:
        if event == "return" and frame.f_code is init:
            found.append(1)

    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        yield found
    finally:
        sys.setprofile(previous)


def test_the_factory_returns_one_cached_parser() -> None:
    commonmark_parser.cache_clear()
    with parser_builds() as builds:
        p1 = commonmark_parser()
        p2 = commonmark_parser()

    assert p1 is p2
    assert len(builds) == 1


def test_every_plain_commonmark_construction_is_in_markdown_module() -> None:
    """Every reader that parses plain CommonMark uses commonmark_parser() and does not
    build its own MarkdownIt("commonmark")."""
    roadmap_dir = Path("src/devops_cli/roadmap")
    found: list[str] = []
    for path in sorted(roadmap_dir.rglob("*.py")):
        for line_num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if 'MarkdownIt("commonmark")' in line:
                if not any(token in line for token in (".use(", ".enable(", ".disable(")):
                    found.append(f"{path.as_posix()}:{line_num}")

    assert all(item.startswith("src/devops_cli/roadmap/markdown.py:") for item in found)
    assert len(found) == 1


def test_three_refine_reads_build_one_parser() -> None:
    commonmark_parser.cache_clear()
    body = """\
## Key questions

- [ ] Question 1?

## Dependencies

- #123
- "feat(repos): test title"
"""
    with parser_builds() as builds:
        q = body_questions(body)
        d = body_dependencies(body)
        t = title_dependencies(body, ())

    assert len(builds) == 1
    assert q == ["[ ] Question 1?"]
    assert d == [123]
    assert t.unmatched == ("feat(repos): test title",)


def test_stage_criteria_reads_build_one_parser() -> None:
    commonmark_parser.cache_clear()
    body = """\
### What should happen

- The stage job calls `devops pr ready` after the checks pass.

### Acceptance criteria

- An acceptance criterion.
"""
    with parser_builds() as builds:
        r = requirement_lines(body)
        a = acceptance_criteria(body)

    assert len(builds) == 1
    assert len(r) >= 1
    assert a == ["An acceptance criterion."]
