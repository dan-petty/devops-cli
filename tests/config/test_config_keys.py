"""Verify which dotted keys the settings know, and which known keys have a name like an unknown one."""

from __future__ import annotations

import pytest

from devops_cli.config.settings import is_config_key, similar_config_keys


@pytest.mark.parametrize(
    "key",
    [
        pytest.param("github.default_org", id="section-field"),
        pytest.param("domain", id="top-level-field"),
        pytest.param("ai.tasks.chat.model", id="nested-section-field"),
        pytest.param("service.github_app.app_id", id="field-of-a-field-default-factory"),
        pytest.param("otel.enabled", id="otel-alias-of-telemetry"),
        pytest.param("firecrawl.api_key", id="credential-with-a-field"),
        pytest.param("grafana.token", id="credential-with-no-field"),
        pytest.param("service.github_app.private_key", id="nested-credential-with-no-field"),
    ],
)
def test_a_setting_or_a_credential_is_a_config_key(key: str) -> None:
    assert is_config_key(key) is True


@pytest.mark.parametrize(
    "key",
    [
        pytest.param("no.such_key", id="no-section"),
        pytest.param("tavily.api_key", id="removed-credential"),
        pytest.param("github.no_such_key", id="no-field"),
        pytest.param("ai", id="section"),
        pytest.param("ai.tasks.chat", id="nested-section"),
        pytest.param("ai.gateway_weights.example-model", id="entry-of-a-mapping"),
        pytest.param("ai.model_dump", id="method-of-a-section"),
    ],
)
def test_a_section_or_a_name_that_no_setting_has_is_no_config_key(key: str) -> None:
    assert is_config_key(key) is False


@pytest.mark.parametrize(
    ("key", "similar"),
    [
        pytest.param(
            "firecrawl.apikey",
            ["firecrawl.api_key", "ai.api_key", "qdrant.api_key"],
            id="credential-typo",
        ),
        pytest.param("github.default-org", ["github.default_org"], id="hyphen-for-underscore"),
        pytest.param("no.such_key", [], id="nothing-similar"),
    ],
)
def test_the_similar_config_keys_are_the_known_keys_nearest_to_the_name(
    key: str, similar: list[str]
) -> None:
    assert similar_config_keys(key) == similar
