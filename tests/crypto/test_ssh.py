"""Tests for SSH key generation, management, and CLI commands."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.commands import BIN_GIT
from devops_cli.core.process import run_subprocess
from devops_cli.crypto.ssh_keys import (
    find_newest_key,
    generate_ed25519_key,
    get_key_age_days,
    list_managed_keys,
    parse_key_date,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.git import GitFake
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.process import ProcessAnswer, ProcessCall


def _get_ssh_config_file(args: list[str], repo_dir: Path | None) -> Path:
    if "--local" in args and repo_dir:
        return repo_dir / ".git" / "config"
    return Path(os.environ.get("GIT_CONFIG_GLOBAL", "/dev/null"))


def _read_ssh_config_key(cfg_file: Path, key: str) -> ProcessAnswer:
    if not cfg_file.exists():
        return ProcessAnswer(returncode=1)
    for line in cfg_file.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            if k.strip().lower() == key.strip().lower():
                return ProcessAnswer(stdout=v.strip() + "\n", returncode=0)
    return ProcessAnswer(returncode=1)


def _handle_ssh_git_config(call: ProcessCall) -> ProcessAnswer:
    args = list(call.argv[1:])
    repo_dir = None
    if len(args) >= 2 and args[0] == "-C":
        repo_dir = Path(args[1])
        args = args[2:]
    if args and args[0] == "config":
        args = args[1:]
    cfg_file = _get_ssh_config_file(args, repo_dir)
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    clean_args = [a for a in args if a not in ("--global", "--local")]

    if "--get" in clean_args:
        idx = clean_args.index("--get")
        return _read_ssh_config_key(cfg_file, clean_args[idx + 1])

    if len(clean_args) == 2 and not clean_args[0].startswith("-"):
        with open(cfg_file, "a", encoding="utf-8") as f:
            f.write(f"\t{clean_args[0]} = {clean_args[1]}\n")
    return ProcessAnswer(returncode=0)


@pytest.fixture(autouse=True)
def _answer_ssh_git(git_fake: GitFake) -> None:
    git_fake.answer(["git", "config"], _handle_ssh_git_config)
    git_fake.answer(["git", "-C"], _handle_ssh_git_config)


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


def test_get_ssh_key_prefix_resolution(tmp_path: Path, config: Callable[..., Path]) -> None:
    from devops_cli.crypto.ssh_keys import format_managed_key_filename, get_ssh_key_prefix

    # 1. Config setting override
    config(ssh={"key_prefix": "custom-prod"})
    assert get_ssh_key_prefix(tmp_path) == "custom-prod"
    assert (
        format_managed_key_filename(key_date=date(2026, 8, 31)) == "custom-prod-id_ed25519-20260831"
    )

    # 2. Devcontainer json name
    config(ssh={"key_prefix": None})
    dev_dir = tmp_path / "project_a"
    dev_config = dev_dir / ".devcontainer"
    dev_config.mkdir(parents=True)
    (dev_config / "devcontainer.json").write_text('{\n  "name": "Project Alpha Microservice"\n}')
    assert get_ssh_key_prefix(dev_dir) == "project-alpha-microservice"

    # 3. Fallback to basename pwd
    plain_dir = tmp_path / "my_plain_repo"
    plain_dir.mkdir()
    assert get_ssh_key_prefix(plain_dir) == "my_plain_repo"


def test_devcontainer_name_survives_urls_next_to_comments(tmp_path: Path) -> None:
    """Verify the devcontainer name is the prefix when a string holds `//` beside real comments.

    Stripping `//` to the end of the line cut `"credential.https://github.com.helper"` in half,
    so the manifest stopped parsing and keys were named after the checkout directory instead.
    """
    from devops_cli.crypto.ssh_keys import get_ssh_key_prefix

    dev_dir = tmp_path / "checkout-worktree"
    (dev_dir / ".devcontainer").mkdir(parents=True)
    (dev_dir / ".devcontainer" / "devcontainer.json").write_text(
        '// Development container\n{\n  "name": "devops-cli", // the key prefix\n'
        '  "containerEnv": {"GIT_CONFIG_KEY_0": "credential.https://github.com.helper"}\n}\n'
    )

    assert get_ssh_key_prefix(dev_dir) == "devops-cli"


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


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(
            ["generate", "--key-dir", "{key_dir}", "--comment", "test@domain.com"], id="generate"
        ),
        pytest.param(["status", "--key-dir", "{key_dir}"], id="status"),
        pytest.param(["audit", "--key-dir", "{key_dir}"], id="audit"),
        pytest.param(["register", "--key-file", "{key_file}", "--title", "My Key"], id="register"),
        pytest.param(["rotate", "--key-dir", "{key_dir}"], id="rotate"),
        pytest.param(["rotate", "--key-dir", "{key_dir}", "--force"], id="rotate-force"),
    ],
)
def test_each_ssh_command_succeeds_with_a_current_managed_key(
    tmp_path: Path,
    cli: Callable[..., Any],
    config: Callable[..., Path],
    clock: ClockFake,
    github_api: GitHubApiFake,
    global_git_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
) -> None:
    """With a ten-day-old managed key and GitHub accepting the key, each command exits 0."""
    clock.move_to(datetime(2026, 9, 10, 12, tzinfo=UTC))
    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    priv_file = key_dir / "devops-cli-id_ed25519-20260831"
    _write_key_pair(key_dir, priv_file.name)
    config(ssh={"key_dir": str(key_dir), "key_prefix": "devops-cli"})
    _accept_keys(github_api)
    monkeypatch.chdir(tmp_path)  # not a repository, so signing changes only the global config

    result = cli(["ssh", *(arg.format(key_dir=key_dir, key_file=priv_file) for arg in argv)])

    assert result.exit_code == 0


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["generate", "--key-dir", "{key_dir}"], id="generate"),
        pytest.param(["register"], id="register"),
        pytest.param(["rotate"], id="rotate"),
        pytest.param(["audit"], id="audit"),
        pytest.param(["status"], id="status"),
    ],
)
def test_each_ssh_command_succeeds_in_a_dry_run(
    tmp_path: Path, cli: Callable[..., Any], argv: list[str]
) -> None:
    """In a dry run, each ssh command exits 0."""
    result = cli(
        ["ssh", *(arg.format(key_dir=tmp_path) for arg in argv)],
        env={"DEVOPS_CLI_DRY_RUN": "true"},
    )

    assert result.exit_code == 0


def test_ssh_generate_key_collision(
    tmp_path: Path, cli: Callable[..., Any], config: Callable[..., Path], clock: ClockFake
) -> None:
    """Verify ssh generate exits with error when key already exists."""
    clock.move_to(datetime(2026, 1, 1, 12, tzinfo=UTC))
    config(ssh={"key_dir": str(tmp_path), "key_prefix": "devops-cli"})
    (tmp_path / "devops-cli-id_ed25519-20260101").touch()

    assert cli(["ssh", "generate"]).exit_code == 1


def test_ssh_register_without_a_managed_key_exits_1(
    tmp_path: Path, cli: Callable[..., Any], config: Callable[..., Path]
) -> None:
    """With no managed key in the key directory, `ssh register` stops with exit status 1."""
    config(ssh={"key_dir": str(tmp_path), "key_prefix": "devops-cli"})

    assert cli(["ssh", "register"]).exit_code == 1


def test_ssh_register_of_a_key_without_its_public_file_exits_1(
    tmp_path: Path, cli: Callable[..., Any]
) -> None:
    """A private key file with no `.pub` beside it cannot be registered."""
    priv = tmp_path / "custom_priv"
    priv.touch()

    assert cli(["ssh", "register", "--key-file", str(priv)]).exit_code == 1


def test_ssh_register_that_github_refuses_exits_1(
    tmp_path: Path,
    cli: Callable[..., Any],
    config: Callable[..., Path],
    github_api: GitHubApiFake,
) -> None:
    """A registration error from GitHub stops the command with exit status 1."""
    priv = tmp_path / "custom_priv"
    priv.touch()
    (tmp_path / "custom_priv.pub").write_text("ssh-ed25519 AAAA", encoding="utf-8")
    config(ssh={"key_prefix": "devops-cli"})
    refusal = {"message": "Validation Failed", "errors": [{"message": "key is invalid"}]}
    github_api.route("POST", "/user/keys", github_json(refusal, status=422))
    github_api.route("GET", "/user/keys", github_json([]))

    assert cli(["ssh", "register", "--key-file", str(priv)]).exit_code == 1


@pytest.mark.parametrize(
    ("today", "message"),
    [
        pytest.param(datetime(2026, 8, 25, 12, tzinfo=UTC), "5 days remaining", id="warning"),
        pytest.param(datetime(2026, 9, 9, 12, tzinfo=UTC), "overdue by 10 days", id="overdue"),
    ],
)
def test_ssh_status_key_age_buckets(
    tmp_path: Path,
    cli: Callable[..., Any],
    config: Callable[..., Path],
    clock: ClockFake,
    today: datetime,
    message: str,
) -> None:
    """A key 85 days old has 5 days left of a 90-day rotation, and one 100 days old is overdue."""
    _write_key_pair(tmp_path, "devops-cli-id_ed25519-20260601")
    config(ssh={"key_dir": str(tmp_path), "key_prefix": "devops-cli", "rotation_days": 90})
    clock.move_to(today)

    result = cli(["ssh", "status"])

    assert (result.exit_code, message in _squash(result.output)) == (0, True)


def test_ssh_audit_key_age_buckets(
    tmp_path: Path, cli: Callable[..., Any], config: Callable[..., Path], clock: ClockFake
) -> None:
    """Verify ssh audit output with multiple managed key ages."""
    clock.move_to(datetime(2026, 9, 10, 12, tzinfo=UTC))
    for age in (110, 95, 85, 10):
        key_date = date(2026, 9, 10) - timedelta(days=age)
        _write_key_pair(tmp_path, f"devops-cli-id_ed25519-{key_date:%Y%m%d}")
    config(ssh={"key_dir": str(tmp_path), "key_prefix": "devops-cli", "rotation_days": 90})

    assert cli(["ssh", "audit"]).exit_code == 0


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

    # Pre-create files with insecure permissions: a world-readable private key, which OpenSSH
    # refuses as too open, and a world-writable public key
    k_path.write_text("old_insecure_private_key")
    os.chmod(k_path, 0o644)
    pub_path.write_text("old_public_key")
    os.chmod(pub_path, 0o666)  # nosec B103  # a world-writable key regeneration must clamp

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
    assert find_newest_key(tmp_path, prefix="nonexistent") is None

    # list_managed_keys_info with prefix
    info_a = list_managed_keys_info(tmp_path, prefix="proj-a")
    assert len(info_a) == 1
    assert info_a[0].path == k_proj_a

    # Non-directory path returns empty list without raising NotADirectoryError
    regular_file = tmp_path / "not_a_dir.txt"
    regular_file.write_text("just a file", encoding="utf-8")
    assert list_managed_keys(regular_file) == []


def test_ssh_register_honors_prefix_setting_and_option(
    tmp_path: Path,
    cli: Callable[..., Any],
    config: Callable[..., Path],
    github_api: GitHubApiFake,
    global_git_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify devops ssh register and list commands honor settings.ssh.key_prefix and --prefix flag."""
    k_prefixed = tmp_path / "custom-env-id_ed25519-20260901"
    k_prefixed.write_text("private")
    (tmp_path / "custom-env-id_ed25519-20260901.pub").write_text("ssh-ed25519 AAAA custom@env")

    # Add second key with different prefix
    k_other = tmp_path / "other-proj-id_ed25519-20260901"
    k_other.write_text("private-other")
    (tmp_path / "other-proj-id_ed25519-20260901.pub").write_text("ssh-ed25519 BBBB other@proj")

    config(ssh={"key_dir": str(tmp_path), "key_prefix": "custom-env", "rotation_days": 90})
    _accept_keys(github_api)
    monkeypatch.chdir(tmp_path)  # not a repository, so signing changes only the global config

    def last_title() -> str:
        return str(json.loads(github_api.sent[-1].content)["title"])

    # 1. Register with key_prefix setting (no --key-file or --title)
    res = cli(["ssh", "register"])
    assert (res.exit_code, last_title()) == (0, "custom-env-id_ed25519-20260901")

    # 2. Register with explicit --prefix option
    res_opt = cli(["ssh", "register", "--prefix", "custom-env"])
    assert (res_opt.exit_code, last_title()) == (0, "custom-env-id_ed25519-20260901")

    # 3. Status with prefix option
    res_stat = cli(["ssh", "status", "--prefix", "custom-env"])
    assert res_stat.exit_code == 0
    assert "custom-env-id_ed25519-20260901" in res_stat.output

    # 4. List without --prefix defaults to settings.ssh.key_prefix (shows custom-env, excludes other-proj)
    res_list_default = cli(["ssh", "list"])
    assert res_list_default.exit_code == 0
    assert "custom-env-id_ed25519-20260901" in res_list_default.output
    assert "other-proj-id_ed25519-20260901" not in res_list_default.output

    # 5. List with explicit --prefix other-proj (shows other-proj, excludes custom-env)
    res_list_other = cli(["ssh", "list", "--prefix", "other-proj"])
    assert res_list_other.exit_code == 0
    assert "other-proj-id_ed25519-20260901" in res_list_other.output
    assert "custom-env-id_ed25519-20260901" not in res_list_other.output


