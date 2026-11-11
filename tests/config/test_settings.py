"""Tests for settings parsing, dotted_set top-level validation, and list field coercion."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from devops_cli.config.constants import CONST_AI_GATEWAY_HOSTED_MODELS
from devops_cli.config.settings import (
    RoadmapImplementConfig,
    ServiceConfig,
    Settings,
    dotted_set,
)
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
    ],
)
def test_parse_repos_handles_various_input_shapes(
    input_repos: str | list[str], expected: list[str]
) -> None:
    """Verify ServiceConfig._parse_repos correctly parses JSON, comma-separated, and list strings."""
    config = ServiceConfig(repos=input_repos)
    assert config.repos == expected


@pytest.mark.parametrize(
    "input_repos",
    [
        pytest.param(["Owner/Repo", "owner/repo"], id="two-spellings"),
        pytest.param(["owner/repo", "owner/repo"], id="same-entry-twice"),
        pytest.param(["[not-json]"], id="broken-json"),
        pytest.param(["[not-json"], id="unclosed-bracket"),
        pytest.param(["no-owner"], id="no-owner"),
        pytest.param(["owner/repo/extra"], id="three-parts"),
    ],
)
def test_service_repos_refuses_an_entry_that_is_no_new_repository(
    input_repos: list[str],
) -> None:
    """Each entry of `service.repos` is `owner/name`, and no two entries name one repository
    (#4533). The error names the setting."""
    with pytest.raises(ValidationError, match=r"service\.repos"):
        ServiceConfig(repos=input_repos)


def test_service_repos_keeps_the_github_spelling_of_each_entry() -> None:
    assert ServiceConfig(repos=["Owner/Repo", "owner/.github"]).repos == [
        "Owner/Repo",
        "owner/.github",
    ]


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


def test_the_implement_ladder_defaults_to_the_local_coder_group_of_each_step_class() -> None:
    """No step class starts on a hosted group, and every class has one tier (#3060)."""
    ladder = RoadmapImplementConfig().ladder

    assert ladder == {step_class: ["devops-coder"] for step_class in ("edit", "repair")}
    assert not {tier for tiers in ladder.values() for tier in tiers} & set(
        CONST_AI_GATEWAY_HOSTED_MODELS
    )


def test_the_implement_ladder_accepts_a_hosted_group_that_it_names() -> None:
    ladder = RoadmapImplementConfig(ladder={"repair": ["devops-coder", "claude-haiku-5-5"]}).ladder

    assert ladder["repair"] == ["devops-coder", "claude-haiku-5-5"]


def test_the_implement_ladder_refuses_a_step_class_that_does_not_exist() -> None:
    with pytest.raises(ValidationError, match="no step class design"):
        RoadmapImplementConfig(ladder={"design": ["devops-coder"]})


def test_the_implement_ladder_refuses_a_model_outside_the_gateway_groups() -> None:
    """A hosted model name reaches no request unless the ladder names a group that it knows."""
    with pytest.raises(ValidationError, match="no local gateway group"):
        RoadmapImplementConfig(ladder={"edit": ["gpt-4o"]})


def test_the_implement_ladder_refuses_a_repeated_tier_and_an_empty_list() -> None:
    with pytest.raises(ValidationError, match="names a tier twice"):
        RoadmapImplementConfig(ladder={"edit": ["devops-coder", "devops-coder"]})
    with pytest.raises(ValidationError, match="holds no tier"):
        RoadmapImplementConfig(ladder={"edit": []})


def test_the_implement_ladder_reads_a_json_object_of_a_config_set() -> None:
    ladder = RoadmapImplementConfig(
        ladder='{"edit": ["devops-coder", "ollama:qwen3.8:27b"]}'
    ).ladder

    assert ladder["edit"] == ["devops-coder", "ollama:qwen3.8:27b"]


def test_the_implement_ladder_refuses_text_that_is_no_json_object() -> None:
    with pytest.raises(ValidationError, match="must be a JSON object:"):
        RoadmapImplementConfig(ladder="{not json")
    with pytest.raises(ValidationError, match="must be a JSON object of step class"):
        RoadmapImplementConfig(ladder='["devops-coder"]')
    with pytest.raises(ValidationError, match="holds an empty tier"):
        RoadmapImplementConfig(ladder={"edit": ["  "]})
