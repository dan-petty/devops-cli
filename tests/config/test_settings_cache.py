"""Tests for the modification-stamp cache in front of configuration loading."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config import settings
from devops_cli.config.constants import CONST_CONFIG_PATH

_ALPHA = "ai:\n  model: alpha\n  ollama_urls:\n    - http://alpha:11434\n"
# Byte-for-byte the same length as _ALPHA, so rewriting one over the other leaves the
# file's size unchanged and only the loader's own bookkeeping can tell them apart.
_BRAVO = "ai:\n  model: bravo\n  ollama_urls:\n    - http://bravo:11434\n"


def _settled_config(config_path: Path, body: str, age_seconds: float = 60.0) -> Path:
    """Write a configuration file and backdate it past the cache's settling window."""
    config_path.write_text(body, encoding="utf-8")
    stamp = time.time() - age_seconds
    os.utime(config_path, (stamp, stamp))
    return config_path


@pytest.fixture(params=["global", "project"])
def config_file(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    isolate_devops_cli_config: Path,
    global_config: Callable[[dict[str, Any]], None],
) -> Path:
    """The one configuration file of a test, as the global file or as the project file that
    `DEVOPS_CLI_CONFIG` names; the other layer is absent."""
    if request.param == "project":
        return isolate_devops_cli_config
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(tmp_path / "no-project-config.yaml"))
    monkeypatch.chdir(tmp_path)
    global_config({})
    return CONST_CONFIG_PATH


def _rewrite_keeping_stamp(config_path: Path, body: str) -> None:
    """Replace a file's contents while restoring the timestamp it had before the write."""
    before = config_path.stat()
    config_path.write_text(body, encoding="utf-8")
    os.utime(config_path, ns=(before.st_atime_ns, before.st_mtime_ns))


def test_unchanged_file_is_reused_and_a_real_edit_is_not(config_file: Path) -> None:
    _settled_config(config_file, _ALPHA)
    settings.reset_settings_cache()

    first = settings.load_settings()
    _rewrite_keeping_stamp(config_file, _BRAVO)
    cached = settings.load_settings()

    # An edit the stamp can see must reach the next load, or the cache would be a snapshot.
    _settled_config(config_file, _BRAVO, age_seconds=30.0)
    reloaded = settings.load_settings()

    assert (first.ai.model, cached.ai.model, reloaded.ai.model) == ("alpha", "alpha", "bravo")


def test_mutating_loaded_settings_does_not_poison_the_cache(config_file: Path) -> None:
    _settled_config(config_file, _ALPHA)
    settings.reset_settings_cache()

    first = settings.load_settings()
    first.ai.model = "mutated"
    first.ai.ollama_urls.append("http://injected:11434")

    _rewrite_keeping_stamp(config_file, _BRAVO)
    second = settings.load_settings()

    assert (second.ai.model, second.ai.ollama_urls) == ("alpha", ["http://alpha:11434"])


def test_a_just_written_file_is_not_cached_until_it_settles(config_file: Path) -> None:
    _settled_config(config_file, _ALPHA, age_seconds=0.0)
    settings.reset_settings_cache()

    settings.load_settings()
    _rewrite_keeping_stamp(config_file, _BRAVO)
    while_hot = settings.load_settings().ai.model

    _settled_config(config_file, _ALPHA)
    settings.load_settings()
    _rewrite_keeping_stamp(config_file, _BRAVO)
    once_settled = settings.load_settings().ai.model

    assert (while_hot, once_settled) == ("bravo", "alpha")


def test_saving_settings_discards_the_parsed_copy(config_file: Path, tmp_path: Path) -> None:
    _settled_config(config_file, _ALPHA)
    settings.reset_settings_cache()

    loaded = settings.load_settings()
    _rewrite_keeping_stamp(config_file, _BRAVO)
    before_save = settings.load_settings().ai.model
    settings.save_settings(loaded, target_path=tmp_path / "written.yaml")
    after_save = settings.load_settings().ai.model

    assert (before_save, after_save) == ("alpha", "bravo")


def test_a_merge_with_the_project_layer_is_not_reused_while_a_review_runs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    global_config: Callable[[dict[str, Any]], None],
) -> None:
    """A review reads no project config it was not told to (#972), so the merge cached from the
    same working directory before it began, project layer included, must not answer inside it;
    nor the merge without the layer once it ends."""
    from devops_cli.core.untrusted_trees import reading_untrusted_trees

    global_config({})
    _settled_config(CONST_CONFIG_PATH, _ALPHA)
    project = tmp_path / "project"
    (project / ".devops").mkdir(parents=True)
    _settled_config(project / ".devops" / "config.yaml", _BRAVO)
    monkeypatch.delenv("DEVOPS_CLI_CONFIG", raising=False)
    monkeypatch.chdir(project)
    settings.reset_settings_cache()

    before = settings.load_settings().ai.model
    with reading_untrusted_trees():
        during = settings.load_settings().ai.model
    after = settings.load_settings().ai.model

    assert (before, during, after) == ("bravo", "alpha", "bravo")
