"""A dry-run result bounds its details, so a large value cannot fill the memory or the screen."""

from __future__ import annotations

from devops_cli.dry_run import CommandDryRunResult


def _details(details: dict[str, object]) -> dict[str, object]:
    return CommandDryRunResult(command="test", details=details).details


def test_a_long_string_is_cut_to_1024_characters_and_ends_with_an_ellipsis() -> None:
    assert _details({"long": "x" * 2000}) == {"long": "x" * 1021 + "..."}


def test_a_long_list_keeps_its_first_50_items() -> None:
    assert _details({"items": list(range(100))}) == {"items": list(range(50))}


def test_a_value_nested_deeper_than_three_levels_is_truncated() -> None:
    deep = {"l1": {"l2": {"l3": {"l4": "too deep"}}}}

    assert _details(deep) == {"l1": {"l2": {"l3": "<truncated: depth exceeded>"}}}


def test_details_keep_their_first_100_keys() -> None:
    assert _details({f"k_{i}": i for i in range(200)}) == {f"k_{i}": i for i in range(100)}
