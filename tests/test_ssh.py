"""Tests for SSH key generation, management, and CLI commands."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    """Verify ssh generate, status, audit, register, and rotate subcommands."""
    mock_key_info = ManagedSSHKey(
        path=tmp_path / "id_ed25519-2024JAN15",
        key_date=date(2024, 1, 15),
        age_days=10,
    )
    priv_file = tmp_path / "id_ed25519-2024JAN15"
    pub_file = tmp_path / "id_ed25519-2024JAN15.pub"
    priv_file.write_text("private", encoding="utf-8")
    pub_file.write_text("ssh-ed25519 AAAA test@domain.com", encoding="utf-8")

    def mock_gen_key(path: Path, *args: object, **kwargs: object) -> None:
        Path(path).write_text("private", encoding="utf-8")
        Path(f"{path}.pub").write_text("ssh-ed25519 AAAA test@domain.com", encoding="utf-8")

    with (
        patch("devops_cli.crypto.ssh_keys.list_managed_keys_info", return_value=[mock_key_info]),
        patch("devops_cli.crypto.ssh_keys.generate_ed25519_key", side_effect=mock_gen_key),
        patch("devops_cli.crypto.ssh_keys.find_newest_key", return_value=priv_file),
        patch("devops_cli.crypto.ssh_keys.get_key_age_days", return_value=10),
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

        res_rot = runner.invoke(ssh_app, ["rotate", "--key-dir", str(tmp_path)])
        assert res_rot.exit_code == 0

        res_rot_force = runner.invoke(ssh_app, ["rotate", "--key-dir", str(tmp_path), "--force"])
        assert res_rot_force.exit_code == 0


def test_ssh_error_and_dry_run_branches(tmp_path: Path) -> None:
    """Verify ssh dry-run, missing keys, registration errors, and age buckets."""
    from devops_cli.github.ssh import SSHRegistrationError

    # 1. Dry run
    with patch("devops_cli.dry_run.is_dry_run", return_value=True):
        assert runner.invoke(ssh_app, ["generate", "--key-dir", str(tmp_path)]).exit_code == 0
        assert runner.invoke(ssh_app, ["register"]).exit_code == 0
        assert runner.invoke(ssh_app, ["rotate"]).exit_code == 0
        assert runner.invoke(ssh_app, ["audit"]).exit_code == 0
        assert runner.invoke(ssh_app, ["status"]).exit_code == 0

    # 2. Generate key collision (exists)
    with (
        patch("devops_cli.commands.ssh._date_suffix", return_value="2026JAN01"),
        patch("devops_cli.config.settings.load_settings") as mock_load,
    ):
        settings = MagicMock()
        settings.ssh.key_dir = tmp_path
        mock_load.return_value = settings
        (tmp_path / "id_ed25519-2026JAN01").touch()
        res_exist = runner.invoke(ssh_app, ["generate"])
        assert res_exist.exit_code == 1

    # 3. Register missing key or pub
    with (
        patch("devops_cli.crypto.ssh_keys.find_newest_key", return_value=None),
        patch("devops_cli.config.settings.load_settings") as mock_load,
    ):
        settings = MagicMock()
        settings.ssh.key_dir = tmp_path
        mock_load.return_value = settings
        res_no_key = runner.invoke(ssh_app, ["register"])
        assert res_no_key.exit_code == 1

    # Missing .pub
    priv = tmp_path / "custom_priv"
    priv.touch()
    res_no_pub = runner.invoke(ssh_app, ["register", "--key-file", str(priv)])
    assert res_no_pub.exit_code == 1

    # SSHRegistrationError in register
    (tmp_path / "custom_priv.pub").write_text("ssh-ed25519 AAAA", encoding="utf-8")
    with (
        patch(
            "devops_cli.github.ssh.register_key_on_github",
            side_effect=SSHRegistrationError("API error"),
        ),
        patch("devops_cli.config.settings.get_github_token", return_value="token"),
    ):
        res_reg_err = runner.invoke(ssh_app, ["register", "--key-file", str(priv)])
        assert res_reg_err.exit_code == 1

    # 4. Status age checks (>7, <=7, overdue)
    with (
        patch("devops_cli.crypto.ssh_keys.find_newest_key", return_value=priv),
        patch("devops_cli.config.settings.load_settings") as mock_load,
    ):
        settings = MagicMock()
        settings.ssh.key_dir = tmp_path
        settings.ssh.rotation_days = 90
        mock_load.return_value = settings

        with patch("devops_cli.crypto.ssh_keys.get_key_age_days", return_value=85):
            res_stat_warn = runner.invoke(ssh_app, ["status"])
            assert res_stat_warn.exit_code == 0
            assert "5 days remaining" in res_stat_warn.output

        with patch("devops_cli.crypto.ssh_keys.get_key_age_days", return_value=100):
            res_stat_overdue = runner.invoke(ssh_app, ["status"])
            assert res_stat_overdue.exit_code == 0
            assert "overdue by 10 days" in res_stat_overdue.output

    # 5. Audit age buckets
    from devops_cli.crypto.ssh_keys import ManagedSSHKey

    keys = [
        ManagedSSHKey(path=tmp_path / "k1", key_date=date.today(), age_days=110),
        ManagedSSHKey(path=tmp_path / "k2", key_date=date.today(), age_days=95),
        ManagedSSHKey(path=tmp_path / "k3", key_date=date.today(), age_days=85),
        ManagedSSHKey(path=tmp_path / "k4", key_date=date.today(), age_days=10),
    ]
    with (
        patch("devops_cli.crypto.ssh_keys.list_managed_keys_info", return_value=keys),
        patch("devops_cli.config.settings.load_settings") as mock_load,
    ):
        settings = MagicMock()
        settings.ssh.key_dir = tmp_path
        settings.ssh.rotation_days = 90
        mock_load.return_value = settings

        res_audit = runner.invoke(ssh_app, ["audit"])
        assert res_audit.exit_code == 0


def test_list_managed_keys_info_and_find_newest(tmp_path: Path) -> None:
    """Verify list_managed_keys_info and find_newest_key directly against filesystem."""
    from devops_cli.crypto.ssh_keys import (
        find_newest_key,
        list_managed_keys,
        list_managed_keys_info,
    )

    # 1. Empty dir
    assert list_managed_keys(tmp_path / "empty") == []
    assert find_newest_key(tmp_path / "empty") is None

    # 2. Populated dir
    k1 = tmp_path / "id_ed25519-2024JAN15"
    k1.write_text("priv1", encoding="utf-8")
    k2 = tmp_path / "id_ed25519-2024DEC01"
    k2.write_text("priv2", encoding="utf-8")
    unmanaged = tmp_path / "id_rsa"
    unmanaged.write_text("rsa", encoding="utf-8")

    keys_info = list_managed_keys_info(tmp_path)
    assert len(keys_info) == 2
    paths = [k.path for k in keys_info]
    assert k1 in paths
    assert k2 in paths
    assert all(k.age_days is not None for k in keys_info)

    newest = find_newest_key(tmp_path)
    assert newest == k2
