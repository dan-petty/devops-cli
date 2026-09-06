"""Unit tests for centralized secret sanitizer (TDD Specification)."""

from __future__ import annotations

from devops_cli.security.sanitizer import mask_dict_secrets, mask_secrets, mask_uri_credentials


def test_mask_secrets_tokens() -> None:
    """Masks GitHub tokens, OpenAI keys, Anthropic keys, and generic auth tokens."""
    sample = (
        "Token: ghp_1234567890abcdef1234\n"
        "Key: sk-ant-api03-abcdef123456789012345678\n"
        "Pass: password='SecretSuperPassword123!'"
    )
    masked = mask_secrets(sample)
    assert "ghp_1234567890abcdef1234" not in masked
    assert "<masked-github-token>" in masked
    assert "sk-ant-api03-abcdef123456789012345678" not in masked
    assert "<masked-anthropic-key>" in masked
    assert "SecretSuperPassword123!" not in masked


def test_mask_dict_secrets_recursive() -> None:
    """Recursively masks string values in nested dictionaries."""
    data = {
        "user": "admin",
        "auth": {
            "token": "ghp_1234567890abcdef1234",
            "safe": "public_value",
        },
        "items": ["token=gho_abcdef1234567890", 123, True],
    }
    cleaned = mask_dict_secrets(data)
    assert cleaned["auth"]["token"] == "<masked-github-token>"
    assert cleaned["auth"]["safe"] == "public_value"
    assert "<masked-github-token>" in cleaned["items"][0]
    assert cleaned["items"][1] == 123


def test_mask_uri_credentials() -> None:
    """Masks credentials embedded in URLs."""
    url = "https://dan:supersecretpass@github.com/dan-petty/repo.git"
    masked = mask_uri_credentials(url)
    assert "supersecretpass" not in masked
    assert "dan:***@github.com" in masked or "dan:<masked>@github.com" in masked


def test_mask_secrets_expanded_patterns() -> None:
    """Masks Vault tokens, GitLab PATs, Slack webhooks, and HuggingFace tokens."""
    dummy_webhook = "".join(
        ["https://", "hooks.", "slack.", "com/services/", "T00000000/", "B00000000/", "A" * 24]
    )
    sample = (
        "Vault: hvs.1234567890abcdef12345678\n"
        "Vault Legacy: s.abcdef123456789012345678\n"
        "GitLab: glpat-abcdef1234567890_1234\n"
        f"Slack Webhook: {dummy_webhook}\n"
        "HuggingFace: hf_abcdefghijklmnopqrstuvwxyz01234567\n"
    )

    masked = mask_secrets(sample)
    assert "hvs.1234567890abcdef12345678" not in masked
    assert "<masked-vault-token>" in masked
    assert "s.abcdef123456789012345678" not in masked
    assert "glpat-abcdef1234567890_1234" not in masked
    assert "<masked-gitlab-token>" in masked
    assert "hooks.slack.com/services" not in masked
    assert "<masked-slack-webhook>" in masked
    assert "hf_abcdefghijklmnopqrstuvwxyz01234567" not in masked
    assert "<masked-huggingface-token>" in masked


def test_mask_uri_credentials_edge_cases() -> None:
    """Verify empty string and unparseable URI regex fallback in mask_uri_credentials."""
    assert mask_uri_credentials("") == ""

    # Valid URI with credentials
    clean = mask_uri_credentials("https://user:secret123@example.com:8443/api")
    assert "secret123" not in clean
    assert "user:***@example.com:8443" in clean

    # URI where urlsplit might fail or regex fallback applies
    fallback_uri = "custom://admin:supersecret@myhost/path"
    res = mask_uri_credentials(fallback_uri)
    assert "supersecret" not in res
    assert "admin:***@" in res
