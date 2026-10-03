"""The cadence sections of `docs/ROUTINE_TASKS.md`, which task files cite by letter (#956)."""

from __future__ import annotations

import re
from pathlib import Path
from string import ascii_uppercase

ROUTINE_TASKS = Path(__file__).resolve().parents[1] / "docs" / "ROUTINE_TASKS.md"


def test_each_cadence_letter_names_one_section_in_order() -> None:
    """Task files cite "Cadence B / Feature PR Lifecycle" and "Cadence C Step 8", so a letter must
    name one section. The final pre-commit stage was a second "Cadence B" (#956)."""
    letters = re.findall(
        r"^### Cadence ([A-Z]):", ROUTINE_TASKS.read_text(encoding="utf-8"), re.MULTILINE
    )

    assert letters == list(ascii_uppercase[: len(letters)])
