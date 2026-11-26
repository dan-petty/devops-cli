"""The commands that read the environment tree take it from `--k8s-dir`, else from the profile
fact `kubernetes.dir`, and the names of live objects come from the settings (#5131)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.dry_run import set_dry_run
from tests.support.fakes.process import ProcessFake
from tests.support.k8s_commands import write_chart_applications
from tests.support.k8s_tree import write_gateway_render_inputs

# The GitHub App the Service acts as, in config.yaml (ADR 0015).
_SERVICE = {"repos": ["owner/repo"], "github_app": {"app_id": 1, "installation_id": 2, "slug": "a"}}


@pytest.fixture(autouse=True)
def _no_dry_run_left() -> Any:
    yield
    set_dry_run(False)


def _details(output: str) -> dict[str, Any]:
    details: dict[str, Any] = json.loads(output[output.index("{") :])["details"]
    return details


def _copy_outside_any_repository(tree: Path, tmp_path: Path) -> Path:
    """A copy of the environment tree `tree` whose parent is no repository. The copy keeps the
    name of its folder, which the path sources of the Applications name."""
    target = tmp_path / "copy" / tree.name
    shutil.copytree(tree, target)
    return target


def _write_infra_repo(root: Path, dashboards: dict[str, str]) -> Path:
    """Write at `root` a repository whose profile names its tree `k8s`, with one dashboard for
    each file name and uid of `dashboards`. Return the tree."""
    (root / ".git").mkdir(parents=True)
    (root / ".devops").mkdir()
    (root / ".devops" / "project.toml").write_text('[kubernetes]\ndir = "k8s"\n', "utf-8")
    folder = root / "k8s" / "monitoring" / "dashboards"
    folder.mkdir(parents=True)
    for name, uid in dashboards.items():
        document = {"uid": uid, "title": name, "panels": []}
        (folder / name).write_text(json.dumps(document), encoding="utf-8")
    return root / "k8s"


def _relative(details: dict[str, Any], *roots: Path) -> str:
    """The details of a dry run, with each path under one of `roots` written under `<root>`."""
    text = json.dumps(details, sort_keys=True)
    for root in roots:
        text = text.replace(str(root), "<root>")
    return text


def test_deploy_stack_reads_a_copy_of_the_tree_as_it_reads_the_tree(
    cli: Callable[..., Any],
    config: Callable[..., Path],
    environment_repo: Path,
    tmp_path: Path,
    process_fake: ProcessFake,
) -> None:
    """The dry run of a copy outside the repository names the same releases, values files,
    manifests and kustomizations, under the copy. The product base stays `k8s/devops` of the
    current repository."""
    config(service=_SERVICE)
    tree = environment_repo / "k8s"
    copy_of_tree = _copy_outside_any_repository(tree, tmp_path)

    in_tree = cli("k8s", "deploy-stack", "--stack", "all", "--dry-run")
    in_copy = cli(
        "k8s", "deploy-stack", "--stack", "all", "--k8s-dir", str(copy_of_tree), "--dry-run"
    )

    read, copied = _details(in_tree.output), _details(in_copy.output)
    assert (
        in_tree.exit_code,
        in_copy.exit_code,
        copied["product_dir"],
        _relative(copied, copy_of_tree, tree),
    ) == (0, 0, str(tree / "devops"), _relative(read, tree))


def test_dashboards_lint_reads_a_copy_of_the_tree_as_it_reads_the_tree(
    cli: Callable[..., Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = _write_infra_repo(tmp_path / "infra", {"a.json": "a", "b.json": "b"})
    copy_of_tree = _copy_outside_any_repository(tree, tmp_path)
    monkeypatch.chdir(tree.parent)

    in_tree = cli("grafana", "dashboards", "lint", "--json")
    in_copy = cli("grafana", "dashboards", "lint", "--k8s-dir", str(copy_of_tree), "--json")

    assert (in_copy.exit_code, json.loads(in_copy.output)) == (
        in_tree.exit_code,
        json.loads(in_tree.output),
    )


def test_a_profile_of_another_repository_gives_the_tree(
    cli: Callable[..., Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In a checkout whose `.devops/project.toml` names its tree, `devops k8s check-deprecated`
    scans that tree when no target is given."""
    repo = tmp_path / "infra"
    (repo / ".git").mkdir(parents=True)
    (repo / ".devops").mkdir()
    (repo / ".devops" / "project.toml").write_text('[kubernetes]\ndir = "cluster"\n', "utf-8")
    write_chart_applications(repo / "cluster", "logging")
    monkeypatch.chdir(repo)

    result = cli("k8s", "check-deprecated", "--dry-run")

    assert (result.exit_code, str(repo / "cluster") in result.output) == (0, True)