def test_ssh_empty_states_and_rotation_failure(
    tmp_path: Path,
    cli: Callable[..., Any],
    config: Callable[..., Path],
    github_api: GitHubApiFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify ssh commands when key dir is empty or rotation fails."""
    empty_dir = tmp_path / "empty_keys"
    empty_dir.mkdir()

    # 1. Rotate in empty dir
    res_rot = cli(["ssh", "rotate", "--key-dir", str(empty_dir)])
    assert res_rot.exit_code == 0
    assert "No managed SSH key with the prefix" in res_rot.output

    # 2. List in empty dir
    res_list = cli(["ssh", "list", "--key-dir", str(empty_dir)])
    assert res_list.exit_code == 0
    assert "No managed SSH key with the prefix" in res_list.output

    # 3. Status in empty dir
    res_stat = cli(["ssh", "status", "--key-dir", str(empty_dir)])
    assert res_stat.exit_code == 0
    assert "No managed SSH key with the prefix" in res_stat.output

    # 4. Rotation with failed GitHub registration cleanup
    old_key = tmp_path / "devops-cli-id_ed25519-20240101"
    old_key.write_text("old_private")
    (tmp_path / "devops-cli-id_ed25519-20240101.pub").write_text("ssh-ed25519 AAA old@test")
    config(ssh={"key_dir": str(tmp_path), "key_prefix": "devops-cli", "rotation_days": 30})
    refusal = {"message": "API timeout for token ghp_secret1234567890123456789012345678901234"}
    github_api.route("POST", "/user/keys", github_json(refusal, status=422))
    github_api.route("GET", "/user/keys", github_json([]))
    monkeypatch.chdir(tmp_path)

    res_rot_fail = cli(["ssh", "rotate", "--force"])
    assert res_rot_fail.exit_code == 0
    assert "registration failed" in res_rot_fail.output
    assert "ghp_secret" not in res_rot_fail.output
    assert "Check your GitHub token and network connectivity" in res_rot_fail.output


def test_a_rotation_github_refuses_removes_the_new_key(
    tmp_path: Path,
    github_api: GitHubApiFake,
    cli: Callable[..., Any],
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The GitHub session registers the new key, and GitHub refuses its signing key with a 422
    the listing does not confirm: rotate warns, removes the key it generated and exits 0 (#983)."""
    old_key = tmp_path / "devops-cli-id_ed25519-20240101"
    old_key.write_text("old_private")
    (tmp_path / "devops-cli-id_ed25519-20240101.pub").write_text("ssh-ed25519 AAA old@test")
    github_api.route("POST", "/user/keys", github_json({"id": 1}, status=201))
    refusal = {"message": "Validation Failed", "errors": [{"message": "key is already in use"}]}
    github_api.route("POST", "/user/ssh_signing_keys", github_json(refusal, status=422))
    github_api.route("GET", "/user/ssh_signing_keys", github_json([]))
    config(ssh={"key_dir": str(tmp_path), "key_prefix": "devops-cli", "rotation_days": 30})
    monkeypatch.chdir(tmp_path)

    result = cli(["ssh", "rotate", "--force"])

    assert (
        result.exit_code,
        "registration failed" in result.output,
        sorted(path.name for path in tmp_path.glob("*id_ed25519*")),
    ) == (0, True, ["devops-cli-id_ed25519-20240101", "devops-cli-id_ed25519-20240101.pub"])


def test_a_rotation_github_answers_with_a_404_warns_with_the_scope_command_and_removes_the_new_key(
    tmp_path: Path,
    github_api: GitHubApiFake,
    cli: Callable[..., Any],
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GitHub answers a token without the key scope with a 404, and rotate's warning gives the
    command that adds the scopes, then removes the key it generated."""
    old_key = tmp_path / "devops-cli-id_ed25519-20240101"
    old_key.write_text("old_private")
    (tmp_path / "devops-cli-id_ed25519-20240101.pub").write_text("ssh-ed25519 AAA old@test")
    github_api.route("POST", "/user/keys", github_json({"message": "Not Found"}, status=404))
    config(ssh={"key_dir": str(tmp_path), "key_prefix": "devops-cli", "rotation_days": 30})
    monkeypatch.chdir(tmp_path)

    result = cli(["ssh", "rotate", "--force"])

    assert (
        result.exit_code,
        "gh auth refresh -h github.com -s admin:public_key,write:ssh_signing_key"
        in " ".join(result.output.split()),
        sorted(path.name for path in tmp_path.glob("*id_ed25519*")),
    ) == (0, True, ["devops-cli-id_ed25519-20240101", "devops-cli-id_ed25519-20240101.pub"])


def test_a_devcontainer_json_that_does_not_parse_falls_back_to_the_directory_name(
    tmp_path: Path,
) -> None:
    """With no prefix setting and a devcontainer.json that is not JSON, the key prefix is the
    workspace directory's name."""
    from devops_cli.crypto.ssh_keys import get_ssh_key_prefix

    dev_dir = tmp_path / "bad_devcontainer"
    dev_cfg = dev_dir / ".devcontainer"
    dev_cfg.mkdir(parents=True)
    (dev_cfg / "devcontainer.json").write_text("INVALID JSON // comment", encoding="utf-8")

    assert get_ssh_key_prefix(dev_dir) == "bad_devcontainer"


def test_a_managed_key_name_with_an_empty_prefix_has_no_leading_dash() -> None:
    """An empty prefix gives the bare key type and date."""
    from devops_cli.crypto.ssh_keys import format_managed_key_filename

    assert format_managed_key_filename(prefix="", key_date=date(2026, 9, 1)) == (
        "id_ed25519-20260901"
    )


@pytest.mark.parametrize(
    ("key_name", "prefix"),
    [
        pytest.param("unmanaged_rsa_key", None, id="unmanaged"),
        pytest.param("my-prefix-id_ed25519-20260901", "my-prefix", id="managed"),
    ],
)
def test_the_prefix_of_a_key_name_is_read_only_from_a_managed_name(
    key_name: str, prefix: str | None
) -> None:
    """A managed key name gives its prefix, and any other name gives none."""
    from devops_cli.crypto.ssh_keys import parse_key_prefix

    assert parse_key_prefix(Path(key_name)) == prefix


def test_crypto_ssh_keys_devcontainer_config_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify get_ssh_key_prefix resolves key_prefix from .devcontainer/config.yaml and ancestors."""
    from devops_cli.config.settings import _find_project_config_path
    from devops_cli.crypto.ssh_keys import get_ssh_key_prefix

    # 1. Project with .devcontainer/config.yaml having ssh.key_prefix
    proj_dir = tmp_path / "gdot-local-dev"
    dev_dir = proj_dir / ".devcontainer"
    dev_dir.mkdir(parents=True)
    (dev_dir / "config.yaml").write_text("ssh:\n  key_prefix: gdot-local-dev\n", encoding="utf-8")

    sub_dir = proj_dir / "repos" / "gdot-network" / "meraki-prom-exporter"
    sub_dir.mkdir(parents=True)

    # Resolving from project root
    assert get_ssh_key_prefix(proj_dir) == "gdot-local-dev"
    # Resolving from submodule/subdirectory
    assert get_ssh_key_prefix(sub_dir) == "gdot-local-dev"

    # 2. Project with root-level key_prefix in config.yaml
    root_proj = tmp_path / "root-proj"
    root_proj.mkdir()
    (root_proj / "config.yaml").write_text("key_prefix: custom-root-prefix\n", encoding="utf-8")
    assert get_ssh_key_prefix(root_proj) == "custom-root-prefix"

    # 3. Verify _find_project_config_path detects .devcontainer/config.yaml
    monkeypatch.delenv("DEVOPS_CLI_CONFIG", raising=False)
    found = _find_project_config_path(base_dir=sub_dir)
    assert found == (dev_dir / "config.yaml").resolve()


_PROJECT_PREFIX = "devops-cli"
_PROJECT_KEY = "devops_cli-id_ed25519-20260831"
_OTHER_PROJECT_KEYS = ["alpha-id_ed25519-20260901", "beta_svc-id_ed25519-20260915"]
_ALL_KEY_NAMES = [_PROJECT_KEY, *_OTHER_PROJECT_KEYS]
_GENERATE_TIP = "devops ssh generate"


def _write_key_pair(key_dir: Path, name: str) -> str:
    """Write the private and the public file of the key `name`; return the public key line."""
    public_line = f"ssh-ed25519 PUBLIC-{name} user@example.com"
    (key_dir / name).write_text("private", encoding="utf-8")
    (key_dir / f"{name}.pub").write_text(public_line, encoding="utf-8")
    return public_line


@pytest.fixture
def global_git_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The global git config of the test: a file under `tmp_path`, which `git config --global`
    writes instead of the one in the home directory that all tests of a worker share. Without it,
    `register` and `rotate` turn on commit signing for each later test that runs `git commit`."""
    config_file = tmp_path / "global-gitconfig"
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config_file))
    return config_file


