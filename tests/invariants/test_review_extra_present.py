"""Invariant guard verifying the `lizard` review dependency is present in test environments (#6380)."""

from __future__ import annotations

import importlib.util
from importlib.machinery import ModuleSpec

import pytest


def _assert_review_extra_present() -> bool:
    """Assert `lizard` resolves cleanly; instruct `uv sync --all-extras` when missing."""
    assert importlib.util.find_spec("lizard") is not None, (
        "The `lizard` package required by `review_window` tests is missing from this Python "
        "environment; run `uv sync --all-extras` (or install the `dev` dependency group)."
    )
    return True


def test_review_extra_lizard_is_installed() -> None:
    """`lizard` is installed in the test environment so `review_window` contracts replay consistently."""
    assert _assert_review_extra_present()


def test_missing_review_extra_names_uv_sync_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replacing `importlib.util.find_spec` with `None` for `lizard` fails naming `uv sync --all-extras`."""
    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, package: str | None = None) -> ModuleSpec | None:
        if name == "lizard":
            return None
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    with pytest.raises(AssertionError, match=r"uv sync --all-extras"):
        _assert_review_extra_present()
