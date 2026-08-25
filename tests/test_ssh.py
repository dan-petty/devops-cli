"""Tests for SSH key generation, management, and CLI commands."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ssh import app as ssh_app
from devops_cli.crypto.ssh_keys import (
    find_newest_key,
    generate_ed25519_key,
    get_key_age_days,
    list_managed_keys,
    parse_key_date,
)
from devops_cli.models.ssh import ManagedSSHKey

runner = CliRunner()


def test_generate_creates_key_pair(tmp_path: Path) -> None:
    key_path = tmp_path / "id_ed25519-2024JAN15"
    generate_ed25519_key(key_path, comment="test-key")

    assert key_path.exists(), "private key missing"
    assert oct(key_path.stat().st_mode & 0o777) == oct(0o600)

    pub_path = key_path.with_name(f"{key_path.name}.pub")
    assert pub_path.exists(), "public key missing"
    pub_text = pub_path.read_text()
    assert pub_text.startswith("ssh-ed25519 ")
    assert "test-key" in pub_text


def test_generate_no_comment(tmp_path: Path) -> None:
    key_path = tmp_path / "id_ed25519-2024JAN15"
    generate_ed25519_key(key_path)
    pub_path = key_path.with_name(f"{key_path.name}.pub")
    assert pub_path.read_text().startswith("ssh-ed25519 ")


def test_parse_key_date_valid() -> None:
    d = parse_key_date(Path("/home/user/.ssh/id_ed25519-2024JAN15"))
    assert d is not None
    assert d == date(2024, 1, 15)


def test_parse_key_date_different_months() -> None:
    cases = [
        ("id_ed25519-2024FEB29", date(2024, 2, 29)),  # leap year
        ("id_ed25519-2024DEC31", date(2024, 12, 31)),
        ("id_ed25519-2025MAR01", date(2025, 3, 1)),
    ]
    for name, expected in cases:
        assert parse_key_date(Path(name)) == expected, name


def test_parse_key_date_invalid() -> None:
    assert parse_key_date(Path("id_rsa")) is None
    assert parse_key_date(Path("id_ed25519")) is None
    assert parse_key_date(Path("id_ed25519-2024jan15")) is None  # lowercase invalid
    assert parse_key_date(Path("id_ed25519-2024JAN15.pub")) is None  # pub suffix


def test_get_key_age_days(tmp_path: Path) -> None:
    past = (date.today() - timedelta(days=10)).strftime("%Y%b%d").upper()
    key_path = tmp_path / f"id_ed25519-{past}"
    key_path.write_text("")
    assert get_key_age_days(key_path) == 10


def test_get_key_age_invalid(tmp_path: Path) -> None:
    key_path = tmp_path / "id_rsa"
    key_path.write_text("")
    with pytest.raises(ValueError, match="Cannot parse date"):
        get_key_age_days(key_path)


def test_find_newest_key(tmp_path: Path) -> None:
    ages = [30, 60, 10, 5]  # days ago
    for age in ages:
        d = (date.today() - timedelta(days=age)).strftime("%Y%b%d").upper()
        (tmp_path / f"id_ed25519-{d}").write_text("")

    newest = find_newest_key(tmp_path)
    assert newest is not None
    assert get_key_age_days(newest) == 5


def test_find_newest_key_empty(tmp_path: Path) -> None:
    assert find_newest_key(tmp_path) is None


def test_find_newest_key_missing_dir(tmp_path: Path) -> None:
    assert find_newest_key(tmp_path / "nonexistent") is None


def test_list_managed_keys_filters_correctly(tmp_path: Path) -> None:
    (tmp_path / "id_ed25519-2024JAN15").write_text("")
    (tmp_path / "id_ed25519-2024JAN15.pub").write_text("")  # pub — excluded
    (tmp_path / "id_rsa").write_text("")  # wrong pattern — excluded
    (tmp_path / "known_hosts").write_text("")  # excluded
    (tmp_path / "id_ed25519-2025MAR01").write_text("")

    keys = list_managed_keys(tmp_path)
    names = {k.name for k in keys}
    assert names == {"id_ed25519-2024JAN15", "id_ed25519-2025MAR01"}


def test_ssh_commands(tmp_path: Path) -> None:
    """Verify ssh generate, status, audit, and register subcommands."""
    mock_key_info = ManagedSSHKey(
        path=tmp_path / "id_ed25519-2024JAN15",
        key_date=date(2024, 1, 15),
        age_days=10,
    )
    priv_file = tmp_path / "id_ed25519-2024JAN15"
    pub_file = tmp_path / "id_ed25519-2024JAN15.pub"
    priv_file.write_text("private", encoding="utf-8")
    pub_file.write_text("ssh-ed25519 AAAA test@domain.com", encoding="utf-8")

    with (
        patch("devops_cli.crypto.ssh_keys.list_managed_keys_info", return_value=[mock_key_info]),
        patch("devops_cli.crypto.ssh_keys.generate_ed25519_key"),
        patch("devops_cli.crypto.ssh_keys.find_newest_key", return_value=priv_file),
        patch("devops_cli.github.ssh.register_key_on_github", return_value=True),
        patch("devops_cli.config.settings.get_github_token", return_value="ghp_test"),
        patch("devops_cli.commands.ssh._configure_git_signing"),
    ):
        res_gen = runner.invoke(
            ssh_app, ["generate", "--key-dir", str(tmp_path), "--comment", "test@domain.com"]
        )
        assert res_gen.exit_code == 0

        res_stat = runner.invoke(ssh_app, ["status", "--key-dir", str(tmp_path)])
        assert res_stat.exit_code == 0

        res_audit = runner.invoke(ssh_app, ["audit", "--key-dir", str(tmp_path)])
        assert res_audit.exit_code == 0

        res_reg = runner.invoke(
            ssh_app, ["register", "--key-file", str(priv_file), "--title", "My Key"]
        )
        assert res_reg.exit_code == 0
