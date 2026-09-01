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
    key_path = tmp_path / "id_ed25519-20240115"
    generate_ed25519_key(key_path, comment="test-key")

    assert key_path.exists(), "private key missing"
    assert oct(key_path.stat().st_mode & 0o777) == oct(0o600)

    pub_path = key_path.with_name(f"{key_path.name}.pub")
    assert pub_path.exists(), "public key missing"
    pub_text = pub_path.read_text()
    assert pub_text.startswith("ssh-ed25519 ")
    assert "test-key" in pub_text


def test_generate_no_comment(tmp_path: Path) -> None:
    key_path = tmp_path / "devops-cli-id_ed25519-20240115"
    generate_ed25519_key(key_path)
    pub_path = key_path.with_name(f"{key_path.name}.pub")
    assert pub_path.read_text().startswith("ssh-ed25519 ")


def test_parse_key_date_valid() -> None:
    d = parse_key_date(Path("/home/user/.ssh/id_ed25519-20240115"))
    assert d is not None
    assert d == date(2024, 1, 15)

    d_prefixed = parse_key_date(Path("/home/user/.ssh/devops-cli-id_ed25519-20260831"))
    assert d_prefixed is not None
    assert d_prefixed == date(2026, 8, 31)


def test_parse_key_date_different_dates() -> None:
    cases = [
        ("id_ed25519-20240229", date(2024, 2, 29)),  # leap year
        ("my-service-id_ed25519-20241231", date(2024, 12, 31)),
        ("team_a-id_ed25519-20250301", date(2025, 3, 1)),
    ]
    for name, expected in cases:
        assert parse_key_date(Path(name)) == expected, name


def test_parse_key_date_invalid() -> None:
    assert parse_key_date(Path("id_rsa")) is None
    assert parse_key_date(Path("id_ed25519")) is None
    assert parse_key_date(Path("id_ed25519-2024011")) is None  # too short
    assert parse_key_date(Path("id_ed25519-20240115.pub")) is None  # pub suffix
    assert parse_key_date(Path("id_ed25519-20241301")) is None  # invalid month


def test_get_ssh_key_prefix_resolution(tmp_path: Path) -> None:
    from devops_cli.crypto.ssh_keys import format_managed_key_filename, get_ssh_key_prefix

    # 1. Config setting override
    with patch("devops_cli.config.settings.load_settings") as mock_load:
        settings = MagicMock()
        settings.ssh.key_prefix = "custom-prod"
        mock_load.return_value = settings
        assert get_ssh_key_prefix(tmp_path) == "custom-prod"
        assert (
            format_managed_key_filename(key_date=date(2026, 8, 31))
            == "custom-prod-id_ed25519-20260831"
        )

    # 2. Devcontainer json name
    dev_dir = tmp_path / "project_a"
    dev_config = dev_dir / ".devcontainer"
    dev_config.mkdir(parents=True)
    (dev_config / "devcontainer.json").write_text('{\n  "name": "Project Alpha Microservice"\n}')

    with patch("devops_cli.config.settings.load_settings") as mock_load:
        settings = MagicMock()
        settings.ssh.key_prefix = None
        mock_load.return_value = settings
        assert get_ssh_key_prefix(dev_dir) == "project-alpha-microservice"

    # 3. Fallback to basename pwd
    plain_dir = tmp_path / "my_plain_repo"
    plain_dir.mkdir()
    with patch("devops_cli.config.settings.load_settings") as mock_load:
        settings = MagicMock()
        settings.ssh.key_prefix = None
        mock_load.return_value = settings
        assert get_ssh_key_prefix(plain_dir) == "my_plain_repo"


def test_get_key_age_days(tmp_path: Path) -> None:
    past = (date.today() - timedelta(days=10)).strftime("%Y%m%d")
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
        d = (date.today() - timedelta(days=age)).strftime("%Y%m%d")
        (tmp_path / f"devops-cli-id_ed25519-{d}").write_text("")

    newest = find_newest_key(tmp_path)
    assert newest is not None
    assert get_key_age_days(newest) == 5


def test_find_newest_key_empty(tmp_path: Path) -> None:
    assert find_newest_key(tmp_path) is None


def test_find_newest_key_missing_dir(tmp_path: Path) -> None:
    assert find_newest_key(tmp_path / "nonexistent") is None