@pytest.fixture
def key_dir_of_three_projects(
    tmp_path: Path, config: Callable[..., Path], global_git_config: Path
) -> Path:
    """A key directory with the key of this project, spelled with an underscore, and the newer
    keys of two other projects. The settings give the prefix `devops-cli`, spelled with a hyphen."""
    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    for name in _ALL_KEY_NAMES:
        _write_key_pair(key_dir, name)
    config(ssh={"key_dir": str(key_dir), "key_prefix": _PROJECT_PREFIX})
    return key_dir


@pytest.fixture
def key_dir_of_other_projects(tmp_path: Path, config: Callable[..., Path]) -> Path:
    """A key directory that holds the keys of two other projects and none of this project."""
    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    for name in _OTHER_PROJECT_KEYS:
        _write_key_pair(key_dir, name)
    config(ssh={"key_dir": str(key_dir), "key_prefix": _PROJECT_PREFIX})
    return key_dir


def _keys_named_in(output: str) -> list[str]:
    """The managed keys of the test directories that `output` names, in a fixed order."""
    return [name for name in _ALL_KEY_NAMES if name in output]


def _squash(output: str) -> str:
    """The output with each run of white space as one space, so a wrapped message compares whole."""
    return " ".join(output.split())


@pytest.mark.parametrize("prefix", ["devops-cli", "devops_cli"])
def test_a_prefix_matches_the_keys_of_both_separator_spellings(tmp_path: Path, prefix: str) -> None:
    """A hyphen and an underscore in a prefix are the same: the prefix `devops-cli` and the
    prefix `devops_cli` each match the key of either spelling and no key of another project."""
    names = [_PROJECT_KEY, "devops-cli-id_ed25519-20261001", *_OTHER_PROJECT_KEYS]
    for name in names:
        _write_key_pair(tmp_path, name)
    assert (
        sorted(path.name for path in list_managed_keys(tmp_path, prefix=prefix)),
        find_newest_key(tmp_path, prefix=prefix),
    ) == (sorted(names[:2]), tmp_path / "devops-cli-id_ed25519-20261001")


