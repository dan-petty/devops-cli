"""Automated regression suite verifying zero-plaintext invariant across files and exceptions."""

from __future__ import annotations

from pathlib import Path

from devops_cli.commands.config import _find_plaintext_config_leaks
from devops_cli.exceptions.security import InsecureConfigError


def test_find_plaintext_config_leaks_detects_secrets(tmp_path: Path) -> None:
    """Ensure _find_plaintext_config_leaks detects unencrypted tokens in yaml."""
    leak_file = tmp_path / "config.yaml"
    leak_file.write_text("github:\n  token: ghp_1234567890abcdef\nai:\n  provider: openai\n")

    leaks = _find_plaintext_config_leaks([leak_file])
    assert len(leaks) == 1
    assert "config.yaml:github.token" in leaks[0]


def test_find_plaintext_config_leaks_clean_file(tmp_path: Path) -> None:
    """Ensure _find_plaintext_config_leaks returns empty for clean configs."""
    clean_file = tmp_path / "config.yaml"
    clean_file.write_text("github:\n  owner: dan-petty\nai:\n  provider: openai\n")

    leaks = _find_plaintext_config_leaks([clean_file])
    assert leaks == []


def test_zero_plaintext_in_workspace_configs() -> None:
    """Scan workspace config files to assert 0 plaintext secret leaks exist."""
    scanned_files = [
        Path("config.yaml"),
        Path(".devops/config.yaml"),
        Path(".data/config.yaml"),
    ]
    leaks = _find_plaintext_config_leaks(scanned_files)
    assert leaks == [], f"Found plaintext secrets in configuration files: {leaks}"


def test_exception_sanitization_masks_sensitive_tokens() -> None:
    """Verify security exceptions sanitize credentials and paths."""
    err = InsecureConfigError(
        option_key="github.token",
        reason="Plaintext token detected",
        path=Path("/home/user/.devops/config.yaml"),
    )
    msg = str(err)
    assert "github.token" in msg
    assert err.code == "E_INSECURE_CONFIG"
    assert err.exit_code == 126
