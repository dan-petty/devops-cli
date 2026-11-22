"""The builds of the path sources of the Argo CD Applications of an environment tree (#6068)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from devops_cli.exceptions.k8s import ApplicationSourceError
from devops_cli.k8s.app_render import write_path_renders
from devops_cli.k8s.environment import EnvironmentTree
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

_ORIGIN = "https://github.com/example/repo"
_OTHER = "https://github.com/example/other"

# One chart source, then two path sources: one of this repository and one of another repository.
_APPLICATION = f"""apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: web
  namespace: argocd
spec:
  project: default
  sources:
    - repoURL: https://charts.example.com
      chart: example
      targetRevision: 1.2.3
    - repoURL: {_ORIGIN}
      path: k8s/web
    - repoURL: {_OTHER}
      targetRevision: main
      path: k8s/other
  destination:
    namespace: web
"""


def _kustomize(call: ProcessCall) -> ProcessAnswer:
    """`kubectl kustomize <directory>` prints the name of the directory that it builds."""
    return ProcessAnswer(stdout=f"built: {Path(call.argv[2]).name}\n")


def _checkout(call: ProcessCall) -> ProcessAnswer:
    """`git -C <checkout> checkout` of the other repository writes its kustomization `k8s/other`."""
    folder = Path(call.argv[2]) / "k8s" / "other"
    folder.mkdir(parents=True)
    (folder / "kustomization.yaml").write_text("resources: []\n", encoding="utf-8")
    return ProcessAnswer()


@pytest.fixture(autouse=True)
def _answers(process_fake: ProcessFake) -> Iterator[None]:
    """kubectl builds a folder, git names the origin, and a fetch checks out the other repository."""
    process_fake.answer(("kubectl", "kustomize"), _kustomize)
    process_fake.answer(
        lambda call: "remote.origin.url" in call.argv, ProcessAnswer(stdout=f"{_ORIGIN}.git\n")
    )
    process_fake.answer(lambda call: call.argv[3:4] == ("checkout",), _checkout)
    yield


def _tree(root: Path) -> EnvironmentTree:
    """A repository at `root` with the Application `web` and the kustomization `k8s/web`."""
    apps = root / "k8s" / "argocd" / "apps"
    apps.mkdir(parents=True)
    (apps / "web.yaml").write_text(_APPLICATION, encoding="utf-8")
    (root / "k8s" / "web").mkdir()
    (root / "k8s" / "web" / "kustomization.yaml").write_text("resources: []\n", encoding="utf-8")
    return EnvironmentTree(root / "k8s", root)


def test_each_path_source_is_built_into_a_file_named_for_its_application_and_place(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """Each path source is built with kustomize into `<application>-<index>.yaml`, where the index
    is the place of the source in the Application: the source of the repository from the checkout,
    the source of another repository from its fetch. A chart source is not built."""
    renders = write_path_renders(_tree(tmp_path / "repo"), tmp_path / "work")

    commands = [call.argv[:2] for call in process_fake.calls]
    assert (
        [(path.name, path.read_text(encoding="utf-8")) for path in sorted(renders.iterdir())],
        ("helm", "template") in commands,
    ) == ([("web-1.yaml", "built: web\n"), ("web-2.yaml", "built: other\n")], False)


def test_the_folder_of_the_builds_holds_no_file_of_a_fetched_source(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """A fetched repository goes to a folder beside the builds, so a tool that reads the folder of
    the builds reads only the builds."""
    renders = write_path_renders(_tree(tmp_path / "repo"), tmp_path / "work")

    assert sorted(path.name for path in renders.rglob("*")) == [
        "web-1.yaml",
        "web-2.yaml",
    ]


def test_a_path_out_of_the_folder_of_its_repository_is_not_built(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """Argo CD builds no path that goes out of the folder of its repository, so no build reads a
    folder outside the checkout (#6681)."""
    env = _tree(tmp_path / "repo")
    application = env.root / "argocd" / "apps" / "web.yaml"
    application.write_text(_APPLICATION.replace("path: k8s/web", "path: ../outside"), "utf-8")
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "kustomization.yaml").write_text("resources: []\n", "utf-8")

    with pytest.raises(ApplicationSourceError) as caught:
        write_path_renders(env, tmp_path / "work")

    assert (
        "../outside" in caught.value.message,
        [call.argv for call in process_fake.calls if call.argv[-1].endswith("outside")],
    ) == (True, [])
