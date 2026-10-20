"""Unit tests for the live Argo CD diff and override report (#1343)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

from devops_cli.config.constants import (
    CONST_MAX_ERROR_DETAIL_LENGTH,
)
from devops_cli.k8s.argocd_live_report import (
    _find_repo_source_position,
    extract_live_tested_hosts,
    report_argocd_live_diff,
)


class FakeRunner:
    """Fake subprocess runner recording commands and environments."""

    def __init__(
        self,
        *,
        diff_code: int = 0,
        diff_stdout: str = "",
        diff_stderr: str = "",
        app_json: str = "{}",
    ) -> None:
        self.calls: list[tuple[list[str], dict[str, str]]] = []
        self.diff_code = diff_code
        self.diff_stdout = diff_stdout
        self.diff_stderr = diff_stderr
        self.app_json = app_json

    def __call__(
        self,
        cmd: list[str],
        *,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        env: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        current_env = dict(env) if env is not None else {}
        self.calls.append((list(cmd), current_env))
        if "diff" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=self.diff_code,
                stdout=self.diff_stdout,
                stderr=self.diff_stderr,
            )
        if "get" in cmd:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout=self.app_json,
                stderr="",
            )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")


def test_missing_argocd_url_warns_and_continues(tmp_path: Path) -> None:
    """When argocd.url is not configured, one warning names what is missing and report skips."""
    fake_runner = FakeRunner()
    warnings: list[str] = []

    with (
        patch(
            "devops_cli.k8s.argocd_live_report.resolve_argocd_server_and_token",
            return_value=(None, "mock-token"),
        ),
        patch("shutil.which", return_value="/usr/local/bin/argocd"),
        patch(
            "devops_cli.k8s.argocd_live_report.print_warning",
            side_effect=lambda msg, *a, **kw: warnings.append(msg),
        ),
    ):
        result = report_argocd_live_diff(tmp_path, runner=fake_runner)

    assert (
        result,
        fake_runner.calls,
        len(warnings),
        "argocd.url" in warnings[0],
    ) == ([], [], 1, True)


def test_missing_argocd_token_warns_and_continues(tmp_path: Path) -> None:
    """When Argo CD token is missing, one warning names token and report skips."""
    fake_runner = FakeRunner()
    warnings: list[str] = []

    with (
        patch(
            "devops_cli.k8s.argocd_live_report.resolve_argocd_server_and_token",
            return_value=("https://example.com", None),
        ),
        patch("shutil.which", return_value="/usr/local/bin/argocd"),
        patch(
            "devops_cli.k8s.argocd_live_report.print_warning",
            side_effect=lambda msg, *a, **kw: warnings.append(msg),
        ),
    ):
        result = report_argocd_live_diff(tmp_path, runner=fake_runner)

    assert (
        result,
        fake_runner.calls,
        len(warnings),
        "token" in warnings[0].lower(),
    ) == ([], [], 1, True)


def test_missing_argocd_binary_warns_and_continues(tmp_path: Path) -> None:
    """When argocd CLI is not installed, one warning names argocd and report skips."""
    fake_runner = FakeRunner()
    warnings: list[str] = []

    with (
        patch(
            "devops_cli.k8s.argocd_live_report.resolve_argocd_server_and_token",
            return_value=("https://example.com", "mock-token"),
        ),
        patch("shutil.which", return_value=None),
        patch(
            "devops_cli.k8s.argocd_live_report.print_warning",
            side_effect=lambda msg, *a, **kw: warnings.append(msg),
        ),
    ):
        result = report_argocd_live_diff(tmp_path, runner=fake_runner)

    assert (
        result,
        fake_runner.calls,
        len(warnings),
        "argocd" in warnings[0].lower(),
    ) == ([], [], 1, True)


def test_find_repo_source_position() -> None:
    """Multi-source git position is detected correctly (1-based index)."""
    sources = [
        {"chart": "traefik", "repoURL": "https://traefik.github.io/charts"},
        {"repoURL": "https://github.com/dan-petty/devops-cli", "path": "k8s/ingress"},
    ]
    pos = _find_repo_source_position(sources, "https://github.com/dan-petty/devops-cli")
    assert pos == 2

    # When no match by repoURL, fallback to source with path and no chart
    sources_alt = [
        {"chart": "traefik", "repoURL": "https://traefik.github.io/charts"},
        {"path": "k8s/ingress"},
    ]
    pos_alt = _find_repo_source_position(sources_alt, "https://github.com/dan-petty/devops-cli")
    assert pos_alt == 2


def test_extract_live_tested_hosts() -> None:
    """JSON patches with op: test are extracted into tested host names."""
    app_data = {
        "spec": {
            "source": {
                "kustomize": {
                    "patches": [
                        {
                            "target": {"kind": "Ingress"},
                            "patch": '[{"op": "test", "path": "/spec/rules/0/host", "value": "devops.example.com"}, {"op": "replace", "path": "/spec/rules/0/host", "value": "devops.custom.internal"}]',
                        }
                    ]
                }
            }
        }
    }
    hosts = extract_live_tested_hosts(app_data)
    assert hosts == {"devops.example.com"}


def test_live_diff_invocation_and_auth_token_safety(tmp_path: Path) -> None:
    """Diff runs with --grpc-web, multi-source by git position, and token only in env."""
    apps_dir = tmp_path / "k8s" / "argocd" / "apps"
    apps_dir.mkdir(parents=True)

    # Single-source application
    (apps_dir / "single.yaml").write_text(
        "apiVersion: argoproj.io/v1alpha1\n"
        "kind: Application\n"
        "metadata:\n"
        "  name: single\n"
        "spec:\n"
        "  source:\n"
        "    repoURL: https://github.com/dan-petty/devops-cli\n"
        "    path: k8s/apps/single\n",
        encoding="utf-8",
    )

    # Multi-source application
    (apps_dir / "multi.yaml").write_text(
        "apiVersion: argoproj.io/v1alpha1\n"
        "kind: Application\n"
        "metadata:\n"
        "  name: multi\n"
        "spec:\n"
        "  sources:\n"
        "    - chart: mychart\n"
        "      repoURL: https://charts.example.com\n"
        "    - repoURL: https://github.com/dan-petty/devops-cli\n"
        "      path: k8s/apps/multi\n",
        encoding="utf-8",
    )

    fake_runner = FakeRunner()
    mock_token = "secret-argo-bearer-token-12345"

    with (
        patch(
            "devops_cli.k8s.argocd_live_report.resolve_argocd_server_and_token",
            return_value=("https://argocd.example.com", mock_token),
        ),
        patch("shutil.which", return_value="/usr/local/bin/argocd"),
    ):
        report = report_argocd_live_diff(
            tmp_path,
            sha="abcdef0123456789abcdef0123456789abcdef01",
            runner=fake_runner,
        )

    # Both apps should be processed
    assert len(report) >= 2

    # Check diff calls made by runner
    diff_calls = [cmd for cmd, env in fake_runner.calls if "diff" in cmd]
    assert len(diff_calls) == 2

    for cmd, env in fake_runner.calls:
        # Token MUST NEVER appear anywhere in argv
        assert mock_token not in " ".join(cmd)
        # Token MUST appear in environment
        assert env.get("ARGOCD_AUTH_TOKEN") == mock_token

    # Verify single-source call structure
    single_cmd = next(c for c in diff_calls if "single" in c)
    assert (
        single_cmd[:6],
        "--revision" in single_cmd,
        "abcdef0123456789abcdef0123456789abcdef01" in single_cmd,
    ) == (
        ["argocd", "app", "diff", "single", "--server", "argocd.example.com"],
        True,
        True,
    )

    # Verify multi-source call structure
    multi_cmd = next(c for c in diff_calls if "multi" in c)
    assert (
        multi_cmd[:6],
        "--source-positions" in multi_cmd,
        "2" in multi_cmd,
        "--revisions" in multi_cmd,
        "abcdef0123456789abcdef0123456789abcdef01" in multi_cmd,
    ) == (
        ["argocd", "app", "diff", "multi", "--server", "argocd.example.com"],
        True,
        True,
        True,
        True,
    )


def test_diff_exit_codes_reporting(tmp_path: Path) -> None:
    """Exit 1 reports 'differs', exit 2 reports 'failed' with truncated stderr."""
    apps_dir = tmp_path / "k8s" / "argocd" / "apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "app1.yaml").write_text(
        "apiVersion: argoproj.io/v1alpha1\nkind: Application\nmetadata:\n  name: app1\nspec:\n  source:\n    repoURL: https://github.com/dan-petty/devops-cli\n    path: k8s/apps/app1\n",
        encoding="utf-8",
    )

    # 1. Exit 1 (differs)
    runner_diff = FakeRunner(diff_code=1, diff_stdout="--- live\n+++ target\n")
    with (
        patch(
            "devops_cli.k8s.argocd_live_report.resolve_argocd_server_and_token",
            return_value=("https://example.com", "tok"),
        ),
        patch("shutil.which", return_value="/usr/local/bin/argocd"),
    ):
        res_diff = report_argocd_live_diff(tmp_path, sha="1234", runner=runner_diff)

    assert any("differs" in line for line in res_diff)

    # 2. Exit 2 (failed) with long error
    long_stderr = "x" * 500
    runner_fail = FakeRunner(diff_code=2, diff_stderr=long_stderr)
    with (
        patch(
            "devops_cli.k8s.argocd_live_report.resolve_argocd_server_and_token",
            return_value=("https://example.com", "tok"),
        ),
        patch("shutil.which", return_value="/usr/local/bin/argocd"),
    ):
        res_fail = report_argocd_live_diff(tmp_path, sha="1234", runner=runner_fail)

    failed_line = next(line for line in res_fail if "failed" in line)
    # Detail should not exceed CONST_MAX_ERROR_DETAIL_LENGTH
    assert (
        "failed" in failed_line,
        "x" * (CONST_MAX_ERROR_DETAIL_LENGTH + 1) not in failed_line,
    ) == (True, True)


def test_uncovered_placeholder_host_reports_deploy_stack(tmp_path: Path) -> None:
    """A placeholder host at tip without live test operation is reported with deploy-stack."""
    apps_dir = tmp_path / "k8s" / "argocd" / "apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "devops.yaml").write_text(
        "apiVersion: argoproj.io/v1alpha1\nkind: Application\nmetadata:\n  name: devops\nspec:\n  source:\n    repoURL: https://github.com/dan-petty/devops-cli\n    path: k8s/devops\n",
        encoding="utf-8",
    )
    devops_path = tmp_path / "k8s" / "devops"
    devops_path.mkdir(parents=True)
    (devops_path / "kustomization.yaml").write_text(
        "resources:\n  - ingress.yaml\n", encoding="utf-8"
    )
    (devops_path / "ingress.yaml").write_text(
        "apiVersion: networking.k8s.io/v1\n"
        "kind: Ingress\n"
        "metadata:\n"
        "  name: devops-ui\n"
        "spec:\n"
        "  rules:\n"
        "    - host: devops.example.com\n"
        "      http:\n"
        "        paths: []\n",
        encoding="utf-8",
    )

    # Live app json does NOT have devops.example.com in test ops
    app_json = '{"spec": {"source": {"kustomize": {"patches": []}}}}'
    runner = FakeRunner(diff_code=0, app_json=app_json)

    with (
        patch(
            "devops_cli.k8s.argocd_live_report.resolve_argocd_server_and_token",
            return_value=("https://example.com", "tok"),
        ),
        patch("shutil.which", return_value="/usr/local/bin/argocd"),
    ):
        report = report_argocd_live_diff(tmp_path, sha="1234", runner=runner)

    assert any(
        "devops.example.com" in line and "deploy-stack --stack devops" in line for line in report
    )
