"""A synthetic release section as large as v0.2.25's, for the release notes size tests (#1097).

v0.2.25 collected 51 changelog fragments into a `[0.2.25]` section of 196,525 characters and 210
entries, past GitHub's 125,000-character Release body limit. This section has the same shape:
210 house-style entries across four categories, each a bold title over four sub-bullets.
"""

from __future__ import annotations

from collections.abc import Iterator

SYNTHETIC_ENTRY_COUNT = 210
_CATEGORY_SIZES = {"Added": 90, "Changed": 40, "Fixed": 70, "Security": 10}
SYNTHETIC_CATEGORIES = tuple(_CATEGORY_SIZES)
_DETAIL = (
    "The sub-bullet says what changed, why, and what a reader sees now, in the full sentences "
    "a fragment holds, with a file path (`src/devops_cli/x.py`), a measurement or two, a reason, and then the "
    "issue it closes "
)


def synthetic_entry_title(number: int) -> str:
    """The title line of entry `number`, unique among the section's titles."""
    return f"- **Entry {number:03d}: A Title as Long as the Real Ones (`devops x {number}`)**:"


def synthetic_entry_detail(number: int, line: int) -> str:
    """Sub-bullet `line` of entry `number`."""
    return f"  - {_DETAIL}(#{number}, line {line})."


def _category_blocks() -> Iterator[str]:
    numbers = iter(range(1, SYNTHETIC_ENTRY_COUNT + 1))
    for category, size in _CATEGORY_SIZES.items():
        entries = []
        for number in (next(numbers) for _ in range(size)):
            details = (synthetic_entry_detail(number, line) for line in range(1, 5))
            entries.append("\n".join((synthetic_entry_title(number), *details)))
        yield f"### {category}\n" + "\n".join(entries)


def synthetic_release_section() -> str:
    """The section's body, as `devops release notes` extracts it: over 200,000 characters."""
    return "\n\n".join(_category_blocks())