def test_list_managed_keys_filters_correctly(tmp_path: Path) -> None:
    (tmp_path / "id_ed25519-20240115").write_text("")
    (tmp_path / "devops-cli-id_ed25519-20240115.pub").write_text("")  # pub — excluded
    (tmp_path / "id_rsa").write_text("")  # wrong pattern — excluded
    (tmp_path / "known_hosts").write_text("")  # excluded
    (tmp_path / "custom-app-id_ed25519-20250301").write_text("")

    keys = list_managed_keys(tmp_path)
    names = {k.name for k in keys}
    assert names == {"id_ed25519-20240115", "custom-app-id_ed25519-20250301"}


def test_ssh_commands(tmp_path: Path) -> None:
    """Verify ssh generate, status, audit, register, and rotate subcommands."""
    mock_key_info = ManagedSSHKey(
        path=tmp_path / "devops-cli-id_ed25519-20240115",
        key_date=date(2024, 1, 15),
        age_days=10,
    )
    priv_file = tmp_path / "devops-cli-id_ed25519-20240115"
    pub_file = tmp_path / "devops-cli-id_ed25519-20240115.pub"
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


def test_ssh_dry_run_commands(tmp_path: Path) -> None:
    """Verify dry-run mode across all ssh subcommands."""
    with patch("devops_cli.dry_run.is_dry_run", return_value=True):
        assert runner.invoke(ssh_app, ["generate", "--key-dir", str(tmp_path)]).exit_code == 0
        assert runner.invoke(ssh_app, ["register"]).exit_code == 0
        assert runner.invoke(ssh_app, ["rotate"]).exit_code == 0
        assert runner.invoke(ssh_app, ["audit"]).exit_code == 0
        assert runner.invoke(ssh_app, ["status"]).exit_code == 0


def test_ssh_generate_key_collision(tmp_path: Path) -> None:
    """Verify ssh generate exits with error when key already exists."""
    with (
        patch("devops_cli.commands.ssh._date_suffix", return_value="20260101"),
        patch("devops_cli.config.settings.load_settings") as mock_load,
    ):
        settings = MagicMock()
        settings.ssh.key_dir = tmp_path
        settings.ssh.key_prefix = None
        mock_load.return_value = settings
        (tmp_path / "devops-cli-id_ed25519-20260101").touch()
        res_exist = runner.invoke(ssh_app, ["generate"])
        assert res_exist.exit_code == 1


def test_ssh_register_error_branches(tmp_path: Path) -> None:
    """Verify ssh register error paths for missing key, missing pub, and API error."""
    from devops_cli.github.ssh import SSHRegistrationError

    # Missing newest key
    with (
        patch("devops_cli.crypto.ssh_keys.find_newest_key", return_value=None),
        patch("devops_cli.config.settings.load_settings") as mock_load,
    ):
        settings = MagicMock()
        settings.ssh.key_dir = tmp_path
        settings.ssh.key_prefix = None
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
        patch("devops_cli.config.settings.load_settings") as mock_load,
    ):
        settings = MagicMock()
        settings.ssh.key_prefix = None
        mock_load.return_value = settings
        res_reg_err = runner.invoke(ssh_app, ["register", "--key-file", str(priv)])
        assert res_reg_err.exit_code == 1


def test_ssh_status_key_age_buckets(tmp_path: Path) -> None:
    """Verify ssh status output for warning threshold and overdue keys."""
    priv = tmp_path / "custom_priv"
    priv.touch()

    with (
        patch("devops_cli.crypto.ssh_keys.find_newest_key", return_value=priv),
        patch("devops_cli.config.settings.load_settings") as mock_load,
    ):
        settings = MagicMock()
        settings.ssh.key_dir = tmp_path
        settings.ssh.key_prefix = None
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


def test_ssh_audit_key_age_buckets(tmp_path: Path) -> None:
    """Verify ssh audit output with multiple managed key ages."""
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
        settings.ssh.key_prefix = None
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
    k1 = tmp_path / "id_ed25519-20240115"
    k1.write_text("priv1", encoding="utf-8")
    k2 = tmp_path / "devops-cli-id_ed25519-20241201"
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


