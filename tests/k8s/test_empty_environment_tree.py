"""A command that reads the environment tree refuses a tree that does not hold what it reads, and
names the missing path and the way to give the tree: no command reports success on an empty tree
(#7290)."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.dry_run.state import set_dry_run
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.scanners import ScannerFake, ToolAnswer
from tests.support.k8s_commands import (
    write_cluster_secrets,
    write_environment_tree,
    write_stack_paths,
)

_APPLICATIONS = "argocd/apps"


@pytest.fixture
def hollow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The current repository declares `k8s` as its tree, and the folder holds a product base and
    no environment: the state of a checkout whose environment moved to another repository."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".devops").mkdir()
    (repo / ".devops" / "project.toml").write_text('[kubernetes]\ndir = "k8s"\n', "utf-8")
    (repo / "k8s" / "devops").mkdir(parents=True)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("COLUMNS", "400")
    return repo / "k8s"


@pytest.fixture(autouse=True)
def _dry_run_state() -> Any:
    yield
    set_dry_run(False)


def _text(result: Any) -> str:
    """The output of a run and the error that ended it, without the wrap of the console."""
    error = getattr(result.exception, "message", "")
    return "".join(f"{result.output}\n{error}".split())


@pytest.mark.parametrize(
    ("command", "missing"),
    [
        (("k8s", "lint"), _APPLICATIONS),
        (("k8s", "lint", "--dry-run"), _APPLICATIONS),
        (("k8s", "image-pins"), _APPLICATIONS),
        (("k8s", "image-pins", "--dry-run"), _APPLICATIONS),
        (("k8s", "catalog"), _APPLICATIONS),
        (("k8s", "catalog", "--dry-run"), _APPLICATIONS),
        (("k8s", "check-deprecated"), _APPLICATIONS),
        (("k8s", "check-deprecated", "--dry-run"), _APPLICATIONS),
        (("k8s", "deploy-stack", "--stack", "llm", "--dry-run"), _APPLICATIONS),
        (("k8s", "teardown-stack", "--stack", "llm", "--dry-run"), _APPLICATIONS),
        (("k8s", "teardown-stack", "--stack", "chat", "--dry-run"), _APPLICATIONS),
        (("k8s", "bootstrap", "--dry-run"), _APPLICATIONS),
        (("k8s", "ollama", "prune", "--dry-run"), "llm/gateway/config.yaml"),
        (("k8s", "push-secrets", "--plan"), "cluster-secrets.toml"),
        (("k8s", "push-secrets", "--dry-run"), "cluster-secrets.toml"),
        (("k8s", "bootstrap-mattermost", "--dry-run"), "cluster-secrets.toml"),
        (
            ("argo", "cd", "apps", "bootstrap-gitops", "--dry-run"),
            "argocd/bootstrap/bootstrap.yaml",
        ),
        (("argo", "gitops", "drift"), _APPLICATIONS),
        (("grafana", "dashboards", "sync", "--dry-run"), "monitoring/dashboards"),
        (("ai", "gateway", "render"), "llm/gateway/config.yaml"),
    ],
    ids=lambda value: " ".join(value) if isinstance(value, tuple) else "",
)
def test_a_command_refuses_a_tree_without_the_path_it_reads(
    hollow: Path,
    cli: Callable[..., Any],
    process_fake: ProcessFake,
    command: tuple[str, ...],
    missing: str,
) -> None:
    result = cli(*command)

    text = _text(result)
    assert (
        result.exit_code != 0,
        str(hollow / missing) in text or missing in text,
        "--k8s-dir" in text,
        "infra.repos" in text,
    ) == (True, True, True, True), result.output


def test_a_tree_that_is_not_there_is_not_read(
    tmp_path: Path, cli: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COLUMNS", "400")

    result = cli("k8s", "push-secrets", "--dry-run", "--k8s-dir", str(tmp_path / "gone"))

    assert (result.exit_code != 0, "cluster-secrets.toml" in _text(result)) == (True, True)


def test_a_folder_of_applications_with_no_application_is_empty(
    hollow: Path, cli: Callable[..., Any]
) -> None:
    (hollow / "argocd" / "apps").mkdir(parents=True)

    result = cli("k8s", "image-pins")

    assert (result.exit_code != 0, _APPLICATIONS in _text(result)) == (True, True)


def test_image_pins_refuses_a_build_that_names_no_image(
    tmp_path: Path, cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """A check that read no image proved nothing, also with `--managed`."""
    base = tmp_path / "base"
    base.mkdir()
    (base / "kustomization.yaml").write_text("resources: []\n", "utf-8")
    process_fake.answer(("kubectl", "kustomize"), ProcessAnswer(stdout=""))

    result = cli("k8s", "image-pins", str(base), "--managed", "ghcr.io/example/product")

    assert (result.exit_code != 0, "noimage" in _text(result)) == (True, True)


@pytest.mark.parametrize("has_config", [True, False], ids=["config", "no-config"])
def test_lint_of_a_folder_needs_an_object_and_reads_the_config_of_its_repository(
    tmp_path: Path,
    cli: Callable[..., Any],
    scanner_fake: ScannerFake,
    has_config: bool,
) -> None:
    """kube-linter itself fails a folder with no object, and reads the `.kube-linter.yaml` of the
    repository that holds the folder, not of the folder."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "k8s" / "devops").mkdir(parents=True)
    if has_config:
        (repo / ".kube-linter.yaml").write_text("checks: {}\n", "utf-8")
    seen: list[tuple[str, ...]] = []

    def kube_linter(request: Any) -> ToolAnswer:
        seen.append(tuple(request.arguments[2:]))
        return ToolAnswer(exit_code=1, stderr="Error: no valid objects found")

    scanner_fake.answer_with("kube-linter", kube_linter)

    result = cli("k8s", "lint", str(repo / "k8s" / "devops"))

    config = ("--config", str(repo / ".kube-linter.yaml")) if has_config else ()
    assert (result.exit_code, seen) == (
        1,
        [("--format", "json", *config, "--fail-if-no-objects-found")],
    )


