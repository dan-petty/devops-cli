"""Unit tests for review path classification and config loading (#1047)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.analyze.symbols import BaseRevision
from devops_cli.ai.review.path_classes import (
    _matches_any_pattern,
    _parse_toml_classes,
    _read_config_content,
    classify_path,
    is_fixture_path,
    load_path_classes,
)
from devops_cli.config.constants import CONST_DEFAULT_PATH_CLASSES


def test_read_config_content_from_base_revision() -> None:
    """_read_config_content reads review.toml from BaseRevision reader."""
    base_rev = BaseRevision(
        changes=(),
        read=lambda path: '[paths]\nsrc = ["src/*"]\n' if path == ".devops/review.toml" else None,
    )
    content = _read_config_content(base_rev, repo_root=None)
    assert content == '[paths]\nsrc = ["src/*"]\n'


def test_read_config_content_from_repo_root(tmp_path: Path) -> None:
    """_read_config_content falls back to disk repo_root."""
    devops_dir = tmp_path / ".devops"
    devops_dir.mkdir()
    cfg = devops_dir / "review.toml"
    cfg.write_text('[paths]\ntest = ["tests/*"]\n', encoding="utf-8")

    content = _read_config_content(None, repo_root=tmp_path)
    assert content == '[paths]\ntest = ["tests/*"]\n'


def test_read_config_content_none(tmp_path: Path) -> None:
    """_read_config_content returns None when config file does not exist."""
    assert _read_config_content(None, repo_root=tmp_path) is None


def test_parse_toml_classes_invalid_syntax() -> None:
    """Invalid TOML content falls back to default path classes."""
    classes = _parse_toml_classes("invalid toml [ syntax")
    assert classes == dict(CONST_DEFAULT_PATH_CLASSES)


def test_parse_toml_classes_custom_classes() -> None:
    """Custom path classes in TOML override defaults."""
    content = """
    [paths]
    src = ["core/**"]
    fixture = ["data/**"]
    """
    classes = _parse_toml_classes(content)
    assert (classes["src"], classes["fixture"]) == (("core/**",), ("data/**",))
    assert classes["test"] == CONST_DEFAULT_PATH_CLASSES["test"]


def test_load_path_classes_default_fallback(tmp_path: Path) -> None:
    """load_path_classes returns default classes when no file is found."""
    classes = load_path_classes(repo_root=tmp_path)
    assert classes == dict(CONST_DEFAULT_PATH_CLASSES)


def test_matches_any_pattern_variations() -> None:
    """_matches_any_pattern handles empty, glob, and wildcard patterns."""
    assert _matches_any_pattern("src/main.py", ["src/**", ""]) is True
    assert _matches_any_pattern("tests/fixtures/data.json", ["tests/fixtures/**"]) is True
    assert _matches_any_pattern("docs/readme.md", ["src/**"]) is False


def test_classify_path_and_is_fixture() -> None:
    """classify_path classifies into priority classes and is_fixture identifies fixtures."""
    custom = {
        "src": ("src/**",),
        "test": ("tests/**",),
        "fixture": ("tests/fixtures/**", "tests/golden/**"),
        "iac": ("k8s/**",),
        "docs": ("docs/**",),
    }

    assert (
        classify_path("tests/fixtures/sample.yaml", custom),
        classify_path("tests/test_app.py", custom),
        classify_path("k8s/deploy.yaml", custom),
        classify_path("docs/index.md", custom),
        classify_path("src/app.py", custom),
    ) == ("fixture", "test", "iac", "docs", "src")

    assert (
        is_fixture_path("tests/fixtures/sample.yaml", custom),
        is_fixture_path("tests/golden/ref.json", custom),
        is_fixture_path("src/app.py", custom),
    ) == (True, True, False)
