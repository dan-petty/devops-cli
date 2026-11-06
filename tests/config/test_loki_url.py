"""`loki.url` is a setting: a person sets it, a cluster scheme is refused, and a variable sets it.

Issue #2651: the fallback of `devops k8s logs` named a `loki.url` setting that did not exist.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.config.settings import load_settings


def _loki_url(config_path: Path) -> object:
    """The `loki.url` value that the active config file holds."""
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return (data.get("loki") or {}).get("url")


def test_config_set_writes_the_loki_url(
    cli: Callable[..., Any], isolate_devops_cli_config: Path
) -> None:
    """`devops config set loki.url http://example.com:3100` exits 0 and writes the setting."""
    result = cli("config", "set", "loki.url", "http://example.com:3100")

    assert (result.exit_code, _loki_url(isolate_devops_cli_config)) == (
        0,
        "http://example.com:3100",
    )
    assert load_settings().loki.url == "http://example.com:3100"


def test_config_set_refuses_a_cluster_scheme_and_names_the_key(
    cli: Callable[..., Any], isolate_devops_cli_config: Path
) -> None:
    """A `k8s://` value is refused with an error that names `loki.url`, and the file does not change."""
    before = isolate_devops_cli_config.read_text(encoding="utf-8")

    result = cli("config", "set", "loki.url", "k8s://logging/loki:3100")

    assert result.exit_code != 0
    assert "loki.url" in result.output
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == before


def test_the_variable_sets_the_address(monkeypatch: pytest.MonkeyPatch) -> None:
    """`DEVOPS_CLI_LOKI_URL` sets `loki.url` when the settings load."""
    monkeypatch.setenv("DEVOPS_CLI_LOKI_URL", "http://example.com:3100")

    assert load_settings().loki.url == "http://example.com:3100"
