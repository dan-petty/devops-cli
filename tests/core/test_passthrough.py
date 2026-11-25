"""Tests for the tool pass-through registry and its ADR contract (#6597)."""

from __future__ import annotations

from devops_cli.core.command_resolver import resolve_devops_argv
from devops_cli.core.passthrough import (
    NEVER_WRAPPED,
    REGISTRY,
    PassthroughEntry,
    get_passthrough_entry,
)
from devops_cli.github.rate_limiter import run_gh


def test_gh_run_list_entry_fields_and_runner() -> None:
    """`REGISTRY['gh run list']` defines the complete pass-through contract using `run_gh`."""
    entry = REGISTRY["gh run list"]

    assert get_passthrough_entry("gh run list") is entry
    assert isinstance(entry, PassthroughEntry)
    assert "devops gh run list" in entry.devops_paths
    assert entry.runner is run_gh
    assert entry.mode == "read"
    assert entry.owned_options
    assert entry.refused_options


def test_never_wrapped_verbs_and_registry_exclusion() -> None:
    """`NEVER_WRAPPED` lists the five forbidden verbs and no entry uses any of them."""
    expected = {"pr merge", "auth", "secret set", "repo delete", "release"}
    assert NEVER_WRAPPED == expected

    for key in REGISTRY:
        normalized = key.removeprefix("gh ")
        for candidate in (key, normalized):
            assert not any(
                candidate == verb or candidate.startswith(f"{verb} ") for verb in NEVER_WRAPPED
            ), f"Registry key {key!r} matches never-wrapped verb"


def test_every_entry_devops_path_resolves_to_registered_command() -> None:
    """Every `devops_paths` command string in `REGISTRY` resolves in the CLI command tree."""
    for key, entry in REGISTRY.items():
        assert entry.devops_paths, f"{key!r} has empty devops_paths"
        for devops_path in entry.devops_paths:
            words = devops_path.split()
            assert words[0] == "devops"
            assert resolve_devops_argv(words[1:]) is None, (
                f"{key!r} devops path {devops_path!r} failed to resolve"
            )


def test_gh_run_list_cost_page_rule_and_timeout() -> None:
    """`gh run list` exposes positive run cost, `-L/--limit` page rule, and positive timeout."""
    entry = REGISTRY["gh run list"]

    assert entry.run_cost > 0
    assert entry.timeout > 0
    assert "-L" in entry.page_rule.flags
    assert "--limit" in entry.page_rule.flags
    assert entry.page_rule.default_limit > 0
    assert entry.page_rule.max_limit >= entry.page_rule.default_limit


def test_gh_run_list_mcp_allowlist_has_arity_caps_and_owned_subset() -> None:
    """Every option in `mcp_allowlist` defines `arity` and `cap` and belongs to `owned_options`."""
    entry = REGISTRY["gh run list"]

    assert entry.mcp_allowlist
    for option, rule in entry.mcp_allowlist.items():
        assert option in entry.owned_options
        assert rule.arity >= 0
        assert rule.cap is not None
        assert rule.cap > 0
