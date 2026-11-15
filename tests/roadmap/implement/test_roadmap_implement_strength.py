"""The strength check of the implement job (#3051): the assertion scan of the new test files, the
bounded mutation run, and the coverage delta of the changed files.

The process edge is `process_fake`: it records the commands and answers them.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.implement_step import command_text

SCAN = "uv run ast-grep scan --rule .ast-grep/rules/test-function-has-assertion.yml --json"
MESSAGE = "Test function has no assert, no pytest.raises, and no assertion or double check."


def _match(path: str, line: int) -> dict[str, object]:
    """One match of the assertion rule, as `ast-grep scan --json` prints it, for the 1-based `line`
    of its function."""
    return {"file": path, "range": {"start": {"line": line - 1}}, "message": MESSAGE}


def test_a_new_test_file_that_asserts_nothing_is_flagged(
    implement_checkout: Path, implement_programs: ProcessFake
) -> None:
    from devops_cli.roadmap.implement.implement_strength import (
        AssertionFinding,
        assertion_failures,
    )

    sample = "tests/test_sample.py"
    (implement_checkout / sample).write_text(
        "def test_shout() -> None:\n    shout()\n", encoding="utf-8"
    )
    implement_programs.answer(
        lambda call: command_text(call).startswith(SCAN),
        ProcessAnswer(returncode=1, stdout=json.dumps([_match(sample, 1)])),
    )

    assert assertion_failures(implement_checkout, [sample]) == (
        AssertionFinding(sample, 1, MESSAGE),
    )
