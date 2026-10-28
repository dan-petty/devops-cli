"""Seeded draws repeat for the same seed and differ across seeds, with no `random` generator
(#1538)."""

from __future__ import annotations

from devops_cli.core.draws import seeded_choice, seeded_sample


def test_a_seeded_sample_repeats_for_the_same_seed() -> None:
    items = list(range(40))
    first = seeded_sample(items, 5, "42")
    assert (
        first == seeded_sample(items, 5, "42"),
        len(set(first)),
        set(first) <= set(items),
        first != seeded_sample(items, 5, "43"),
    ) == (True, 5, True, True)


def test_a_seeded_sample_takes_every_item_when_k_is_larger() -> None:
    assert sorted(seeded_sample(["a", "b", "c"], 10, "7")) == ["a", "b", "c"]


def test_a_seeded_choice_repeats_for_the_same_seed() -> None:
    items = [f"template-{n}" for n in range(12)]
    picks = {seeded_choice(items, f"7:file-{n}.py") for n in range(30)}
    assert (
        seeded_choice(items, "7:roles/client.py") == seeded_choice(items, "7:roles/client.py"),
        picks <= set(items),
        len(picks) > 1,
    ) == (True, True, True)