def test_a_prefix_with_no_key_finds_no_key_and_never_the_key_of_another_project(
    tmp_path: Path,
) -> None:
    for name in (*_OTHER_PROJECT_KEYS, "id_ed25519-20260801"):
        _write_key_pair(tmp_path, name)
    assert (
        list_managed_keys(tmp_path, prefix=_PROJECT_PREFIX),
        find_newest_key(tmp_path, prefix=_PROJECT_PREFIX),
    ) == ([], None)


def test_the_empty_prefix_matches_only_the_keys_without_a_prefix(tmp_path: Path) -> None:
    for name in (*_OTHER_PROJECT_KEYS, "id_ed25519-20260801"):
        _write_key_pair(tmp_path, name)
    assert list_managed_keys(tmp_path, prefix="") == [tmp_path / "id_ed25519-20260801"]


def test_list_shows_only_the_keys_of_the_project_prefix(
    key_dir_of_three_projects: Path, cli: Callable[..., Any]
) -> None:
    result = cli("ssh", "list")
    assert (result.exit_code, _keys_named_in(result.output)) == (0, [_PROJECT_KEY])


def test_list_with_all_shows_the_keys_of_every_project(
    key_dir_of_three_projects: Path, cli: Callable[..., Any]
) -> None:
    result = cli("ssh", "list", "--all")
    assert (result.exit_code, _keys_named_in(result.output)) == (
        0,
        _ALL_KEY_NAMES,
    )


