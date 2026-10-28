"""Properties of the pinned GitHub host keys that `_ensure_known_host` writes to known_hosts (#2545)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from devops_cli.config.constants import CONST_GITHUB_KNOWN_HOSTS_LINES
from devops_cli.git.operations import _ensure_known_host, reset_known_host_cache

# Every character that `str.splitlines` takes as a line break, so a generated line is one line.
_LINE_BREAKS = "\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029"

other_lines = st.text(
    alphabet=st.characters(exclude_categories=("Cs",), exclude_characters=_LINE_BREAKS),
    max_size=40,
)
known_hosts_lines = st.lists(
    st.sampled_from(CONST_GITHUB_KNOWN_HOSTS_LINES) | other_lines, max_size=8
)


def _ensure(path: Path) -> str:
    """Run the check as a fresh process does, and return the file's text."""
    reset_known_host_cache()
    _ensure_known_host(path)
    return path.read_text(encoding="utf-8")


@given(existing=known_hosts_lines, ends_with_newline=st.booleans())
def test_the_pinned_keys_are_appended_once_after_every_existing_line(
    existing: list[str], ends_with_newline: bool
) -> None:
    """The file keeps each line it had, in order, and gains only the pinned lines it lacked,
    each once; a second run changes nothing."""
    content = "\n".join(existing) + ("\n" if existing and ends_with_newline else "")
    lines = content.splitlines()
    missing = [line for line in CONST_GITHUB_KNOWN_HOSTS_LINES if line not in lines]

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / ".ssh" / "known_hosts"
        path.parent.mkdir()
        path.write_text(content, encoding="utf-8")

        first = _ensure(path)
        second = _ensure(path)

    assert (first.splitlines(), second) == (lines + missing, first)
