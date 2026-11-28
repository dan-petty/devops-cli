"""The setting `roadmap.brain.digest` (#4682): whether the alternatives check reads the brain
digest of an item before its model call, `off` or `on`, and `on` when it is not set.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.config.settings import Settings, load_settings


def test_the_digest_setting_is_on_when_it_is_not_set(config: Callable[..., Path]) -> None:
    config()

    assert load_settings().roadmap.brain.digest == "on"


def test_the_digest_setting_reads_its_variable(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    config()
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_BRAIN_DIGEST", "off")

    assert load_settings().roadmap.brain.digest == "off"


def test_a_digest_value_other_than_off_or_on_is_refused() -> None:
    with pytest.raises(ValidationError, match="digest"):
        Settings(roadmap={"brain": {"digest": "shadow"}})
