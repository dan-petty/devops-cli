"""The approval that a round of refine records for an item that a bot opened (#3502)."""

from __future__ import annotations

from devops_cli.roadmap.body_hash import body_hashes
from devops_cli.roadmap.stores.store import JudgeVerdict, RefineRecordKey
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore


def approval_of(body: str) -> dict[RefineRecordKey, str]:
    """The marks that a round writes when the review approves an item whose body is `body`: the
    verdict, and the hashes of the text that the review read."""
    body_hash, section_hash = body_hashes(body)
    marks = {
        RefineRecordKey.JUDGE: JudgeVerdict.APPROVED.value,
        RefineRecordKey.BODY_HASH: body_hash,
    }
    if section_hash is not None:
        marks[RefineRecordKey.SECTION_HASH] = section_hash
    return marks


def approve(store: InMemoryRoadmapStore, number: int) -> None:
    """Record the approval of the review for issue `number` as its body is now."""
    item = store.item(number)
    assert item is not None
    store.set_marks(item, dict(approval_of(item.body)))