def test_a_deploy_reads_the_secret_table_before_it_reaches_the_cluster(
    hollow: Path, cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """The push is a later step of the deploy: a tree with no Secret table stops it first."""
    write_stack_paths(hollow, "llm")
    apps = hollow / "argocd" / "apps"
    apps.mkdir(parents=True)
    for name in ("open-webui", "qdrant"):
        (apps / f"{name}.yaml").write_text(
            f"kind: Application\nmetadata:\n  name: {name}\nspec:\n  source:\n"
            f"    repoURL: https://charts.example.com\n    chart: {name}\n"
            "    targetRevision: 1.2.3\n",
            "utf-8",
        )
    process_fake.answer(
        lambda call: "remote.origin.url" in call.argv,
        ProcessAnswer(stdout="https://github.com/example/repo.git\n"),
    )

    result = cli("k8s", "deploy-stack", "--stack", "llm", "--context", "example")

    cluster = [c.argv for c in process_fake.calls if c.argv[0] in ("kubectl", "helm")]
    assert (result.exit_code, "cluster-secrets.toml" in _text(result), cluster) == (1, True, [])


def test_bootstrap_mattermost_reads_the_secret_table_of_the_tree_it_is_given(
    hollow: Path, cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """The error of a tree with no Secret table names `--k8s-dir`, so the command takes it: the
    run reads the table of that tree and goes on to the cluster."""
    tree = hollow.parent / "given"
    write_cluster_secrets(tree)
    process_fake.answer("kubectl", ProcessAnswer(stdout=""))

    result = cli("k8s", "bootstrap-mattermost", "--k8s-dir", str(tree))

    assert (result.exit_code, "NoMattermostpodfound" in _text(result)) == (1, True), result.output


@pytest.mark.parametrize(
    ("command", "stack", "missing"),
    [
        ("deploy-stack", "llm", "llm/valkey-runs.yaml"),
        ("deploy-stack", "llm", "llm/gateway-db.yaml"),
        ("deploy-stack", "infra", "monitoring"),
        ("deploy-stack", "chat", "mattermost"),
        ("deploy-stack", "llm", "kustomization.yaml"),
        ("teardown-stack", "llm", "llm/valkey-runs.yaml"),
        ("teardown-stack", "chat", "mattermost"),
        ("teardown-stack", "all", "kustomization.yaml"),
    ],
    ids=lambda value: value,
)
def test_a_stack_command_refuses_a_tree_that_lacks_a_path_of_the_stack(
    tmp_path: Path,
    cli: Callable[..., Any],
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    stack: str,
    missing: str,
) -> None:
    """A tree with its Applications and not each file of the stack lists no file that is not
    there: a real teardown ignores a missing object and reports success."""
    monkeypatch.setenv("COLUMNS", "400")
    tree = write_environment_tree(tmp_path / "tree")
    path = tree / missing
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    process_fake.answer(lambda call: True, ProcessAnswer(stdout=""))
    secrets = ("--no-push-secrets",) if command == "deploy-stack" else ()

    result = cli("k8s", command, "--stack", stack, "--dry-run", "--k8s-dir", str(tree), *secrets)

    assert (result.exit_code != 0, missing in _text(result)) == (True, True), result.output
