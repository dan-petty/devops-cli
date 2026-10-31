"""Tests for GH_TELEMETRY_ENDPOINT_URL environment variable handling."""

import pytest

from devops_cli.core.process import build_subprocess_env
from devops_cli.exceptions import SecurityError


def test_build_subprocess_env_refuses_gh_telemetry_endpoint_url_override() -> None:
    """Verify build_subprocess_env raises SecurityError when env contains GH_TELEMETRY_ENDPOINT_URL."""
    with pytest.raises(SecurityError, match="GH_TELEMETRY_ENDPOINT_URL"):
        build_subprocess_env(env={"GH_TELEMETRY_ENDPOINT_URL": "https://example.com"})


def test_build_subprocess_env_accepts_gh_telemetry_override() -> None:
    """Verify build_subprocess_env does not raise SecurityError when env contains GH_TELEMETRY set to log."""
    env = build_subprocess_env(env={"GH_TELEMETRY": "log"})
    assert env.get("GH_TELEMETRY") == "log"


def test_build_subprocess_env_accepts_gh_telemetry_sample_rate_override() -> None:
    """Verify build_subprocess_env does not raise SecurityError when env contains GH_TELEMETRY_SAMPLE_RATE set to 0.5."""
    env = build_subprocess_env(env={"GH_TELEMETRY_SAMPLE_RATE": "0.5"})
    assert env.get("GH_TELEMETRY_SAMPLE_RATE") == "0.5"


def test_build_subprocess_env_ambient_excludes_telemetry_endpoint_url() -> None:
    """Verify that with isolate_env=True and os.environ containing GH_TELEMETRY_ENDPOINT_URL,
    the key is absent from the returned dict."""
    import os

    # Set the environment variable in current process
    original_value = os.environ.get("GH_TELEMETRY_ENDPOINT_URL")
    os.environ["GH_TELEMETRY_ENDPOINT_URL"] = "https://example.com"

    try:
        env = build_subprocess_env()
        assert "GH_TELEMETRY_ENDPOINT_URL" not in env
    finally:
        # Restore original value or unset
        if original_value is not None:
            os.environ["GH_TELEMETRY_ENDPOINT_URL"] = original_value
        else:
            os.environ.pop("GH_TELEMETRY_ENDPOINT_URL", None)