@pytest.mark.parametrize("dry_run_env", [{}, {"DEVOPS_CLI_DRY_RUN": "true"}])
def test_list_refuses_all_together_with_a_prefix(
    key_dir_of_three_projects: Path, cli: Callable[..., Any], dry_run_env: dict[str, str]
) -> None:
    """A dry run refuses the same arguments as a run, and prints no plan for them."""
    result = cli("ssh", "list", "--all", "--prefix", "alpha", env=dry_run_env)
    assert (
        result.exit_code,
        _keys_named_in(result.output),
        "Use '--all' or '--prefix'. Do not use both." in _squash(result.output),
    ) == (2, [], True)


def test_list_of_a_project_with_no_key_names_the_prefix_and_never_shows_other_projects(
    key_dir_of_other_projects: Path, cli: Callable[..., Any]
) -> None:
    result = cli("ssh", "list")
    output = _squash(result.output)
    assert (
        result.exit_code,
        _keys_named_in(output),
        f"prefix '{_PROJECT_PREFIX}'" in output,
        _GENERATE_TIP in output,
        "--all" in output,
    ) == (0, [], True, True, True)


def test_list_with_all_of_a_directory_with_no_managed_key_names_the_expected_file_names(
    tmp_path: Path, config: Callable[..., Path], cli: Callable[..., Any]
) -> None:
    config(ssh={"key_dir": str(tmp_path), "key_prefix": _PROJECT_PREFIX})
    result = cli("ssh", "list", "--all")
    assert (
        result.exit_code,
        "(expected: PREFIX-id_ed25519-YYYYMMDD or id_ed25519-YYYYMMDD)" in _squash(result.output),
    ) == (0, True)


