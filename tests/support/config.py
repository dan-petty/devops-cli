"""The shared config fixtures: `config` writes overrides into the per-test config.yaml (#1310), and
`global_config` writes the global config file under the run's own HOME."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest


def _deep_merge_config(base: dict[str, Any], updates: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge `updates` into a copy of `base`."""
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge_config(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


@pytest.fixture
def config(isolate_devops_cli_config: Path) -> Callable[..., Path]:
    """Write overrides into the per-test `config.yaml` and reset the settings cache (#1310)."""
    import yaml

    from devops_cli.config.settings import reset_settings_cache
    from devops_cli.telemetry.tracer import reset_tracer

    def apply(overrides: Mapping[str, Any] | None = None, **sections: Any) -> Path:
        current = yaml.safe_load(isolate_devops_cli_config.read_text(encoding="utf-8")) or {}
        combined: dict[str, Any] = {}
        if overrides:
            combined = _deep_merge_config(combined, overrides)
        if sections:
            combined = _deep_merge_config(combined, sections)
        updated = _deep_merge_config(current, combined)
        isolate_devops_cli_config.write_text(
            yaml.safe_dump(updated, sort_keys=False), encoding="utf-8"
        )
        reset_settings_cache()
        reset_tracer()
        return isolate_devops_cli_config

    return apply


@pytest.fixture
def global_config() -> Iterator[Callable[[dict[str, Any]], None]]:
    """Write the global config file, which the floor keeps under the run's own HOME, then remove it
    and each directory that the write made."""
    import yaml

    from devops_cli.config.constants import CONST_CONFIG_PATH
    from devops_cli.config.settings import reset_settings_cache
    from tests.support.home_write_guard import hold_to_the_run

    made = [
        d for d in (CONST_CONFIG_PATH.parent, *CONST_CONFIG_PATH.parent.parents) if not d.exists()
    ]

    def write(data: dict[str, Any]) -> None:
        hold_to_the_run(CONST_CONFIG_PATH)
        CONST_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONST_CONFIG_PATH.write_text(yaml.safe_dump(data), encoding="utf-8")
        reset_settings_cache()

    yield write
    CONST_CONFIG_PATH.unlink(missing_ok=True)
    for directory in made:
        if directory.exists():
            directory.rmdir()
    reset_settings_cache()
