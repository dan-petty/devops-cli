"""The record of the digest clears of an item (#3481): a list of the class, the digest and the time
of each clear, the time of the last clear comment, and the two settings that bound the clears."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.config import settings
from devops_cli.roadmap.digest_clears import (
    DigestClear,
    encode_clears,
    has_digest_clear,
    last_clear_comment,
    recorded_clears,
)
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import ImplementRecordKey, Item, ItemField
from tests.support.roadmap_stage import STAGE_REPO

NOON = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


def _item(store: InMemoryRoadmapStore, **marks: str | None) -> Item:
    number = store.seed_issue("fix(cli): one", fields={ItemField.PRIORITY: "P2-Medium"})
    item = store.item(number)
    assert item is not None
    store.set_marks(
        item, {ImplementRecordKey(key.replace("_", ".", 1)): v for key, v in marks.items()}
    )
    again = store.item(number)
    assert again is not None
    return again


def test_the_clears_of_an_item_survive_a_write_and_a_read(store: InMemoryRoadmapStore) -> None:
    clears = (
        DigestClear(failure_class=FailureClass.PROVIDER, digest="sha256:" + "a" * 64, time=NOON),
        DigestClear(failure_class=FailureClass.CI_INFRA, digest="sha256:" + "b" * 64, time=NOON),
    )

    item = _item(store, implement_digest_clears=encode_clears(clears))

    assert (recorded_clears(item), has_digest_clear(item)) == (clears, True)


def test_the_record_names_the_class_under_the_key_class(store: InMemoryRoadmapStore) -> None:
    text = encode_clears((DigestClear(failure_class=FailureClass.TIMEOUT, digest="d", time=NOON),))

    assert '"class":"timeout"' in text


def test_an_item_with_no_record_has_no_clears_and_no_comment_time(
    store: InMemoryRoadmapStore,
) -> None:
    item = _item(store)

    assert (recorded_clears(item), has_digest_clear(item), last_clear_comment(item)) == (
        (),
        False,
        None,
    )


@pytest.mark.parametrize(
    "text",
    ["not json", '{"class": "provider"}', '[{"class": "nonsense", "digest": "d", "time": "x"}]'],
)
def test_a_record_that_is_not_a_valid_list_raises_and_still_counts_as_an_attempt(
    store: InMemoryRoadmapStore, text: str
) -> None:
    item = _item(store, implement_digest_clears=text)

    with pytest.raises(ValidationError, match="validation error"):
        recorded_clears(item)
    assert has_digest_clear(item) is True


def test_the_comment_time_is_read_and_a_bad_time_raises(store: InMemoryRoadmapStore) -> None:
    good = _item(store, implement_digest_clear_commented_at=NOON.isoformat())
    bad = _item(store, implement_digest_clear_commented_at="yesterday")

    assert last_clear_comment(good) == NOON
    with pytest.raises(ValidationError, match="validation error"):
        last_clear_comment(bad)


def test_the_limits_default_to_one_for_a_class_and_three_for_an_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(settings, "CONFIG_PATH", path)
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(tmp_path / "no-project-config.yaml"))
    for name in ("PER_CLASS", "PER_ITEM"):
        monkeypatch.delenv(f"DEVOPS_CLI_ROADMAP_IMPLEMENT_DIGEST_CLEARS_{name}", raising=False)
    settings.reset_settings_cache()

    implement = settings.load_settings().roadmap.implement

    assert (implement.digest_clears_per_class, implement.digest_clears_per_item) == (1, 3)


def test_the_limits_come_from_the_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(settings, "CONFIG_PATH", path)
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(tmp_path / "no-project-config.yaml"))
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_IMPLEMENT_DIGEST_CLEARS_PER_CLASS", "2")
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_IMPLEMENT_DIGEST_CLEARS_PER_ITEM", "5")
    settings.reset_settings_cache()

    implement = settings.load_settings().roadmap.implement

    assert (implement.digest_clears_per_class, implement.digest_clears_per_item) == (2, 5)
