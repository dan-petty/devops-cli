"""Tests for the modification-stamp cache in front of configuration loading."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from devops_cli.config import settings

_ALPHA = "ai:\n  model: alpha\n  ollama_urls:\n    - http://alpha:11434\n"
# Byte-for-byte the same length as _ALPHA, so rewriting one over the other leaves the
# file's size unchanged and only the loader's own bookkeeping can tell them apart.
_BRAVO = "ai:\n  model: bravo\n  ollama_urls:\n    - http://bravo:11434\n"


def _settled_config(tmp_path: Path, body: str, age_seconds: float = 60.0) -> Path:
    """Write a configuration file and backdate it past the cache's settling window."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(body, encoding="utf-8")
    stamp = time.time() - age_seconds
    os.utime(config_path, (stamp, stamp))
    return config_path


def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, config_path: Path) -> None:
    """Point both configuration layers at this test, leaving the project layer absent."""
    monkeypatch.setattr(settings, "CONFIG_PATH", config_path)
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(tmp_path / "no-project-config.yaml"))
    monkeypatch.chdir(tmp_path)
    settings.reset_settings_cache()


def _rewrite_keeping_stamp(config_path: Path, body: str) -> None:
    """Replace a file's contents while restoring the timestamp it had before the write."""
    before = config_path.stat()
    config_path.write_text(body, encoding="utf-8")
    os.utime(config_path, ns=(before.st_atime_ns, before.st_mtime_ns))


def test_unchanged_file_is_reused_and_a_real_edit_is_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _settled_config(tmp_path, _ALPHA)
    _isolate(monkeypatch, tmp_path, config_path)

    first = settings.load_settings()
    _rewrite_keeping_stamp(config_path, _BRAVO)
    cached = settings.load_settings()

    # An edit the stamp can see must reach the next load, or the cache would be a snapshot.
    _settled_config(tmp_path, _BRAVO, age_seconds=30.0)
    reloaded = settings.load_settings()

    assert (first.ai.model, cached.ai.model, reloaded.ai.model) == ("alpha", "alpha", "bravo")


def test_mutating_loaded_settings_does_not_poison_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _settled_config(tmp_path, _ALPHA)
    _isolate(monkeypatch, tmp_path, config_path)

    first = settings.load_settings()
    first.ai.model = "mutated"
    first.ai.ollama_urls.append("http://injected:11434")

    _rewrite_keeping_stamp(config_path, _BRAVO)
    second = settings.load_settings()

    assert (second.ai.model, second.ai.ollama_urls) == ("alpha", ["http://alpha:11434"])


def test_a_just_written_file_is_not_cached_until_it_settles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _settled_config(tmp_path, _ALPHA, age_seconds=0.0)
    _isolate(monkeypatch, tmp_path, config_path)

    settings.load_settings()
    while_hot = len(settings._CONFIG_CACHE)

    _settled_config(tmp_path, _ALPHA)
    settings.load_settings()
    once_settled = len(settings._CONFIG_CACHE)

    assert (while_hot, once_settled) == (0, 1)


def test_saving_settings_discards_the_parsed_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _settled_config(tmp_path, _ALPHA)
    _isolate(monkeypatch, tmp_path, config_path)

    loaded = settings.load_settings()
    before_save = len(settings._CONFIG_CACHE)
    settings.save_settings(loaded, target_path=tmp_path / "written.yaml")

    assert (before_save, len(settings._CONFIG_CACHE)) == (1, 0)
