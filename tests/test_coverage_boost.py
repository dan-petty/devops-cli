"""Focused unit tests to boost test coverage across core, config, audit, cleanup, git, ssh, scan, repos, k8s, tls, release, security, output, and workspace commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.k8s import app as k8s_app
from devops_cli.commands.release import app as release_app
from devops_cli.commands.repos import app as repos_app
from devops_cli.commands.scan import app as scan_app
from devops_cli.commands.ssh import app as ssh_app
from devops_cli.commands.tls import app as tls_app
from devops_cli.commands.workspace import (
    _is_safe_workspace_file,
    _load,
    _save,
)
from devops_cli.commands.workspace import (
    app as workspace_app,
)
from devops_cli.config.metadata import (
    _parse_python_version,
    get_version,
    load_project_metadata,
)
from devops_cli.core.audit import (
    _resolve_audit_log_dest,
    record_audit_event,
    stream_audit_records,
)
from devops_cli.core.cleanup import CleanupSummary, cleanup_data_tier
from devops_cli.core.repo import (
    find_repo_root,
    find_top_level_repo_root,
    is_ignored_by_git,
    list_repo_files,
    read_gitignore_patterns,
)
from devops_cli.github.client import GitHubClient, RepoInfo
from devops_cli.output.file_writer import (
    write_json_file,
    write_serialized_file,
    write_text_file,
    write_yaml_file,
)
from devops_cli.output.formatter import (
    format_location,
    format_output,
    format_serialized,
    format_yaml,
    render_table,
)
from devops_cli.security.checkov import run_checkov_scan
from devops_cli.security.dive import run_dive_scan
from devops_cli.security.kubeconform import (
    _run_native_fallback_k8s_validation,
    run_kubeconform_validation,
)
from devops_cli.security.pluto import run_pluto_scan
from devops_cli.security.popeye import run_popeye_scan
from devops_cli.security.semgrep import run_semgrep_scan
from devops_cli.security.tflint import (
    _run_native_fallback_tf_lint,
    run_tflint_scan,
)
from devops_cli.security.trivy import run_trivy_scan

runner = CliRunner()


def test_repo_info_model() -> None:
    info = RepoInfo(
        name="test",
        full_name="org/test",
        ssh_url="git@github.com:org/test.git",
        clone_url="https://github.com/org/test.git",
        private=True,
        fork=False,
        archived=False,
    )
    assert info.name == "test"
    assert info.private is True


def test_github_client_operations() -> None:
    mock_gh = MagicMock()
    mock_user = MagicMock()
    mock_user.login = "test-user"
    mock_key = MagicMock()
    mock_key.id = 1
    mock_key.title = "key1"
    mock_key.key = "ssh-ed25519 AAA..."
    mock_user.get_keys.return_value = [mock_key]
    mock_created_key = MagicMock()
    mock_created_key.id = 2
    mock_user.create_key.return_value = mock_created_key
    mock_gh.get_user.return_value = mock_user

    mock_repo = MagicMock()
    mock_repo.name = "repo1"
    mock_repo.full_name = "test-org/repo1"
    mock_repo.ssh_url = "git@github.com:test-org/repo1.git"
    mock_repo.clone_url = "https://github.com/test-org/repo1.git"
    mock_repo.private = False
    mock_repo.fork = False
    mock_repo.archived = False

    mock_org = MagicMock()
    mock_org.get_repos.return_value = [mock_repo]
    mock_gh.get_organization.return_value = mock_org

    with patch("github.Github", return_value=mock_gh):
        client = GitHubClient("token123")
        repos = client.get_org_repos("test-org")
        assert len(repos) == 1
        assert repos[0].name == "repo1"

        keys = client.get_user_ssh_keys()
        assert len(keys) == 1
        assert keys[0].id == 1

        new_key_id = client.add_user_ssh_key("new_key", "ssh-ed25519 AAA...")
        assert new_key_id == 2

        client.delete_user_ssh_key(1)
        mock_user.get_key.assert_called_with(1)

        _ = client.get_pull("test-org/repo1", 42)
        mock_gh.get_repo.assert_called_with("test-org/repo1")


def test_core_repo_find_roots(tmp_path: Path) -> None:
    sub = tmp_path / "a" / "b" / "c"
    sub.mkdir(parents=True)
    git_dir = tmp_path / "a" / ".git"
    git_dir.mkdir()

    root = find_repo_root(sub)
    assert root == tmp_path / "a"

    top_root = find_top_level_repo_root(sub)
    assert top_root == tmp_path / "a"


def test_core_repo_gitignore_and_files(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.tmp\nbuild/\n# comment\n", encoding="utf-8")

    patterns = read_gitignore_patterns(tmp_path)
    assert "*.tmp" in patterns
    assert "build/" in patterns

    (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "test.tmp").write_text("temp", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.bin").write_text("bin", encoding="utf-8")

    files = list_repo_files(tmp_path)
    file_names = [f.name for f in files]
    assert "app.py" in file_names
    assert is_ignored_by_git(tmp_path, tmp_path / "test.tmp") is True
    assert is_ignored_by_git(tmp_path, tmp_path / "app.py") is False


def test_output_file_writers(tmp_path: Path) -> None:
    json_path = tmp_path / "sub" / "data.json"
    write_json_file(json_path, {"status": "ok"})
    assert json_path.exists()
    assert '"status": "ok"' in json_path.read_text(encoding="utf-8")

    yaml_path = tmp_path / "sub" / "data.yaml"
    write_yaml_file(yaml_path, {"key": "value"})
    assert yaml_path.exists()
    assert "key: value" in yaml_path.read_text(encoding="utf-8")

    txt_path = tmp_path / "sub" / "notes.txt"
    write_text_file(txt_path, "First line\n", atomic=False)
    assert txt_path.read_text(encoding="utf-8") == "First line\n"

    ser_path = tmp_path / "sub" / "ser.json"
    write_serialized_file(ser_path, [{"name": "item1"}])
    assert ser_path.exists()


def test_audit_record_and_stream(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log_file = tmp_path / ".data" / "audit.jsonl"
    record = record_audit_event(
        command="devops test",
        status="SUCCESS",
        duration_ms=12.5,
        details={"key": "val"},
        log_file=log_file,
    )
    assert record.command == "devops test"
    assert log_file.exists()

    count = stream_audit_records("https://example.com/siem", log_file=log_file)
    assert count == 1

    count_empty = stream_audit_records("https://example.com/siem", log_file=tmp_path / "none.jsonl")
    assert count_empty == 0

    monkeypatch.setenv("DEVOPS_CLI_AUDIT_LOG_DEST", str(tmp_path / ".data" / "custom.jsonl"))
    monkeypatch.setattr("devops_cli.core.audit.CONST_DATA_DIR", tmp_path / ".data")
    dest = _resolve_audit_log_dest(None)
    assert dest == tmp_path / ".data" / "custom.jsonl"

    monkeypatch.setenv("DEVOPS_CLI_AUDIT_LOG_DEST", "/etc/passwd")
    with pytest.raises(ValueError, match="must be within"):
        _resolve_audit_log_dest(None)


def test_cleanup_data_tier(tmp_path: Path) -> None:
    data_dir = tmp_path / ".data"
    reviews_dir = data_dir / "reviews"
    reviews_dir.mkdir(parents=True)
    old_file = reviews_dir / "old_review.json"
    old_file.write_text("{}", encoding="utf-8")

    old_dir = reviews_dir / "old_session"
    old_dir.mkdir()
    (old_dir / "summary.md").write_text("old", encoding="utf-8")

    summary_dry = cleanup_data_tier(
        repo_root=tmp_path,
        older_than_seconds=-10,
        dry_run=True,
    )
    assert isinstance(summary_dry, CleanupSummary)
    assert summary_dry.dry_run is True
    assert len(summary_dry.pruned_files) > 0 or len(summary_dry.pruned_dirs) > 0
    assert old_file.exists()

    summary_live = cleanup_data_tier(
        repo_root=tmp_path,
        older_than_seconds=-10,
        dry_run=False,
    )
    assert summary_live.dry_run is False
    assert not old_file.exists()


def test_workspace_helpers_and_commands(tmp_path: Path) -> None:
    ws_file = tmp_path / "devops.code-workspace"
    data: dict[str, object] = {"folders": [{"path": "repos/a"}], "settings": {}}
    _save(ws_file, data)
    assert ws_file.exists()

    loaded = _load(ws_file)
    assert "folders" in loaded
    assert len(loaded["folders"]) >= 2

    assert _is_safe_workspace_file(ws_file) is True
    assert _is_safe_workspace_file(Path("/etc/passwd")) is False

    res = runner.invoke(workspace_app, ["clean", "--dry-run"])
    assert res.exit_code == 0


def test_ssh_commands_dry_run() -> None:
    with patch("devops_cli.dry_run.is_dry_run", return_value=True):
        res1 = runner.invoke(ssh_app, ["generate"])
        assert res1.exit_code == 0
        assert "generate_ed25519_ssh_key" in res1.output or "dry-run" in res1.output

        res2 = runner.invoke(ssh_app, ["register"])
        assert res2.exit_code == 0
        assert "register_ssh_key_on_github" in res2.output or "dry-run" in res2.output

        res3 = runner.invoke(ssh_app, ["rotate"])
        assert res3.exit_code == 0
        assert "rotate_ssh_keys" in res3.output or "dry-run" in res3.output

        res4 = runner.invoke(ssh_app, ["audit"])
        assert res4.exit_code == 0
        assert "audit_ssh_keys" in res4.output or "dry-run" in res4.output

        res5 = runner.invoke(ssh_app, ["status"])
        assert res5.exit_code == 0
        assert "get_ssh_key_status" in res5.output or "dry-run" in res5.output


def test_scan_commands_dry_run(tmp_path: Path) -> None:
    with (
        patch("devops_cli.security.trivy.run_trivy_scan", return_value=[]),
        patch("devops_cli.security.semgrep.run_semgrep_scan", return_value=[]),
        patch("devops_cli.security.gitleaks.run_gitleaks_scan", return_value=[]),
        patch("devops_cli.security.checkov.run_checkov_scan", return_value=[]),
    ):
        res_trivy = runner.invoke(scan_app, ["trivy", str(tmp_path), "--dry-run", "--json"])
        assert res_trivy.exit_code == 0

        res_secrets = runner.invoke(scan_app, ["secrets", str(tmp_path), "--dry-run", "--json"])
        assert res_secrets.exit_code == 0

        res_gitleaks = runner.invoke(scan_app, ["gitleaks", str(tmp_path), "--dry-run", "--json"])
        assert res_gitleaks.exit_code == 0

        res_semgrep = runner.invoke(scan_app, ["semgrep", str(tmp_path), "--dry-run", "--json"])
        assert res_semgrep.exit_code == 0

        res_sast = runner.invoke(scan_app, ["sast", str(tmp_path), "--dry-run", "--json"])
        assert res_sast.exit_code == 0

        res_checkov = runner.invoke(scan_app, ["checkov", str(tmp_path), "--dry-run", "--json"])
        assert res_checkov.exit_code == 0

        res_iac = runner.invoke(scan_app, ["iac", str(tmp_path), "--dry-run", "--json"])
        assert res_iac.exit_code == 0


def test_repos_commands_dry_run(tmp_path: Path) -> None:
    with patch("devops_cli.dry_run.is_dry_run", return_value=True):
        res_list = runner.invoke(repos_app, ["list", "--base-dir", str(tmp_path)])
        assert res_list.exit_code == 0

        res_sync = runner.invoke(repos_app, ["sync", "--base-dir", str(tmp_path)])
        assert res_sync.exit_code == 0


def test_k8s_commands_dry_run() -> None:
    with patch("devops_cli.dry_run.is_dry_run", return_value=True):
        res_status = runner.invoke(k8s_app, ["status"])
        assert res_status.exit_code == 0

        res_pods = runner.invoke(k8s_app, ["pods"])
        assert res_pods.exit_code == 0

        res_bootstrap = runner.invoke(k8s_app, ["bootstrap"])
        assert res_bootstrap.exit_code == 0

        res_deploy = runner.invoke(k8s_app, ["deploy-stack", "--dry-run"])
        assert res_deploy.exit_code == 0

        res_teardown = runner.invoke(k8s_app, ["teardown-stack", "--dry-run"])
        assert res_teardown.exit_code == 0


def test_tls_commands_dry_run() -> None:
    with patch("devops_cli.dry_run.is_dry_run", return_value=True):
        res_ca = runner.invoke(tls_app, ["ca", "--dry-run"])
        assert res_ca.exit_code == 0

        res_cert = runner.invoke(tls_app, ["cert", "example.com", "--dry-run"])
        assert res_cert.exit_code == 0

        res_k8s = runner.invoke(tls_app, ["enable-k8s", "--dry-run"])
        assert res_k8s.exit_code == 0


def test_release_commands_dry_run() -> None:
    with patch("devops_cli.dry_run.is_dry_run", return_value=True):
        res_status = runner.invoke(release_app, ["status"])
        assert res_status.exit_code == 0


def test_security_scanners_and_fallbacks(tmp_path: Path) -> None:
    tf_file = tmp_path / "main.tf"
    tf_file.write_text(
        'resource "aws_security_group" "allow_all" { cidr_blocks = ["0.0.0.0/0"] }\n',
        encoding="utf-8",
    )
    tf_findings = _run_native_fallback_tf_lint(tmp_path)
    assert len(tf_findings) >= 1

    tf_findings_scan = run_tflint_scan(tmp_path)
    assert isinstance(tf_findings_scan, list)

    k8s_file = tmp_path / "bad.yaml"
    k8s_file.write_text("foo: bar\n", encoding="utf-8")
    k8s_findings = _run_native_fallback_k8s_validation(tmp_path)
    assert len(k8s_findings) >= 1

    k8s_findings_scan = run_kubeconform_validation(tmp_path)
    assert isinstance(k8s_findings_scan, list)

    with patch("shutil.which", return_value=None):
        assert run_dive_scan("alpine:latest") == []
        assert run_pluto_scan(tmp_path) == []
        assert run_popeye_scan() == []
        assert run_trivy_scan(tmp_path) == []
        assert run_semgrep_scan(tmp_path) == []
        assert run_checkov_scan(tmp_path) == []


def test_config_metadata(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "test-pkg"\nversion = "1.0.0"\ndescription = "desc"\nrequires-python = ">=3.14"\n',
        encoding="utf-8",
    )
    meta = load_project_metadata(pyproject)
    assert meta.name == "test-pkg"
    assert meta.version == "1.0.0"
    assert get_version(pyproject) == "1.0.0"
    assert _parse_python_version(">=3.14.0") == "3.14.0"
    assert _parse_python_version("3.14") == "3.14"


def test_output_formatting() -> None:
    assert format_location("src/app.py", 10, 20) == "src/app.py:10-20"
    assert format_location("src/app.py", 10) == "src/app.py:10"
    assert format_location("src/app.py") == "src/app.py"

    yaml_str = format_yaml({"foo": "bar"})
    assert "foo: bar" in yaml_str

    ser_str = format_serialized({"a": 1}, format_type="yaml")
    assert "a: 1" in ser_str

    tbl = render_table("Title", [("Col1", "bold"), "Col2"], [["1", "2"]])
    assert tbl.title == "Title"

    out_json = format_output({"status": "ok"}, format_type="json")
    assert '"status": "ok"' in str(out_json)

    out_tbl = format_output(None, format_type="table", title="T", columns=["C1"], rows=[["V1"]])
    assert out_tbl is not None