def test_generate_ed25519_key_overwriting_insecure_permissions(tmp_path: Path) -> None:
    """Verify that overwriting pre-existing keys resets permissions to 0600 / 0644."""
    import os

    k_path = tmp_path / "id_ed25519-20250101"
    pub_path = tmp_path / "id_ed25519-20250101.pub"

    # Pre-create files with overly permissive permissions (0666 / 0644)
    k_path.write_text("old_insecure_private_key")
    os.chmod(k_path, 0o666)
    pub_path.write_text("old_public_key")
    os.chmod(pub_path, 0o666)

    # Regenerate key pair
    generate_ed25519_key(k_path, comment="test-regen")

    # Assert permissions were clamped to 0600 for private and 0644 for public
    priv_mode = os.stat(k_path).st_mode & 0o777
    pub_mode = os.stat(pub_path).st_mode & 0o777
    assert priv_mode == 0o600
    assert pub_mode == 0o644


def test_ssh_prefix_filtering_and_parsing(tmp_path: Path) -> None:
    """Verify prefix filtering in list_managed_keys, find_newest_key, and parse_key_prefix."""
    from devops_cli.crypto.ssh_keys import (
        find_newest_key,
        list_managed_keys,
        list_managed_keys_info,
        parse_key_prefix,
    )

    k_proj_a = tmp_path / "proj-a-id_ed25519-20260801"
    k_proj_b = tmp_path / "proj-b-id_ed25519-20260901"
    k_no_prefix = tmp_path / "id_ed25519-20260815"
    k_proj_a.write_text("a")
    k_proj_b.write_text("b")
    k_no_prefix.write_text("c")

    assert parse_key_prefix(k_proj_a) == "proj-a"
    assert parse_key_prefix(k_proj_b) == "proj-b"
    assert parse_key_prefix(k_no_prefix) is None

    # Filter list_managed_keys
    keys_a = list_managed_keys(tmp_path, prefix="proj-a")
    assert keys_a == [k_proj_a]

    keys_all = list_managed_keys(tmp_path)
    assert len(keys_all) == 3

    # find_newest_key with prefix
    assert find_newest_key(tmp_path, prefix="proj-a") == k_proj_a
    assert find_newest_key(tmp_path, prefix="proj-b") == k_proj_b
    assert find_newest_key(tmp_path, prefix="nonexistent") == k_proj_b  # Fallback to newest

    # list_managed_keys_info with prefix
    info_a = list_managed_keys_info(tmp_path, prefix="proj-a")
    assert len(info_a) == 1
    assert info_a[0].path == k_proj_a

    # Non-directory path returns empty list without raising NotADirectoryError
    regular_file = tmp_path / "not_a_dir.txt"
    regular_file.write_text("just a file", encoding="utf-8")
    assert list_managed_keys(regular_file) == []


def test_ssh_register_honors_prefix_setting_and_option(tmp_path: Path) -> None:
    """Verify devops ssh register and list commands honor settings.ssh.key_prefix and --prefix flag."""
    k_prefixed = tmp_path / "custom-env-id_ed25519-20260901"
    k_prefixed.write_text("private")
    (tmp_path / "custom-env-id_ed25519-20260901.pub").write_text("ssh-ed25519 AAAA custom@env")

    # Add second key with different prefix
    k_other = tmp_path / "other-proj-id_ed25519-20260901"
    k_other.write_text("private-other")
    (tmp_path / "other-proj-id_ed25519-20260901.pub").write_text("ssh-ed25519 BBBB other@proj")

    mock_registered_titles: list[str] = []

    def mock_register_gh(pub_key: str, title: str, token: str | None = None) -> None:
        mock_registered_titles.append(title)

    with (
        patch("devops_cli.github.ssh.register_key_on_github", side_effect=mock_register_gh),
        patch("devops_cli.config.settings.get_github_token", return_value="ghp_test"),
        patch("devops_cli.commands.ssh._configure_git_signing"),
        patch("devops_cli.config.settings.load_settings") as mock_load,
    ):
        settings = MagicMock()
        settings.ssh.key_dir = tmp_path
        settings.ssh.key_prefix = "custom-env"
        settings.ssh.rotation_days = 90
        mock_load.return_value = settings

        # 1. Register with key_prefix setting (no --key-file or --title)
        res = runner.invoke(ssh_app, ["register"])
        assert res.exit_code == 0
        assert mock_registered_titles[-1] == "custom-env-id_ed25519-20260901"

        # 2. Register with explicit --prefix option
        res_opt = runner.invoke(ssh_app, ["register", "--prefix", "custom-env"])
        assert res_opt.exit_code == 0
        assert mock_registered_titles[-1] == "custom-env-id_ed25519-20260901"

        # 3. Status with prefix option
        res_stat = runner.invoke(ssh_app, ["status", "--prefix", "custom-env"])
        assert res_stat.exit_code == 0
        assert "custom-env-id_ed25519-20260901" in res_stat.output

        # 4. List without --prefix defaults to settings.ssh.key_prefix (shows custom-env, excludes other-proj)
        res_list_default = runner.invoke(ssh_app, ["list"])
        assert res_list_default.exit_code == 0
        assert "custom-env-id_ed25519-20260901" in res_list_default.output
        assert "other-proj-id_ed25519-20260901" not in res_list_default.output

        # 5. List with explicit --prefix other-proj (shows other-proj, excludes custom-env)
        res_list_other = runner.invoke(ssh_app, ["list", "--prefix", "other-proj"])
        assert res_list_other.exit_code == 0
        assert "other-proj-id_ed25519-20260901" in res_list_other.output
        assert "custom-env-id_ed25519-20260901" not in res_list_other.output


