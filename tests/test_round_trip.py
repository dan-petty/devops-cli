"""Tests for round-trip YAML editing and key discovery (#2656)."""

from __future__ import annotations

import pytest

from devops_cli.config.round_trip import find
from devops_cli.exceptions import ConfigurationError

_MERGE_KEY_YAML = """\
a:
  b: &d
    api_key: secret
ai:
  <<: *d
"""


def test_find_merge_key_raises_configuration_error() -> None:
    """A key that comes from a YAML merge key has no source line in ruamel.yaml and raises
    ConfigurationError naming the file and the merge key."""
    with pytest.raises(ConfigurationError) as raised:
        find(_MERGE_KEY_YAML, "ai.api_key", name="config.yaml")

    assert (
        "config.yaml" in raised.value.message,
        "merge key" in raised.value.message,
        "'api_key'" in raised.value.message,
    ) == (True, True, True)
