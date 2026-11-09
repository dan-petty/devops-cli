"""Each key of the implement job record has a reader (#4070, #4071).

A key that the job only writes is dead weight, unless a person reads it or the spec requires it. So
each member of `ImplementRecordKey` is named below with the place that reads it: a read in the code
of `src/devops_cli`, a line of the spec `roadmap-implement-job`, or a line of
`docs/ROADMAP_WORKFLOW.md`, which a person reads. A key that nothing reads is removed, and a new
key needs a line here.
"""

from __future__ import annotations

import re
from typing import Final

import pytest

from devops_cli.roadmap.stores.store import ImplementRecordKey
from tests.support.paths import REPO_ROOT

SPEC = "openspec/specs/roadmap-implement-job/spec.md"
DOCUMENT = "docs/ROADMAP_WORKFLOW.md"
ROADMAP = "src/devops_cli/roadmap"

# The key, then where it is read: ("code", file) or ("text", file, a text that the file holds).
READERS: Final[dict[str, tuple[str, ...]]] = {
    "implement.group": ("text", SPEC, "`implement.group` (the last group that passed)"),
    "implement.sha": ("text", SPEC, "`implement.sha` (the commit it ended on)"),
    "implement.branch": (
        "text",
        f"{ROADMAP}/implement/implement.py",
        "(ImplementRecordKey.BRANCH, ImplementRecordKey.PR)",
    ),
    "implement.pr": ("code", f"{ROADMAP}/implement/implement_pull.py"),
    "implement.stopped": ("code", f"{ROADMAP}/status_sync.py"),
    "implement.result": ("code", f"{ROADMAP}/implement/implement_submit.py"),
    "implement.failure": ("code", f"{ROADMAP}/stop_clear.py"),
    "implement.check": ("text", DOCUMENT, "The check that failed in the stop"),
    "implement.check_log": ("code", f"{ROADMAP}/implement/implement_run.py"),
    "implement.conflict": ("code", f"{ROADMAP}/implement/implement_run.py"),
    "implement.wip": ("text", SPEC, "The job SHALL write `implement.wip` to the job record"),
    "implement.base": ("code", f"{ROADMAP}/implement/implement_run.py"),
    "implement.checked_sha": ("code", f"{ROADMAP}/implement/implement_run.py"),
    "implement.published_sha": ("code", f"{ROADMAP}/implement/implement_run.py"),
    "implement.spend": ("code", f"{ROADMAP}/implement/implement_submit.py"),
    "implement.trace": ("code", f"{ROADMAP}/explain.py"),
    "implement.job": ("code", f"{ROADMAP}/status_sync.py"),
    "implement.job_state": ("code", f"{ROADMAP}/status_sync.py"),
    "implement.job_digest": ("code", f"{ROADMAP}/stop_clear.py"),
    "implement.digest_clears": ("code", f"{ROADMAP}/digest_clears.py"),
    "implement.digest_clear_commented_at": ("code", f"{ROADMAP}/digest_clears.py"),
    "implement.continuations": ("code", f"{ROADMAP}/stop_clear.py"),
    "implement.repair_rounds": ("code", f"{ROADMAP}/implement/implement_submit.py"),
}


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _reads(source: str, key: str) -> bool:
    """Whether `source` reads the member of `key`: `record.get(Key)` or `_record(item, Key)`."""
    name = key.partition(".")[2].upper()
    return (
        re.search(rf"(?:get\(|_record\([\w.]+, *)ImplementRecordKey\.{name}\b", source) is not None
    )


def test_each_key_of_the_implement_record_has_a_reader_in_the_table() -> None:
    assert {key.value for key in ImplementRecordKey} == set(READERS)


@pytest.mark.parametrize("key", sorted(READERS))
def test_the_reader_of_a_key_reads_it(key: str) -> None:
    kind, path, *text = READERS[key]
    source = _read(path)
    if kind == "code":
        assert _reads(source, key), f"{path} does not read {key}"
    else:
        assert text[0] in source, f"{path} does not hold the text for {key}"


def test_a_key_with_neither_a_reader_nor_a_spec_line_is_found() -> None:
    """The table is checked against the members of the enum: a member that the table lacks, and a
    line of the table that names no member, both make the first test fail."""
    members = {key.value for key in ImplementRecordKey} | {"implement.unread"}

    assert members - set(READERS) == {"implement.unread"}


def test_the_document_names_the_result_key_and_the_hand_off_of_the_stop() -> None:
    rows = [line for line in _read(DOCUMENT).splitlines() if line.startswith("| Implement |")]

    assert any("`implement.result`" in row for row in rows)
    for key in ("`implement.check_log`", "`implement.conflict`"):
        (row,) = [row for row in rows if key in row]
        assert "first step" in row, f"the row of {key} does not state the hand-off"
