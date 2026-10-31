"""Tests for settings parsing, dotted_set top-level validation, and list field coercion."""

from __future__ import annotations

import pytest

from devops_cli.config.settings import ServiceConfig, Settings, dotted_set
from devops_cli.exceptions import ConfigurationError


@pytest.mark.parametrize(
    ("input_repos", "expected"),
    [
        pytest.param(
            '["org/repo1", "org/repo2"]', ["org/repo1", "org/repo2"], id="json-list-string"
        ),
        pytest.param(
            "org/repo1, org/repo2", ["org/repo1", "org/repo2"], id="comma-separated-string"
        ),
        pytest.param("", [], id="empty-string"),
        pytest.param(
            ['["org/repo1", "org/repo2"]'],
            ["org/repo1", "org/repo2"],
            id="one-item-list-json-string",
        ),
        pytest.param(["[not-json]"], ["[not-json]"], id="one-item-list-broken-json"),
        pytest.param(["[not-json"], ["[not-json"], id="one-item-list-unclosed-bracket"),
    ],
)
def test_parse_repos_handles_various_input_shapes(
    input_repos: str | list[str], expected: list[str]
) -> None:
    """Verify ServiceConfig._parse_repos correctly parses JSON, comma-separated, and list strings."""
    config = ServiceConfig(repos=input_repos)
    assert config.repos == expected


def test_dotted_set_rejects_top_level_section_assignment() -> None:
    """Calling dotted_set with a top-level section name directly raises ConfigurationError."""
    settings = Settings()
    with pytest.raises(ConfigurationError) as exc_info:
        dotted_set(settings, "ai", "invalid-value")
    assert "Cannot set top-level section 'ai' directly to a string" in str(exc_info.value)
    assert exc_info.value.key == "ai"


def test_dotted_set_rejects_unknown_top_level_key() -> None:
    """Calling dotted_set with an unknown top-level key raises ConfigurationError."""
    settings = Settings()
    with pytest.raises(ConfigurationError) as exc_info:
        dotted_set(settings, "nonexistent_top_key", "some-value")
    assert "Unknown configuration key 'nonexistent_top_key'" in str(exc_info.value)
    assert exc_info.value.key == "nonexistent_top_key"


def test_dotted_set_rejects_invalid_top_level_value() -> None:
    """Calling dotted_set on a top-level field with an invalid value raises ValueError."""
    settings = Settings()
    with pytest.raises(ValueError, match=r"domain: Input should be a valid string"):
        dotted_set(settings, "domain", object())


def test_dotted_set_coerces_json_list_string_for_list_field() -> None:
    """Calling dotted_set with a JSON list string on a list field coerces it into a list."""
    settings = Settings()
    dotted_set(settings, "service.repos", '["org/repo1", "org/repo2"]')
    assert settings.service.repos == ["org/repo1", "org/repo2"]


def test_ai_config_has_no_append_cache_shim() -> None:
    """AIConfig has no append_cache property or legacy migration shim."""
    settings = Settings()
    assert not hasattr(settings.ai, "append_cache")
    assert hasattr(settings.ai.cache, "append_cache")
