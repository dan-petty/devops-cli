"""The GitHub identity every test runs under, and a fixture for a process with none (#1312).

The root conftest's `pin_github_session` gives every test `PINNED_GITHUB_TOKEN`, so no test runs
a real `gh auth token`. This module imports devops-cli at its top, so it must load after HOME is
isolated, as `bootstrap` registers it. `tests/test_isolation_tripwire.py` checks both sides: a
pytester project whose conftest names only `bootstrap` sees devops-cli's paths under the isolated
HOME, which loading this module first, through `pytest_plugins` or `-p`, breaks, and a test in
this suite's own run sees them there too.
"""

from __future__ import annotations

import pytest

from devops_cli.core import process
from devops_cli.lang import ERRORS

PINNED_GITHUB_TOKEN = "test-github-token"


def fail_the_github_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make `gh auth token` print no token from now on, as when gh has no login."""
    unauthenticated = ERRORS.git.github_unauthenticated.format(status=1)
    monkeypatch.setattr(process, "_github_token", None)
    monkeypatch.setattr(process, "_lookup_github_token", lambda: ("", unauthenticated))


@pytest.fixture
def no_github_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """The process has no GitHub identity: every lookup finds no token."""
    fail_the_github_lookup(monkeypatch)
