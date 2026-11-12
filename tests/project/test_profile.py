"""The project profile of a repository: the type template, the facts detected in its files and
its `.devops/project.toml`, merged in that order, each value with its source (#4627, #5121)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.exceptions import ConfigurationError
from devops_cli.project.profile import ProjectType, resolve_profile, type_template

_CONFIG = """[defaults]
inventory = ansible/inventory/hosts.yaml
roles_path = ansible/roles:./roles:../roles
"""


def _repo(tmp_path: Path, *, project_file: str | None = None) -> Path:
    """A repository with an `ansible.cfg`, an inventory, roles, playbooks and a `k8s` folder."""
    root = tmp_path / "repo"
    for folder in ("ansible/inventory", "ansible/roles/common/tasks", "ansible/playbooks", "k8s"):
        (root / folder).mkdir(parents=True)
    (root / "ansible.cfg").write_text(_CONFIG, encoding="utf-8")
    if project_file is not None:
        (root / ".devops").mkdir()
        (root / ".devops" / "project.toml").write_text(project_file, encoding="utf-8")
    return root


def test_an_ansible_cfg_makes_the_type_and_gives_the_layout(tmp_path: Path) -> None:
    resolved = resolve_profile(_repo(tmp_path))

    assert resolved.profile.model_dump(mode="json") == {
        "extends": "ansible-k8s",
        "ansible": {
            "inventory": ["ansible/inventory/hosts.yaml"],
            "playbook_dir": "ansible/playbooks",
            "roles_path": ["ansible/roles"],
            "offline_group": "offline",
        },
        "kubernetes": {"dir": "k8s"},
    }
    assert resolved.sources == {
        "extends": "detected: ansible.cfg",
        "ansible.inventory": "detected: ansible.cfg",
        "ansible.playbook_dir": "detected: ansible/playbooks",
        "ansible.roles_path": "detected: ansible.cfg",
        "ansible.offline_group": "template: ansible-k8s",
        "kubernetes.dir": "detected: k8s",
    }
    assert resolved.project_file is False


def test_the_project_file_wins_over_detection_and_the_template(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        project_file='extends = "ansible-k8s"\n[ansible]\noffline_group = "retired"\n',
    )

    resolved = resolve_profile(root)

    assert (
        resolved.profile.ansible.offline_group,
        resolved.sources["ansible.offline_group"],
        resolved.sources["extends"],
        resolved.sources["ansible.inventory"],
        resolved.project_file,
    ) == ("retired", ".devops/project.toml", ".devops/project.toml", "detected: ansible.cfg", True)


def test_the_values_to_declare_are_those_that_differ_from_the_template(tmp_path: Path) -> None:
    resolved = resolve_profile(_repo(tmp_path))

    assert resolved.declarable() == {
        "extends": "ansible-k8s",
        "ansible.inventory": ["ansible/inventory/hosts.yaml"],
        "ansible.playbook_dir": "ansible/playbooks",
        "ansible.roles_path": ["ansible/roles"],
        "kubernetes.dir": "k8s",
    }


def test_a_repository_with_no_marker_has_no_type(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    resolved = resolve_profile(root)

    assert (resolved.profile.extends, resolved.profile.ansible.offline_group, resolved.sources) == (
        None,
        None,
        {},
    )


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("extends = [", id="not-toml"),
        pytest.param('extends = "cobol"\n', id="unknown-type"),
        pytest.param("[ansible]\nhosts = 3\n", id="unknown-key"),
    ],
)
def test_an_invalid_project_file_is_refused(tmp_path: Path, text: str) -> None:
    root = _repo(tmp_path, project_file=text)

    with pytest.raises(ConfigurationError) as caught:
        resolve_profile(root)

    assert (caught.value.error_code, caught.value.key) == (
        "CONFIGURATION_ERROR",
        ".devops/project.toml",
    )


def test_each_type_has_a_packaged_template() -> None:
    assert [sorted(type_template(kind)) for kind in ProjectType] == [["ansible"]]