def test_dashboards_lint_in_an_infra_repo_reads_only_its_tree(
    cli: Callable[..., Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An infra repo holds no product base, so the lint with no path reads the dashboards of the
    tree alone."""
    _write_infra_repo(tmp_path / "infra", {"coredns.json": "coredns"})
    monkeypatch.chdir(tmp_path / "infra")

    result = cli("grafana", "dashboards", "lint", "--json")

    assert (result.exit_code, [r["source_file"] for r in json.loads(result.output)]) == (
        0,
        ["coredns.json"],
    )


def test_no_tree_names_the_option_and_the_project_file(
    cli: Callable[..., Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "work" / ".git").mkdir(parents=True)
    monkeypatch.chdir(tmp_path / "work")

    result = cli("k8s", "lint", "--dry-run")

    assert (result.exit_code, "--k8s-dir" in result.output, "project.toml" in result.output) == (
        1,
        True,
        True,
    )


def test_gateway_render_reads_each_file_that_no_option_names_from_the_tree(
    cli: Callable[..., Any], env_tree: Path
) -> None:
    """After a render writes the files of the tree, the next render finds them up to date and
    names the gateway config of the tree."""
    write_gateway_render_inputs(env_tree)

    written = cli("ai", "gateway", "render", "--k8s-dir", str(env_tree), "--apply")
    result = cli("ai", "gateway", "render", "--k8s-dir", str(env_tree))

    assert (written.exit_code, result.exit_code) == (0, 0), written.output + result.output
    assert " ".join(result.output.split()).split(" at ")[1].split(" is already")[0] == str(
        env_tree / "llm" / "gateway" / "config.yaml"
    )


def test_ollama_prune_plans_from_the_gateway_config_of_the_tree(
    cli: Callable[..., Any], environment_repo: Path, tmp_path: Path
) -> None:
    """A tree whose gateway serves no model plans no removal; a tree that serves one does."""
    copy_of_tree = _copy_outside_any_repository(environment_repo / "k8s", tmp_path)
    (copy_of_tree / "llm" / "gateway" / "config.yaml").write_text("model_list: []\n", "utf-8")

    in_tree = cli("k8s", "ollama", "prune", "--dry-run")
    in_copy = cli("k8s", "ollama", "prune", "--k8s-dir", str(copy_of_tree), "--dry-run")

    assert (
        in_tree.exit_code,
        in_copy.exit_code,
        "ollama rm" in in_tree.output,
        "ollama rm" in in_copy.output,
    ) == (0, 0, True, False)


def test_bootstrap_gitops_applies_the_root_application_of_the_tree(
    cli: Callable[..., Any], environment_repo: Path
) -> None:
    root_application = environment_repo / "k8s" / "argocd" / "bootstrap" / "bootstrap.yaml"
    root_application.parent.mkdir(parents=True, exist_ok=True)
    root_application.write_text("kind: Application\n", "utf-8")

    result = cli("argo", "cd", "apps", "bootstrap-gitops", "--dry-run")

    assert (result.exit_code, str(root_application) in "".join(result.output.split())) == (0, True)


def test_gitops_sync_syncs_the_last_root_application_of_the_settings(
    cli: Callable[..., Any], config: Callable[..., Path]
) -> None:
    config(argocd={"root_applications": ["root", "apps-of-apps"]})

    result = cli("argo", "gitops", "sync", "--dry-run")

    assert (result.exit_code, "Plan for GitOps sync on 'apps-of-apps'" in result.output) == (
        0,
        True,
    )


def test_bootstrap_mattermost_uses_the_team_of_the_settings(
    cli: Callable[..., Any], config: Callable[..., Path], environment_repo: Path
) -> None:
    config(mattermost={"team": "example-team"})

    result = cli("k8s", "bootstrap-mattermost", "--dry-run")

    assert (result.exit_code, "example-team" in result.output) == (0, True)


def test_access_sync_names_the_application_and_policies_of_the_settings(
    cli: Callable[..., Any], config: Callable[..., Path]
) -> None:
    config(
        cloudflare={
            "domain": "example.com",
            "account_id": "acc-1",
            "access": {
                "allowed_emails": ["admin@example.com"],
                "bypass_ips": ["192.0.2.1"],
                "application_name": "Example Ingress",
                "allow_policy_name": "Allow example emails",
                "bypass_policy_name": "example-bypass",
            },
        }
    )

    result = cli("cloudflare", "access", "sync", "--dry-run", "--json")

    payload = json.loads(result.output)
    names = [json.loads(r["stdin"])["name"] for r in payload["requests"] if r.get("stdin")]
    assert (result.exit_code, payload["app_name"], names) == (
        0,
        "Example Ingress",
        [
            "Example Ingress",
            "Allow example emails",
            "Allow example emails",
            "example-bypass",
            "example-bypass",
        ],
    )


def test_the_gitea_doctor_checks_the_applications_of_the_settings(
    cli: Callable[..., Any], config: Callable[..., Path]
) -> None:
    config(gitea={"applications": ["forge"]})

    result = cli("k8s", "doctor", "--stack", "gitea", "--dry-run", "--format", "json")

    targets = [r["argv"] for r in json.loads(result.output)["requests"]]
    assert (result.exit_code, [argv for argv in targets if "applications" in " ".join(argv)]) == (
        0,
        [targets[0]],
    )
    assert "forge" in targets[0]


def test_the_names_of_live_objects_default_to_the_names_of_the_homelab() -> None:
    from devops_cli.config.settings import Settings

    settings = Settings()
    access = settings.cloudflare.access
    assert (
        settings.argocd.root_applications,
        settings.gitea.applications,
        settings.mattermost.team,
        access.application_name,
        access.allow_policy_name,
        access.bypass_policy_name,
    ) == (
        ["bootstrap", "cluster"],
        ["gitea", "gitea-manifests"],
        "homelab",
        "Homelab Ingress",
        "Allow homelab authorized emails",
        "homelab-public-ip-bypass",
    )
