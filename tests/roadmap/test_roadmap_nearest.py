"""The nearest-item ranking that intake and the consolidation job share (#1127)."""

from __future__ import annotations

from devops_cli.config.defaults import DEFAULT_ROADMAP_INTAKE_TEXT_CHARS
from devops_cli.roadmap.nearest import embedding_text, nearest


def test_the_closest_vectors_come_first() -> None:
    candidates = [(1, [0.0, 1.0]), (2, [1.0, 0.1]), (3, [1.0, 1.0])]
    assert nearest([1.0, 0.0], candidates, 2) == [2, 3]


def test_keys_with_an_equal_score_keep_the_order_of_the_input() -> None:
    candidates = [(7, [1.0, 0.0]), (3, [2.0, 0.0]), (5, [0.0, 1.0])]
    assert nearest([1.0, 0.0], candidates, 3) == [7, 3, 5]


def test_a_limit_above_the_count_returns_every_key_and_none_returns_none() -> None:
    assert nearest([1.0], [(1, [1.0])], 5) == [1]
    assert nearest([1.0], [], 5) == []


def test_the_text_of_an_item_is_its_title_and_body_cut_at_the_limit() -> None:
    assert embedding_text("Title", "Body") == "Title\n\nBody"
    assert len(embedding_text("Title", "x" * 10 * DEFAULT_ROADMAP_INTAKE_TEXT_CHARS)) == (
        DEFAULT_ROADMAP_INTAKE_TEXT_CHARS
    )