def _accept_keys(github_api: GitHubApiFake) -> None:
    """Make the GitHub fake accept a key at both endpoints that `register` and `rotate` use."""
    for endpoint in ("/user/keys", "/user/ssh_signing_keys"):
        github_api.route("POST", endpoint, github_json({"id": 1}, status=201))


def test_register_adds_the_key_of_the_project_to_github(
    key_dir_of_three_projects: Path,
    global_git_config: Path,
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(key_dir_of_three_projects)
    _accept_keys(github_api)
    result = cli("ssh", "register")
    project_line = (key_dir_of_three_projects / f"{_PROJECT_KEY}.pub").read_text(encoding="utf-8")
    signing_config = global_git_config.read_text(encoding="utf-8")
    assert (
        result.exit_code,
        [json.loads(sent.content)["key"] for sent in github_api.sent],
        [str(key_dir_of_three_projects / name) in signing_config for name in _ALL_KEY_NAMES],
    ) == (0, [project_line, project_line], [True, False, False])


@pytest.mark.parametrize(
    ("key_name", "expected_title"),
    [
        (None, _PROJECT_KEY),
        ("id_ed25519-20260801", f"{_PROJECT_PREFIX}-id_ed25519-20260801"),
        ("id_rsa", f"{_PROJECT_PREFIX}-id_rsa"),
    ],
)
def test_register_titles_a_key_with_its_own_prefix_or_with_the_prefix_of_the_project(
    key_dir_of_three_projects: Path,
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
    monkeypatch: pytest.MonkeyPatch,
    key_name: str | None,
    expected_title: str,
) -> None:
    """The project key `devops_cli-id_ed25519-20260831` keeps its own name as the title, though the
    prefix `devops-cli` spells the separator in another way. A key with no prefix, managed or not,
    gets the prefix of the project."""
    monkeypatch.chdir(key_dir_of_three_projects)
    _accept_keys(github_api)
    key_options: list[str] = []
    if key_name is not None:
        _write_key_pair(key_dir_of_three_projects, key_name)
        key_options = ["--key-file", str(key_dir_of_three_projects / key_name)]
    result = cli("ssh", "register", *key_options)
    assert (result.exit_code, [json.loads(sent.content)["title"] for sent in github_api.sent]) == (
        0,
        [expected_title, expected_title],
    )


def test_register_of_a_project_with_no_key_sends_nothing_and_points_to_generate(
    key_dir_of_other_projects: Path, cli: Callable[..., Any], github_api: GitHubApiFake
) -> None:
    result = cli("ssh", "register")
    output = _squash(result.output)
    assert (result.exit_code, github_api.requested, f"prefix '{_PROJECT_PREFIX}'" in output) == (
        1,
        [],
        True,
    )
    assert _GENERATE_TIP in output


def test_rotate_replaces_the_key_of_the_project_and_leaves_the_keys_of_other_projects(
    key_dir_of_three_projects: Path,
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(key_dir_of_three_projects)
    _accept_keys(github_api)
    before = {path.name for path in key_dir_of_three_projects.iterdir()}
    result = cli("ssh", "rotate", "--force")
    created = {path.name for path in key_dir_of_three_projects.iterdir()} - before
    assert (result.exit_code, sorted(created), _keys_named_in(_squash(result.output))) == (
        0,
        sorted(
            f"{_PROJECT_PREFIX}-id_ed25519-{date.today():%Y%m%d}{suffix}" for suffix in ("", ".pub")
        ),
        [_PROJECT_KEY],
    )
    assert {path.name for path in key_dir_of_three_projects.iterdir()} >= before


def test_rotate_of_a_project_with_no_key_changes_nothing_and_points_to_generate(
    key_dir_of_other_projects: Path, cli: Callable[..., Any], github_api: GitHubApiFake
) -> None:
    before = sorted(path.name for path in key_dir_of_other_projects.iterdir())
    result = cli("ssh", "rotate", "--force")
    output = _squash(result.output)
    assert (
        result.exit_code,
        sorted(path.name for path in key_dir_of_other_projects.iterdir()),
        github_api.requested,
        f"prefix '{_PROJECT_PREFIX}'" in output,
        _GENERATE_TIP in output,
    ) == (0, before, [], True, True)


def test_status_shows_the_key_of_the_project(
    key_dir_of_three_projects: Path, cli: Callable[..., Any]
) -> None:
    result = cli("ssh", "status")
    assert (result.exit_code, _keys_named_in(result.output)) == (0, [_PROJECT_KEY])


def test_status_of_a_project_with_no_key_names_the_prefix_and_points_to_generate(
    key_dir_of_other_projects: Path, cli: Callable[..., Any]
) -> None:
    result = cli("ssh", "status")
    output = _squash(result.output)
    assert (
        result.exit_code,
        _keys_named_in(output),
        f"prefix '{_PROJECT_PREFIX}'" in output,
        _GENERATE_TIP in output,
    ) == (0, [], True, True)


def test_git_signing_points_the_global_config_and_a_repository_at_the_key(
    tmp_path: Path, global_git_config: Path
) -> None:
    """`configure_git_signing` sets SSH commit signing with the key in the global git config and
    in the local config of the repository it is given."""
    from devops_cli.crypto.ssh_keys import configure_git_signing

    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    key = tmp_path / "devops-cli-id_ed25519-20260901"

    configure_git_signing(key, repo)

    def read(*where: str) -> list[str]:
        return [
            run_subprocess([BIN_GIT, *where, "--get", name], quiet=True).stdout.strip()
            for name in ("gpg.format", "user.signingkey", "commit.gpgsign")
        ]

    expected = ["ssh", str(key), "true"]
    assert (read("config", "--global"), read("-C", str(repo), "config", "--local")) == (
        expected,
        expected,
    )


# =============================================================================
# Dry runs (#2258)
# =============================================================================


def _plan_lines(output: str) -> list[str]:
    """The numbered lines of a request plan, without their numbers."""
    import re

    return [line.split(". ", 1)[1] for line in output.splitlines() if re.match(r"^\s*\d+\. ", line)]


def test_ssh_dry_run_classes() -> None:
    """Each ssh command carries the dry-run class of what it reaches."""
    from devops_cli.commands import ssh
    from devops_cli.dry_run.decorator import get_dry_run_class

    for callback in (ssh.generate, ssh.list_keys, ssh.status):
        assert get_dry_run_class(callback) == "no-external-request"
    for callback in (ssh.register, ssh.rotate):
        assert get_dry_run_class(callback) == "request-plan"


@pytest.mark.parametrize("command", ["list", "audit", "status"])
def test_ssh_read_commands_run_under_the_dry_run_flag(
    key_dir_of_three_projects: Path,
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
    command: str,
) -> None:
    """A command that only reads the key directory runs normally under `devops --dry-run`."""
    result = cli("--dry-run", "ssh", command)

    assert (result.exit_code, _keys_named_in(result.output)) == (0, [_PROJECT_KEY])
    assert "action" not in result.output
    assert github_api.requested == []


@pytest.mark.parametrize("command", ["list", "audit", "status"])
def test_ssh_read_commands_have_no_dry_run_option(cli: Callable[..., Any], command: str) -> None:
    """A command that makes no request has no preview to offer."""
    result = cli("ssh", command, "--dry-run")

    assert result.exit_code == 2
    assert "No such option" in result.output


@pytest.mark.parametrize(
    "argv",
    [
        ["ssh", "generate", "--key-dir", "{key_dir}", "--dry-run"],
        ["--dry-run", "ssh", "generate", "--key-dir", "{key_dir}"],
    ],
)
def test_ssh_generate_dry_run_writes_no_key(
    tmp_path: Path,
    cli: Callable[..., Any],
    config: Callable[..., Path],
    clock: ClockFake,
    argv: list[str],
) -> None:
    """A dry run names the key that the run would write, and writes nothing."""
    clock.move_to(datetime(2026, 1, 1, 12, tzinfo=UTC))
    config(ssh={"key_prefix": "devops-cli"})
    key_dir = tmp_path / "keys"

    result = cli([arg.format(key_dir=key_dir) for arg in argv])

    assert result.exit_code == 0, result.output
    assert f"Would write the key {key_dir / 'devops-cli-id_ed25519-20260101'}" in _squash(
        result.output
    )
    assert not key_dir.exists()


def test_ssh_generate_dry_run_refuses_a_key_that_exists(
    tmp_path: Path, cli: Callable[..., Any], config: Callable[..., Path], clock: ClockFake
) -> None:
    """A dry run refuses the key of today that exists, as a run does."""
    clock.move_to(datetime(2026, 1, 1, 12, tzinfo=UTC))
    config(ssh={"key_dir": str(tmp_path), "key_prefix": "devops-cli"})
    (tmp_path / "devops-cli-id_ed25519-20260101").touch()

    assert cli(["ssh", "generate", "--dry-run"]).exit_code == 1


@pytest.mark.parametrize(
    "argv",
    [["ssh", "register", "--dry-run"], ["--dry-run", "ssh", "register"]],
)
def test_ssh_register_dry_run_lists_the_requests(
    key_dir_of_three_projects: Path,
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
    git_fake: GitFake,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
) -> None:
    """A dry run sends GitHub nothing, starts no process, and lists the requests of the run."""
    monkeypatch.chdir(key_dir_of_three_projects)
    key = key_dir_of_three_projects / _PROJECT_KEY

    result = cli(argv)

    assert result.exit_code == 0, result.output
    assert (github_api.requested, git_fake.calls) == ([], [])
    lines = _plan_lines(result.output)
    assert lines[0] == "POST /user/keys"
    assert lines[1].startswith("GET /user/keys  [only if GitHub answers the POST /user/keys")
    assert lines[2] == "POST /user/ssh_signing_keys"
    assert lines[3].startswith("GET /user/ssh_signing_keys  [only if")
    assert lines[4:] == [
        "git config --global gpg.format ssh",
        f"git config --global user.signingkey {key}",
        "git config --global commit.gpgsign true",
    ]
    assert f'"title": "{_PROJECT_KEY}", "key": "<public key>"' in result.output


@pytest.mark.parametrize(
    "argv",
    [["ssh", "rotate", "--dry-run"], ["--dry-run", "ssh", "rotate"]],
)
def test_ssh_rotate_dry_run_writes_no_key_and_lists_the_requests(
    key_dir_of_three_projects: Path,
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
    git_fake: GitFake,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
) -> None:
    """A dry run writes no new key, sends nothing, and lists the requests with their condition."""
    monkeypatch.chdir(key_dir_of_three_projects)
    before = sorted(path.name for path in key_dir_of_three_projects.iterdir())

    result = cli(argv)

    assert result.exit_code == 0, result.output
    assert (github_api.requested, git_fake.calls) == ([], [])
    assert sorted(path.name for path in key_dir_of_three_projects.iterdir()) == before
    lines = _plan_lines(result.output)
    assert [line.split("  [")[0] for line in lines[:4]] == [
        "POST /user/keys",
        "GET /user/keys",
        "POST /user/ssh_signing_keys",
        "GET /user/ssh_signing_keys",
    ]
    assert all(
        "the newest key is older than the rotation age or --force is set" in line for line in lines
    )


def test_ssh_register_runs_the_requests_of_its_plan(
    key_dir_of_three_projects: Path,
    cli: Callable[..., Any],
    github_api: GitHubApiFake,
    git_fake: GitFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real run sends the requests of the plan that have no condition, in the same order,
    and runs the `git config` commands of the plan."""
    monkeypatch.chdir(key_dir_of_three_projects)
    _accept_keys(github_api)
    lines = _plan_lines(cli("ssh", "register", "--dry-run").output)

    result = cli("ssh", "register")

    assert result.exit_code == 0, result.output
    unconditional = [line for line in lines if "[only if" not in line]
    assert [f"{sent.method} {sent.url.path}" for sent in github_api.sent] == [
        line for line in unconditional if not line.startswith("git ")
    ]
    assert [" ".join(call.argv) for call in git_fake.calls] == [
        line for line in unconditional if line.startswith("git ")
    ]