def test_ssh_empty_states_and_rotation_failure(tmp_path: Path) -> None:
    """Verify ssh commands when key dir is empty or rotation fails."""
    from devops_cli.github.ssh import SSHRegistrationError

    empty_dir = tmp_path / "empty_keys"
    empty_dir.mkdir()

    # 1. Rotate in empty dir
    res_rot = runner.invoke(ssh_app, ["rotate", "--key-dir", str(empty_dir)])
    assert res_rot.exit_code == 0
    assert "No managed SSH keys found" in res_rot.output

    # 2. List in empty dir
    res_list = runner.invoke(ssh_app, ["list", "--key-dir", str(empty_dir)])
    assert res_list.exit_code == 0
    assert "No managed SSH keys found" in res_list.output

    # 3. Status in empty dir
    res_stat = runner.invoke(ssh_app, ["status", "--key-dir", str(empty_dir)])
    assert res_stat.exit_code == 0
    assert "No managed SSH keys found" in res_stat.output

    # 4. Rotation with failed GitHub registration cleanup
    old_key = tmp_path / "id_ed25519-20240101"
    old_key.write_text("old_private")
    (tmp_path / "id_ed25519-20240101.pub").write_text("ssh-ed25519 AAA old@test")

    with (
        patch(
            "devops_cli.github.ssh.register_key_on_github",
            side_effect=SSHRegistrationError("API timeout"),
        ),
        patch("devops_cli.config.settings.get_github_token", return_value="ghp_test"),
        patch("devops_cli.config.settings.load_settings") as mock_load,
    ):
        settings = MagicMock()
        settings.ssh.key_dir = tmp_path
        settings.ssh.key_prefix = None
        settings.ssh.rotation_days = 30
        mock_load.return_value = settings

        res_rot_fail = runner.invoke(ssh_app, ["rotate", "--force"])
        assert res_rot_fail.exit_code == 0
        assert "registration failed" in res_rot_fail.output


def test_crypto_ssh_keys_edge_cases(tmp_path: Path) -> None:
    """Verify corrupted devcontainer.json parsing, parse_key_prefix, and format_managed_key_filename."""
    from devops_cli.crypto.ssh_keys import (
        format_managed_key_filename,
        get_ssh_key_prefix,
        parse_key_prefix,
    )

    # 1. Corrupted devcontainer.json
    dev_dir = tmp_path / "bad_devcontainer"
    dev_cfg = dev_dir / ".devcontainer"
    dev_cfg.mkdir(parents=True)
    (dev_cfg / "devcontainer.json").write_text("INVALID JSON // comment", encoding="utf-8")

    with patch("devops_cli.config.settings.load_settings", side_effect=Exception("no settings")):
        prefix = get_ssh_key_prefix(dev_dir)
        assert prefix == "bad_devcontainer"

    # 2. format_managed_key_filename with empty prefix
    fn = format_managed_key_filename(prefix="", key_date=date(2026, 9, 1))
    assert fn == "id_ed25519-20260901"

    # 3. parse_key_prefix with invalid key name
    assert parse_key_prefix(Path("unmanaged_rsa_key")) is None
    assert parse_key_prefix(Path("my-prefix-id_ed25519-20260901")) == "my-prefix"
